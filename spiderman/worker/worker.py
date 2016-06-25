# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import copy
import functools
import json
import logging
import threading
import time

import six
import tornado.httpclient
import tornado.httputil
import tornado.ioloop

from requests import cookies
from six.moves import queue, http_cookies
from six.moves.urllib.parse import urljoin, urlsplit
from tornado import gen

from ..utils import unicode_text

from .http_utils import extract_cookies_to_jar
from .http_utils import MyCurlAsyncHTTPClient
from .result_handler import Processor

logger = logging.getLogger('worker')


fetcher_output = {
    "status_code": int,
    "orig_url": str,
    "url": str,
    "headers": dict,
    "content": str,
    "cookies": dict,
}

class Worker(object):
    default_options = {
        'method': 'GET',
        'headers': {},
        'timeout': 120,
    }
    phantomjs_proxy = None

    def __init__(self, readytask_queue, newtask_queue, projectdb, poolsize=200, timeout=None,
                 proxy=None, async=True, user_agent=None):
        self.readytask_queue = readytask_queue
        self.processor = Processor(newtask_queue, projectdb)
        self.poolsize = poolsize
        self.proxy = proxy
        self.async = async
        self.ioloop = tornado.ioloop.IOLoop()

        self._running = False
        self._quit = False

        if not user_agent:
            self.user_agent = "spiderman/%s" % 'spiderman.__version__'

        # binding io_loop to http_client here
        if self.async:
            self.http_client = MyCurlAsyncHTTPClient(max_clients=self.poolsize, io_loop=self.ioloop)
        else:
            self.http_client = tornado.httpclient.HTTPClient(MyCurlAsyncHTTPClient, max_clients=self.poolsize)

    def fetch(self, task):
        callback = task.get('process', {}).get('callback')
        if callback is None:
            raise Exception('No callback found !')

        if self.async:
            result = self.async_fetch(task)
        else:
            result = self.async_fetch(task, callback).result()
            self.processor.handle_result(task, result)
        return result


    @gen.coroutine
    def async_fetch(self, task):
        '''Do one fetch'''
        url = task.get('url')
        if url.startswith('first_task'):
            result = yield gen.maybe_future(self.data_fetch(url, task))
        else:
            try:
                if task.get('fetch', {}).get('fetch_type') in ('js', 'phantomjs'):
                    result = yield self.phantomjs_fetch(url, task)
                else:
                    result = yield self.http_fetch(url, task)
            except Exception as e:
                logger.exception(e)

        self.processor.handle_result(task, result)
        raise gen.Return(result)

    def sync_fetch(self, task):
        '''Synchronization fetch, usually used in xmlrpc thread'''
        if not self._running:
            return self.ioloop.run_sync(functools.partial(self.async_fetch, task, lambda t, _, r: True))

        wait_result = threading.Condition()
        _result = {}

        def callback(type, task, result):
            wait_result.acquire()
            _result['type'] = type
            _result['task'] = task
            _result['result'] = result
            wait_result.notify()
            wait_result.release()

        wait_result.acquire()
        self.ioloop.add_callback(self.fetch, task, callback)
        while 'result' not in _result:
            wait_result.wait()
        wait_result.release()
        return _result['result']

    def handle_error(self, type, url, task, start_time, error):
        result = {
            'status_code': getattr(error, 'code', 599),
            'error': unicode_text(error),
            'content': "",
            'time': time.time() - start_time,
            'orig_url': url,
            'url': url,
        }
        logger.error("[%d] %s:%s %s, %r %.2fs",
                     result['status_code'], task.get('project'), task.get('taskid'),
                     url, error, result['time'])
        self.on_result(type, task, result)
        return result

    allowed_options = ['method', 'data', 'timeout', 'cookies', 'validate_cert']

    def pack_tornado_request_parameters(self, url, task):
        # default optionstyl

        fetch = copy.deepcopy(self.default_options)
        fetch['url'] = url

        # only init {}
        fetch['headers'] = tornado.httputil.HTTPHeaders(fetch['headers'])

        fetch['headers']['User-Agent'] = task.get('user_agent') or self.user_agent

        task_fetch = task.get('fetch', {})
        for each in self.allowed_options:
            if each in task_fetch:
                fetch[each] = task_fetch[each]
        fetch['headers'].update(task_fetch.get('headers', {}))

        # UNDO: proxy
        proxy_string = None
        if isinstance(task_fetch.get('proxy'), six.string_types):
            proxy_string = task_fetch['proxy']
        elif self.proxy and task_fetch.get('proxy', True):
            proxy_string = self.proxy
        if proxy_string:
            if '://' not in proxy_string:
                proxy_string = 'http://' + proxy_string
            proxy_splited = urlsplit(proxy_string)
            if proxy_splited.username:
                fetch['proxy_username'] = proxy_splited.username
                if six.PY2:
                    fetch['proxy_username'] = fetch['proxy_username'].encode('utf8')
            if proxy_splited.password:
                fetch['proxy_password'] = proxy_splited.password
                if six.PY2:
                    fetch['proxy_password'] = fetch['proxy_password'].encode('utf8')
            fetch['proxy_host'] = proxy_splited.hostname.encode('utf8')
            if six.PY2:
                fetch['proxy_host'] = fetch['proxy_host'].encode('utf8')
            fetch['proxy_port'] = proxy_splited.port or 8080

        # timeout
        if 'timeout' in fetch:
            # 这里需要看一下???
            fetch['connect_timeout'] = fetch['request_timeout'] = fetch['timeout']
            del fetch['timeout']

        # data rename to body
        if 'data' in fetch:
            fetch['body'] = fetch['data']
            del fetch['data']

        return fetch


    @gen.coroutine
    def http_fetch(self, url, task):
        start_time = time.time()

        handle_error = lambda x: self.handle_error('http', url, task, start_time, x)

        # setup request parameters
        fetch = self.pack_tornado_request_parameters(url, task)
        task_fetch = task.get('fetch', {})

        session = cookies.RequestsCookieJar()

        if 'cookies' in fetch:
            session.update(fetch['cookies'])
            del fetch['cookies']

        max_redirects = task_fetch.get('max_redirects', 5)
        # we will handle redirects by hand to capture cookies
        fetch['follow_redirects'] = False

        # making requests
        while True:
            try:
                request = tornado.httpclient.HTTPRequest(**fetch)
                # 这里把cookie整合到了request里面, cookie来自于fetch自带的; 合理
                cookie_header = cookies.get_cookie_header(session, request)
                if cookie_header:
                    request.headers['Cookie'] = cookie_header
            except Exception as e:
                logger.exception(fetch)
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
                            task.get('project'), task.get('taskid'),
                            url)
            # redirect
            elif (response.code in (301, 302, 303, 307)
                    and response.headers.get('Location')
                    and task_fetch.get('allow_redirects', True)):
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
                '''
                # maybe not make sense
                fetch['request_timeout'] -= time.time() - start_time
                if fetch['request_timeout'] < 0:
                    fetch['request_timeout'] = 0.1
                fetch['connect_timeout'] = fetch['request_timeout']
                '''
                max_redirects -= 1
                continue
            else:
                logger.warning("[%d] %s:%s %s %.2fs", response.code,
                               task.get('project'), task.get('taskid'),
                               url, result['time_cost'])

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
    def phantomjs_fetch(self, url, task, callback):
        '''Fetch with phantomjs proxy'''
        start_time = time.time()

        self.on_fetch('phantomjs', task)
        handle_error = lambda x: self.handle_error('phantomjs', url, task, start_time, x)

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
        fetch = self.pack_tornado_request_parameters(url, task)
        task_fetch = task.get('fetch', {})
        for each in task_fetch:
            if each not in fetch:
                fetch[each] = task_fetch[each]

        request_conf = {
            'follow_redirects': False
        }
        request_conf['connect_timeout'] = fetch.get('connect_timeout', 120)
        request_conf['request_timeout'] = fetch.get('request_timeout', 120)

        session = cookies.RequestsCookieJar()
        request = tornado.httpclient.HTTPRequest(url=fetch['url'])
        if fetch.get('cookies'):
            session.update(fetch['cookies'])
            if 'Cookie' in request.headers:
                del request.headers['Cookie']
            fetch['headers']['Cookie'] = cookies.get_cookie_header(session, request)

        # making requests
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
                        task.get('project'), task.get('taskid'), url, result['time'])
        else:
            logger.error("[%d] %s:%s %s, %r %.2fs", result['status_code'],
                         task.get('project'), task.get('taskid'),
                         url, result['content'], result['time'])

        raise gen.Return(result)

    def data_fetch(self, url, task):
        '''A fake fetcher for dataurl'''
        result = {}
        result['orig_url'] = url
        result['content'] = ''
        result['headers'] = {}
        result['status_code'] = 200
        result['url'] = url
        result['cookies'] = {}
        result['time_cost'] = 0
        logger.info("[200] %s:%s %s 0s", task.get('project'), task.get('taskid'), url)

        return result

    def run(self):
        '''Run loop'''
        logger.info("worker starting...")

        def queue_loop():
            if not self.readytask_queue:
                return
            while not self._quit:
                try:
                    # ioloop 有并发请求限制
                    if self.http_client.free_size() <= 0:
                        break
                    task = self.readytask_queue.pop()
                    #task = {'url': 'https://www.baidu.com/', 'callback': '123'}
                    # task in dict
                    # task = unpack(task)
                    result = self.fetch(task)
                    self._quit = True
                except queue.Empty:
                    break
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.exception(e)
                    break
        tornado.ioloop.PeriodicCallback(queue_loop, 1000, io_loop=self.ioloop).start()
        self._running = True
        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            pass

        logger.info("worker exiting...")

    def quit(self):
        '''Quit worker'''
        self._running = False
        self._quit = True
        self.ioloop.stop()

    def size(self):
        return self.http_client.size()

    def xmlrpc_run(self, port=24444, bind='127.0.0.1', logRequests=False):
        '''Run xmlrpc server'''
        import umsgpack
        try:
            from xmlrpc.server import SimpleXMLRPCServer
            from xmlrpc.client import Binary
        except ImportError:
            from SimpleXMLRPCServer import SimpleXMLRPCServer
            from xmlrpclib import Binary

        server = SimpleXMLRPCServer((bind, port), allow_none=True, logRequests=logRequests)
        server.register_introspection_functions()
        server.register_multicall_functions()

        server.register_function(self.quit, '_quit')
        server.register_function(self.size)

        def sync_fetch(task):
            result = self.sync_fetch(task)
            result = Binary(umsgpack.packb(result))
            return result
        server.register_function(sync_fetch, 'fetch')

        def dump_counter(_time, _type):
            return self._cnt[_time].to_dict(_type)
        server.register_function(dump_counter, 'counter')

        server.timeout = 0.5
        while not self._quit:
            server.handle_request()
        server.server_close()