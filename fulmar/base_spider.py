# -*- encoding: utf-8 -*-
import inspect
import logging

import six

from fulmar.utils import (
    quote_chinese, build_url, encode_params)
from fulmar.utils import sha1string
from fulmar.pprint import pprint

logger = logging.getLogger(__name__)


def crawl_rate(request_number=None, time_period=1):
    def handle_func(func):
        def inner(*args, **kwargs):
            local_time_period = time_period
            if request_number:
                kwargs.update(time_period=local_time_period, request_number=request_number)
            else:
                raise KeyError('crawl_rate() did not get expected keyword argument: %s.' % 'request_number')
            return func(*args, **kwargs)
        return inner
    return handle_func


class BaseSpider(object):
    """BaseSpider for project scripts."""
    project_name = None
    project_id = None

    __env__ = {'not_inited': True}

    def __init__(self,
                 request_number=None,
                 time_period=None,
                 db_name=None,
                 coll_name=None):

        self.request_number = request_number
        self.time_period = time_period
        self.db_name = db_name
        self.coll_name = coll_name or 'result'

        self._curr_conn_cookie = {}
        self._follows = []

    def _reset(self):
        """
        reset before each task
        """
        self._curr_conn_cookie = {}
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

        # todo: don't handle this error.
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
        Processing the task, catching exceptions and logs
        """
        logger = module.logger
        results = None
        self.task = task
        self.response = response
        self._curr_conn_cookie = response.cookies
        try:
            self._reset()
            results = self._run_task(task, response)
        except Exception as e:
            logger.exception(e)
        finally:
            follows = self._follows
            self.task = None
            self.response = None
            self.save = None

        return (results, follows, self.db_name or self.project_name, self.coll_name)

    def _crawl(self, url, **kwargs):
        """
        real crawl API.

        checking kwargs, and repack them to each sub-dict.
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
            kwargs.setdefault('method', 'POST')

        schedule = {}
        for key in (
            'priority',
            ):
            if key in kwargs:
                schedule[key] = kwargs.pop(key)
        for key in (
            'crawl_at', 'crawl_later',
            'crawl_period'
        ):
            if key in kwargs:
                schedule['is_cron'] = True
                schedule[key] = kwargs.pop(key)

        task['schedule'] = schedule
        fetch = {}
        for key in (
                'method',
                'headers',
                'data',
                'timeout',
                'cookies',
                'max_redirects',
                'proxy_host',
                'proxy_port',
                'proxy_username',
                'proxy_password',
                'js_run_at',
                'js_script',
                'js_viewport_width',
                'js_viewport_height',
                'load_images',
                'fetch_type',
                'validate_cert',
        ):
            if key in kwargs:
                fetch[key] = kwargs.pop(key)

        if kwargs.get('cookie_persistence', True):
            if fetch.get('cookies'):
                fetch['cookies'].update(self._curr_conn_cookie)
            else:
                fetch['cookies'] = self._curr_conn_cookie

        if kwargs.get('allow_redirects'):
            fetch['allow_redirects'] = kwargs.pop('allow_redirects')
        else:
            fetch['allow_redirects'] = True

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
        for key in ('request_number', 'time_period'):
            if key in kwargs:
                crawl_rate[key] = kwargs.pop(key)
        if crawl_rate:
            if not crawl_rate.get('request_number'):
                raise KeyError('crawl() did not get expected keyword argument: %s' % 'request_number')
            if not crawl_rate.get('time_period'):
                crawl_rate['time_period'] = 1
            crawl_rate['limit_level'] = 'rate_limit: %s' % task['url']
        elif self.request_number and self.time_period:
            crawl_rate['limit_level'] = 'rate_limit: %s' % self.project_name
            crawl_rate.update({
                'request_number': self.request_number,
                'time_period': self.time_period
            })
        task['crawl_rate'] = crawl_rate

        if kwargs:
            raise TypeError('crawl() got unexpected keyword argument: %s' % kwargs.keys())

        self._follows.append(task)

    def get_taskid(self, task):
        '''Generate taskid by information of task sha1(url) by default, override me'''
        return sha1string(task['url'])

    def crawl(self, url, **kwargs):
        """Constructs a http request.

        :param url: URL for the new request.
        :param method: method for the new request. Defaults to ``GET``.
        :param params: (optional) Dictionary or bytes to be sent in the query string for the request.
        :param data: (optional) Dictionary or bytes to be send in the body of request.
        :param headers: (optional) Dictionary of HTTP Headers to be send with the request.
        :param cookies: (optional) Dictionary to be send with the request.
        :param cookie_persistence: Previous request and response's cookies will persist next
            request for the same website. Defaults to ``True``.
        :type cookie_persistence: bool.
        :param timeout: (optional) How long to wait for the server to send data before giving up.
        :type timeout: float
        :param allow_redirects: (optional) Boolean. Defaults to ``True``.
        :type allow_redirects: bool.
        :param proxy_host: (optional) HTTP proxy hostname.
            To use proxies, proxy_host and proxy_port must be set; proxy_username and proxy_password are optional.
        :type proxy_host: string.
        :param proxy_port: (optional) HTTP proxy port.
        :type proxy_port: Int.
        :param proxy_username: (optional) HTTP proxy username.
        :type proxy_username: string.
        :param proxy_password: (optional) HTTP proxy password.
        :type proxy_password: string.
        :param fetch_type: (optional) Set to ``js`` to enable JavaScript fetcher. Defaults to ``None``.
        :param js_script: (optional) JavaScript run before or after page loaded,
            should been wrapped by a function like ``function() { document.write("Hello World !"); }``.
        :param js_run_at: (optional) Run JavaScript specified via js_script at
            document-start or document-end. defaults to document-end.
        :param js_viewport_width: (optional) Set the size of the viewport for the JavaScript fetcher of the layout process.
        :param js_viewport_height: (optional) Set the size of the viewport for the JavaScript fetcher of the layout process.
        :param load_images: (optional) Load images when JavaScript fetcher enabled. Defaults to ``False``.
        :param validate_cert: (optional) For HTTPS requests, validate the server’s certificate? Defaults to ``True``.

        :param priority:  The bigger, the higher priority of the request.
        :type priority: int.
        :param callback: The method to parse the response.
        :param callback_args: The additional args to the callback.
        :type callback_args: list.
        :param callback_kwargs: The additional kwargs to the callback.
        :type cakkback_kwargs: dict.
        :param taskid: (optional) Unique id to identify the task. Default is the sha1 check code of the URL. But it won't be unique
            when you request the same url with different post params.
        :param crawl_at: The time to start the rquest. It must be a timestamp.
        :type crawl_at: Int or Float.
        :param crawl_later: Starts the request after ``crawl_later`` seconds.
        :param crawl_period: Schedules the request to be called periodically.
            The request is called every ``crawl_period`` seconds.
        :param crawl_rate: This should be a dict Which contain ``request_number`` and ``time_period``.
            Note that the  ``time_period`` is given in seconds. If you don't set ``time_period``, the default is 1.
            E.g.,
                {'request_number': 10,
                 'time_period': 2}
            Which means you can crawl the url at most 10 times every 2 seconds.
        :type crawl_rate: dict.
        """
        if isinstance(url, six.string_types):
            return self._crawl(url, **kwargs)

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
