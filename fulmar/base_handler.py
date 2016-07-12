# -*- encoding: utf-8 -*-

import sys
import inspect
import fractions
import logging

import six
from six import add_metaclass

from fulmar.utils import (
    quote_chinese, build_url, encode_params)
from fulmar.utils import sha1string
from fulmar.pprint import pprint

logger = logging.getLogger(__name__)

def catch_status_code_error(func):
    """
    Non-200 response will been regarded as fetch failed and will not pass to callback.
    Use this decorator to override this feature.
    """
    func._catch_status_code_error = True
    return func


def config(_config=None, **kwargs):
    """
    A decorator for setting the default kwargs of `BaseHandler.crawl`.
    Any self.crawl with this callback will use this config.
    """
    if _config is None:
        _config = {}
    _config.update(kwargs)

    def wrapper(func):
        func._config = _config
        return func
    return wrapper


class NOTSET(object):
    pass


def every(minutes=NOTSET, seconds=NOTSET):
    """
    method will been called every minutes or seconds
    """
    def wrapper(func):
        # mark the function with variable 'is_cronjob=True', the function would be
        # collected into the list Handler._cron_jobs by meta class
        func.is_cronjob = True

        # collect interval and unify to seconds, it's used in meta class. See the
        # comments in meta class.
        func.tick = minutes * 60 + seconds
        return func

    if inspect.isfunction(minutes):
        func = minutes
        minutes = 1
        seconds = 0
        return wrapper(func)

    if minutes is NOTSET:
        if seconds is NOTSET:
            minutes = 1
            seconds = 0
        else:
            minutes = 0
    if seconds is NOTSET:
        seconds = 0

    return wrapper


class BaseHandlerMeta(type):
    def __new__(cls, name, bases, attrs):
        # A list of all functions which is marked as 'is_cronjob=True'
        cron_jobs = []

        # The min_tick is the greatest common divisor(GCD) of the interval of cronjobs
        # this value would be queried by scheduler when the project initial loaded.
        # Scheudler may only send _on_cronjob task every min_tick seconds. It can reduce
        # the number of tasks sent from scheduler.
        min_tick = 0

        for each in attrs.values():
            if inspect.isfunction(each) and getattr(each, 'is_cronjob', False):
                cron_jobs.append(each)
                min_tick = fractions.gcd(min_tick, each.tick)
        newcls = type.__new__(cls, name, bases, attrs)
        newcls._cron_jobs = cron_jobs
        newcls._min_tick = min_tick
        return newcls


