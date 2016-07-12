from requests.cookies import MockRequest
from tornado.curl_httpclient import CurlAsyncHTTPClient


def extract_cookies_to_jar(jar, request, response):
    req = MockRequest(request)
    res = MockResponse(response)
    jar.extract_cookies(res, req)


class MockResponse(object):
    def __init__(self, headers):
        self._headers = headers

    def info(self):
        return self

    def getheaders(self, name):
        """make cookie python 2 version use this method to get cookie list"""
        return self._headers.get_list(name)

    def get_all(self, name, default=[]):
        """make cookie python 3 version use this instead of getheaders"""
        return self._headers.get_list(name) or default


class MyCurlAsyncHTTPClient(CurlAsyncHTTPClient):
    def free_size(self):
        return len(self._free_list)

    def size(self):
        return len(self._curls) - self.free_size()