# -*- encoding: utf-8 -*-
from __future__ import unicode_literals

import copy
import json
import time
import logging
import functools
import threading

import six
import tornado.httpclient
import tornado.httputil
import tornado.ioloop

from tornado import gen
from requests import cookies
from result_handler import Processor
from six.moves.urllib.parse import urljoin, urlsplit

from ..utils import unicode_text
from .http_utils import extract_cookies_to_jar
from .http_utils import MyCurlAsyncHTTPClient

logger = logging.getLogger('requestor')


class Requestor(object):
    default_options = {
        'method': 'GET',
        'headers': {},
        'timeout': 120,
    }
    phantomjs_proxy = None

    def __init__(self, poolsize=300, timeout=120,
                 proxy=None, async=True,
                 user_agent=None, ioloop=None,
                 newtask_queue=None, resultdb=None,
                 projectdb=None):
        self.poolsize = poolsize
        self.timeout = timeout
        self.proxy = proxy
        self.async = async
        self.processor = Processor(newtask_queue, resultdb, projectdb)
        if not user_agent:
            self.user_agent = "fulmar/%s" % 'fulmar.__version__'

        if ioloop == None:
            self.ioloop = tornado.ioloop.IOLoop()
        else:
            self.ioloop = ioloop
        # Bind io_loop to http_client
        if self.async:
            self.http_client = MyCurlAsyncHTTPClient(max_clients=self.poolsize, io_loop=self.ioloop)
        else:
            self.http_client = tornado.httpclient.HTTPClient(MyCurlAsyncHTTPClient, max_clients=self.poolsize)

        self._follows = []

    def add_follows(self, tasks):
        """Collect new generated tasks"""
        if not isinstance(tasks, list):
            tasks = [tasks]
        self._follows.extend(tasks)

    def _put_follows(self):
        """Put new generated tasks to newtask_queue"""
        if self._follows:
            self.processor.put_tasks(self._follows)
        self._follows = []

    def request(self, task=None):
        """Request a new task"""
        callback = task.get('process', {}).get('callback')
        if callback is None:
            raise Exception('No callback found !')

        if self.async:
            result = self._async_request(task)
        else:
            result = self._async_request(task, callback).result()
        return result

    @gen.coroutine
    def _async_request(self, task):
        url = task.get('url')
        if url.startswith('first_task'):
            result = yield gen.maybe_future(self._fake_request(url, task))
        else:
            try:
                if task.get('fetch', {}).get('fetch_type') in ('js', 'phantomjs'):
                    result = yield self._phantomjs_request(url, task)
                else:
                    result = yield self._http_request(url, task)
            except Exception as e:
                logger.exception(e)

        if task.get('process', {}).get('callback'):
            task, results, follows, db_name, coll_name = self.processor.handle_result(task, result)

            if follows:
                # put new tasks to newtask_queue
                self.add_follows(follows)
                self._put_follows()

            if results:
                self.processor.put_results(results, db_name, coll_name, task)

        raise gen.Return(result)

    def sync_request(self, task):
        """
            Synchronization request.
            Now, it's only for testing.
        """
        return self.ioloop.run_sync(functools.partial(self._async_request, task))

    def _handle_error(self, url, task, start_time, error):
        result = {
            'status_code': getattr(error, 'code', 599),
            'error': unicode_text(error),
            'content': "",
            'time_cost': time.time() - start_time,
            'orig_url': url,
            'url': url,
        }
        logger.error("[%d] %s:%s %s, %r %.2fs",
                     result['status_code'], task.get('project'), task.get('taskid'),
                     url, error, result['time_cost'])
        return result

    allowed_options = ['method', 'data', 'timeout', 'cookies', 'validate_cert']

    def _pack_tornado_request_parameters(self, url, task):
        fetch = copy.deepcopy(self.default_options)
        fetch['url'] = url
        fetch['headers'] = tornado.httputil.HTTPHeaders(fetch['headers'])
        fetch['headers']['User-Agent'] = task.get('user_agent') or self.user_agent

        task_fetch = task.get('fetch', {})
        for each in self.allowed_options:
            if each in task_fetch:
                fetch[each] = task_fetch[each]
        fetch['headers'].update(task_fetch.get('headers', {}))

        # Proxy setting
        if isinstance(task_fetch.get('proxy_host'), six.string_types):
            fetch['proxy_host'] = task_fetch['proxy_host']
            if isinstance(task_fetch.get('proxy_port'), six.integer_types):
                fetch['proxy_port'] = task_fetch['proxy_port']
            if isinstance(task_fetch.get('proxy_username'), six.string_types):
                fetch['proxy_username'] = task_fetch['proxy_username']
            if isinstance(task_fetch.get('proxy_password'), six.string_types):
                fetch['proxy_password'] = task_fetch['proxy_password']

        # Timeout
        if 'timeout' in fetch:
            fetch['connect_timeout'] = fetch['request_timeout'] = fetch['timeout']
            del fetch['timeout']

        # Rename data to body
        if 'data' in fetch:
            fetch['body'] = fetch['data']
            del fetch['data']

        return fetch

    @gen.coroutine
    def _http_request(self, url, task):
        start_time = time.time()

        handle_error = lambda x: self._handle_error(url, task, start_time, x)

        # setup request parameters
        fetch = self._pack_tornado_request_parameters(url, task)
        task_fetch = task.get('fetch', {})
        session = cookies.RequestsCookieJar()
        if 'cookies' in fetch:
            session.update(fetch['cookies'])
            del fetch['cookies']

        allow_redirects = task_fetch.get('allow_redirects', True)
        max_redirects = task_fetch.get('max_redirects', 5)

        fetch['follow_redirects'] = False

        # Make request
        while True:
            try:
                request = tornado.httpclient.HTTPRequest(**fetch)
                cookie_header = cookies.get_cookie_header(session, request)
                if cookie_header:
                    request.headers['Cookie'] = cookie_header
            except Exception as e:
                logger.exception(e)
                raise gen.Return(handle_error(e))

            try:
                response = yield gen.maybe_future(self.http_client.fetch(request))
            except tornado.httpclient.HTTPError as e:
                if e.response:
                    response = e.response
                else:
                    raise gen.Return(handle_error(e))

            extract_cookies_to_jar(session, response.request, response.headers)
            if 200 <= response.code < 300:
                logger.info("[%d] %s:%s %s ", response.code,
                            task.get('project_name'), task.get('taskid'),
                            url)
            # Redirect
            elif (response.code in (301, 302, 303, 307)
                    and response.headers.get('Location')
                    and allow_redirects):
                if max_redirects <= 0:
                    error = tornado.httpclient.HTTPError(
                        599, 'Maximum (%d) redirects followed' % task_fetch.get('max_redirects', 5),
                        response)
                    raise gen.Return(handle_error(error))
                if response.code in (302, 303):
                    fetch['method'] = 'GET'
                    if 'body' in fetch:
                        del fetch['body']
                fetch['url'] = urljoin(fetch['url'], response.headers['Location'])
                max_redirects -= 1
                continue
            else:
                logger.error("[%d] %s:%s %s ", response.code,
                               task.get('project_name'), task.get('taskid'),
                               url)

            result = {}
            result['orig_url'] = url
            result['content'] = response.body or ''
            result['headers'] = dict(response.headers)
            result['status_code'] = response.code
            result['url'] = response.effective_url or url
            result['cookies'] = session.get_dict()
            result['time_cost'] = time.time() - start_time
            if response.error:
                result['error'] = unicode_text(response.error)

            raise gen.Return(result)

    @gen.coroutine
    def _phantomjs_request(self, url, task):
        """Fetch with phantomjs proxy"""
        start_time = time.time()

        handle_error = lambda x: self._handle_error('phantomjs', url, task, start_time, x)

        # check phantomjs proxy is enabled
        if not self.phantomjs_proxy:
            result = {
                "orig_url": url,
                "content": "phantomjs is not enabled.",
                "headers": {},
                "status_code": 501,
                "url": url,
                "cookies": {},
                "time_cost": 0,
            }
            logger.warning("[501] %s:%s %s 0s", task.get('project'), task.get('taskid'), url)
            raise gen.Return(result)

        # setup request parameters
        fetch = self._pack_tornado_request_parameters(url, task)
        task_fetch = task.get('fetch', {})
        for each in task_fetch:
            if each not in fetch:
                fetch[each] = task_fetch[each]

        request_conf = {
            'follow_redirects': False
        }
        request_conf['connect_timeout'] = fetch.get('connect_timeout', self.timeout)
        request_conf['request_timeout'] = fetch.get('request_timeout', self.timeout)

        session = cookies.RequestsCookieJar()
        request = tornado.httpclient.HTTPRequest(url=fetch['url'])
        if fetch.get('cookies'):
            session.update(fetch['cookies'])
            if 'Cookie' in request.headers:
                del request.headers['Cookie']
            fetch['headers']['Cookie'] = cookies.get_cookie_header(session, request)

        # Make request
        fetch['headers'] = dict(fetch['headers'])
        try:
            request = tornado.httpclient.HTTPRequest(
                url="%s" % self.phantomjs_proxy, method="POST",
                body=json.dumps(fetch), **request_conf)
        except Exception as e:
            raise gen.Return(handle_error(e))

        try:
            response = yield gen.maybe_future(self.http_client.fetch(request))
        except tornado.httpclient.HTTPError as e:
            if e.response:
                response = e.response
            else:
                raise gen.Return(handle_error(e))

        if not response.body:
            raise gen.Return(handle_error(Exception('no response from phantomjs')))

        try:
            result = json.loads(unicode_text(response.body))
        except Exception as e:
            if response.error:
                result['error'] = unicode_text(response.error)
            raise gen.Return(handle_error(e))

        if result.get('status_code', 200):
            logger.info("[%d] %s:%s %s %.2fs", result['status_code'],
                        task.get('project'), task.get('taskid'), url, result['time_cost'])
        else:
            logger.error("[%d] %s:%s %s, %r %.2fs", result['status_code'],
                         task.get('project'), task.get('taskid'),
                         url, result['content'], result['time_cost'])

        raise gen.Return(result)

    def _fake_request(self, url, task):
        """A fake request for the first task in project"""
        result = {}
        result['orig_url'] = url
        result['content'] = ''
        result['headers'] = {}
        result['status_code'] = 200
        result['url'] = url
        result['cookies'] = {}
        result['time_cost'] = 0
        logger.info("[200] %s:%s %s 0s", task.get('project_name'), task.get('taskid'), url)

        return result

    def free_size(self):
        return self.http_client.free_size()