import pytest
import os
import time
import copy
import subprocess

from fulmar.worker.response import rebuild_response
from fulmar.scheduler.projectdb import Projectdb


@pytest.fixture(scope="module", autouse=True)
def http_server(request):
    import httpbin
    from fulmar.utils import run_in_subprocess
    httpbin_server = run_in_subprocess(httpbin.app.run, port=55555, passthrough_errors=False)
    def fin():
        httpbin_server.terminate()
        httpbin_server.join()
    request.addfinalizer(fin)

    return httpbin_server


@pytest.fixture(scope="module", autouse=True)
def proxy_server(request):

    proxy_process = subprocess.Popen(['pyproxy', '--username=somebody',
                                              '--password=pwd', '--port=8888',
                                              '--debug'], close_fds=True)
    def fin():
        proxy_process.terminate()
        proxy_process.wait()
    request.addfinalizer(fin)
    return proxy_process


@pytest.fixture(scope="module", autouse=True)
def phantom_server(request):
    try:
        phantomjs = subprocess.Popen(['phantomjs',
                os.path.join(os.path.dirname(__file__),
                    '../../fulmar/worker/phantomjs_fetcher.js'),
                '25555'])
    except OSError:
        phantomjs = None
    def fin():
        if phantomjs:
            phantomjs.kill()
            phantomjs.wait()
    request.addfinalizer(fin)
    return phantomjs


@pytest.fixture(scope="module")
def newtask_queue(redis_conn):
    from fulmar.message_queue.redis_queue import NewTaskQueue
    newtask_queue = NewTaskQueue(redis_conn, 'test_newtask_queue')
    newtask_queue.clear()
    return newtask_queue


@pytest.fixture(scope="module")
def projectdb(redis_conn):
    projectdb = Projectdb(redis_conn, 'test_projectdb')
    return projectdb


@pytest.fixture(scope="module")
def requestor(newtask_queue, projectdb):
    from fulmar.worker.requestor import Requestor
    requestor = Requestor(newtask_queue=newtask_queue, projectdb=projectdb)
    requestor.phantomjs_proxy = '127.0.0.1:25555'

    return requestor


class TestRequestor:
    proxy_host = '127.0.0.1'
    proxy_port = 8888
    proxy_username = 'somebody'
    proxy_password = 'pwd'
    default_task = {
        'project_name': 'test_project_name',
        'project_id': 'test_project_id',
        'taskid': 'test_taskid',
        'url': 'http://127.0.0.1:55555',
        'fetch': {
            'method': 'GET',
            'headers': {
                'Cookie': 'a=b',
                'a': 'b'
            },
            'cookies': {
                'c': 'd',
            },
            'timeout': 60,
        },
        'process': {
            'callback': None,
        },
        'schedule': {},
    }

    def test_http_get(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/get'
        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.ok == True
        assert response.status_code == 200
        assert response.url == task['url']
        assert hasattr(response, 'headers')
        assert len(response.content) > 0
        assert isinstance(response.time_cost, (int, float))
        assert response.cookies == {'c': 'd'}
        assert response.json['headers']['A'] == 'b'
        assert response.json['headers']['Cookie'] == 'a=b'

    def test_http_post(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/post'
        task['fetch']['method'] = 'POST'
        task['fetch']['data'] = 'Hello World'
        task['fetch']['cookies'] = {'c': 'd'}
        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 200
        assert response.orig_url == task['url']
        assert response.json['form']['Hello World'] == ''
        assert response.json['headers'].get('A') == 'b'

    def test_fake_request(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = 'first_task: test_project'
        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.json == None

    def test_http_timeout(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/delay/4'
        task['fetch']['timeout'] = 2
        start_time = time.time()
        result = requestor.sync_request(task)
        end_time = time.time()
        response = rebuild_response(result)
        time_cost = end_time - start_time

        assert time_cost >= 2
        assert time_cost < 3
        assert response.content == ''
        assert response.status_code == 599
        assert 'HTTP 599: Operation timed out' in response.error

    def test_http_status_555(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/status/555'
        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 555

    def test_http_no_redirect(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/redirect/4'
        task['fetch']['allow_redirects'] = False

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.error == 'HTTP 302: FOUND'

    def test_http_max_redirect(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/redirect/4'
        task['fetch']['max_redirects'] = 3

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.error == 'HTTP 599: Maximum (3) redirects followed'

        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/redirect/4'
        task['fetch']['max_redirects'] = 5

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 200

    def test_http_proxy_auth_failed(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/get'
        task['fetch']['proxy_host'] = self.proxy_host
        task['fetch']['proxy_port'] = self.proxy_port

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 403

    def test_http_proxy_auth_ok(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/get'
        task['fetch']['proxy_host'] = self.proxy_host
        task['fetch']['proxy_port'] = self.proxy_port
        task['fetch']['proxy_username'] = self.proxy_username
        task['fetch']['proxy_password'] = self.proxy_password

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 200

    def test__phantomjs_url(self, requestor):
        task = copy.deepcopy(self.default_task)
        task['url'] = task['url'] + '/status/200'
        task['fetch']['fetch_type'] = 'js'

        result = requestor.sync_request(task)
        response = rebuild_response(result)

        assert response.status_code == 200
        assert response.error == None
        assert response.isok() == True
        assert response.js_script_result == None