@add_metaclass(BaseHandlerMeta)
class BaseHandler(object):
    """BaseHandler for all scripts.

    `BaseHandler.run` is the main method to handler the task.
    """
    project_name = None
    project_id = None

    _cron_jobs = []
    _min_tick = 0
    __env__ = {'not_inited': True}
    retry_delay = {}

    def __init__(self):
        self.curr_conn_cookie = {}

    def _reset(self):
        """
        reset before each task
        """
        self.curr_conn_cookie = {}
        self._follows = []

    def _run_task(self, task, response):
        """
        Finding callback specified by `task['callback']`
        raising status error for it if needed.
        """
        process = task.get('process', {})
        callback = process.get('callback', '__call__')
        callback_args = process.get('callback_args', [])
        callback_kwargs = process.get('callback_kwargs', {})

        if not hasattr(self, callback):
            raise NotImplementedError("self.%s() not implemented!" % callback)

        function = getattr(self, callback)
        #logger.info(function)
        # do not run_func when 304
        if response.status_code == 304 and not getattr(function, '_catch_status_code_error', False):
            return None
        if not getattr(function, '_catch_status_code_error', False):
            response.raise_for_status()

        if function.__name__ == 'on_start':
            return function(*callback_args, **callback_kwargs)
        return function(response, *callback_args, **callback_kwargs)

    def run_task(self, module, task, response):
        """
        Processing the task, catching exceptions and logs, return a `ProcessorResult` object
        """
        logger = module.logger
        result = None
        exception = None
        self.task = task
        self.response = response
        self.curr_conn_cookie = response.cookies
        try:
            self._reset()
            result = self._run_task(task, response)
            if inspect.isgenerator(result):
                for r in result:
                    self.on_result(r)
            else:
                self.on_result(result)
        except Exception as e:
            logger.exception(e)
            exception = e
        finally:
            follows = self._follows

            self.task = None
            self.response = None
            self.save = None

        return (result, follows,  exception)

    def _crawl(self, url, **kwargs):
        """
        real crawl API

        checking kwargs, and repack them to each sub-dict
        """
        task = {}

        assert len(url) < 1024, "Maximum (1024) URL length error."

        if kwargs.get('callback'):
            callback = kwargs['callback']
            if isinstance(callback, six.string_types) and hasattr(self, callback):
                func = getattr(self, callback)
            elif six.callable(callback) and six.get_method_self(callback) is self:
                func = callback
                kwargs['callback'] = func.__name__
            else:
                raise NotImplementedError("self.%s() not implemented!" % callback)

        url = quote_chinese(build_url(url.strip(), kwargs.pop('params', None)))
        if kwargs.get('data'):
            kwargs['data'] = encode_params(kwargs['data'])
        if kwargs.get('data'):
            kwargs.setdefault('method', 'POST')

        schedule = {}
        for key in ('priority', 'retries', 'start_time', 'age', 'rate'):
            if key in kwargs:
                schedule[key] = kwargs.pop(key)
        task['schedule'] = schedule

        fetch = {}

        for key in (
                'method',
                'headers',
                'data',
                'timeout',
                'cookies',
                'allow_redirects',
                'proxy',
                'js_run_at',
                'js_script',
                'js_viewport_width',
                'js_viewport_height',
                'load_images',
                'fetch_type',
                'validate_cert',
                'max_redirects',
        ):
            if key in kwargs:
                fetch[key] = kwargs.pop(key)

        if kwargs.get('cookie_persistence', True) != False:
            if fetch.get('cookies'):
                fetch['cookies'] = fetch['cookies'].update(self.curr_conn_cookie)
            else:
                fetch['cookies'] = self.curr_conn_cookie
        task['fetch'] = fetch

        process = {}
        for key in ('callback', 'callback_args', 'callback_kwargs'):
            if key in kwargs:
                process[key] = kwargs.pop(key)
        task['process'] = process

        task['project_name'] = self.project_name
        task['project_id'] = self.project_id
        task['url'] = url
        if 'taskid' in kwargs:
            task['taskid'] = kwargs.pop('taskid')
        else:
            task['taskid'] = self.get_taskid(task)

        crawl_rate = {}
        for key in ('request_number', 'time_period', ):
            if key in kwargs:
                crawl_rate[key] = kwargs.pop(key)
        if crawl_rate:
            if not crawl_rate.get('time_period'):
                crawl_rate['time_period'] = 1
            if not crawl_rate.get('key_name'):
                crawl_rate['key_name'] = self.project_name
        task['crawl_rate'] = crawl_rate

        if kwargs:
            raise TypeError('crawl() got unexpected keyword argument: %s' % kwargs.keys())

        #logger.info('in_crawl: task %s ' % str(task))
        self._follows.append(task)

    def get_taskid(self, task):
        '''Generate taskid by information of task sha1(url) by default, override me'''
        return sha1string(task['url'])

    # apis
    def crawl(self, url, **kwargs):
        '''
        params=None,

        method=None,
        data=None,
        headers=None,
        cookies=None,
        cookie_persistence=True,
        timeout=None,
        allow_redirects=True,
        proxies=None,

        fetch_type=None,
        js_run_at=None,
        js_script=None,
        js_viewport_width=None,
        js_viewport_height=None,
        load_images=None,

        priority=None, # type: int. The bigger, the higher priority.
        retries=None,
        exetime=None,
        age=None,

        taskid=None,

        callback=None,
        callback_args=[],
        callback_kwargs={}

        crawl_limit:
            request_number
            time_period
        ----------------------
        available params:

          url
          params

          # fetch
          method
          data
          headers
          timeout
          allow_redirects
          cookies
          cookie_persistence
          proxy

          # js fetch
          fetch_type
          js_run_at
          js_script
          js_viewport_width
          js_viewport_height
          load_images

          priority
          retries
          exetime
          age

          taskid

          callback

        '''

        if isinstance(url, six.string_types):
            return self._crawl(url, **kwargs)
        elif hasattr(url, "__iter__"):
            result = []
            for each in url:
                result.append(self._crawl(each, **kwargs))
            return result

    def is_debugger(self):
        """Return true if running in debugger"""
        return self.__env__.get('debugger')

    def on_result(self, result):
        """Receiving returns from other callback, override me."""
        if not result:
            return
        assert self.task, "on_result can't outside a callback."
        if self.is_debugger():
            pprint(result)
        if self.__env__.get('result_queue'):
            self.__env__['result_queue'].put((self.task, result))

    def _on_cronjob(self, response, task):
        if (not response.save
                or not isinstance(response.save, dict)
                or 'tick' not in response.save):
            return

        # When triggered, a '_on_cronjob' task is sent from scheudler with 'tick' in
        # Response.save. Scheduler may at least send the trigger task every GCD of the
        # inverval of the cronjobs. The method should check the tick for each cronjob
        # function to confirm the execute interval.
        for cronjob in self._cron_jobs:
            if response.save['tick'] % cronjob.tick != 0:
                continue
            function = cronjob.__get__(self, self.__class__)
            function(response, task)