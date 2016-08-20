# -*- coding: utf-8 -*-
import os
import six
import redis
import logging
import hashlib
import yaml
import json
from functools import partial

from six.moves.urllib.parse import urlparse, urlunparse
from pymongo import MongoClient
from requests.models import RequestEncodingMixin

encode_params = RequestEncodingMixin._encode_params
json_dumps = partial(json.dumps, ensure_ascii=False, sort_keys=True)


LUA_RATE_LIMIT_SCRIPT = """
    local current_requests = redis.call('get', KEYS[1])
    if not current_requests then
        redis.call('incr', KEYS[1])
        redis.call('expire', KEYS[1], ARGV[1])
        return 0
    end
    if tonumber(current_requests) >= tonumber(ARGV[2]) then
        return 1
    end
    redis.call('incr', KEYS[1])
    return 0
    """


# lua_rate_limit = redis_conn.register_script(LUA_RATE_LIMIT_SCRIPT)


def build_url(url, _params):
    """Build the actual URL to use."""

    # Support for unicode domain names and paths.
    scheme, netloc, path, params, query, fragment = urlparse(url)
    netloc = netloc.encode('idna').decode('utf-8')
    if not path:
        path = '/'

    if six.PY2:
        if isinstance(scheme, six.text_type):
            scheme = scheme.encode('utf-8')
        if isinstance(netloc, six.text_type):
            netloc = netloc.encode('utf-8')
        if isinstance(path, six.text_type):
            path = path.encode('utf-8')
        if isinstance(params, six.text_type):
            params = params.encode('utf-8')
        if isinstance(query, six.text_type):
            query = query.encode('utf-8')
        if isinstance(fragment, six.text_type):
            fragment = fragment.encode('utf-8')

    enc_params = encode_params(_params)
    if enc_params:
        if query:
            query = '%s&%s' % (query, enc_params)
        else:
            query = enc_params
    url = (urlunparse([scheme, netloc, path, params, query, fragment]))
    return url


def connect_mongodb(url=None):
    if url is None:
        return

    parsed = urlparse(url)
    if parsed.scheme != 'mongodb':
        raise Exception('Please use MongoDB URI format, e.g., "mongodb://localhost:27017/".')

    return MongoClient(url, connect=False)


def connect_redis(url=None):
    if url is None:
        url = 'redis://127.0.0.1:6379/0'

    parsed = urlparse(url)
    if parsed.scheme != 'redis':
        raise Exception('Please use Redis URI format, e.g., "redis://localhost:6379/0".')

    db = parsed.path.lstrip('/').split('/')
    try:
        db = int(db[0])
    except:
        db = 0
    host = parsed.hostname
    port = parsed.port
    password = parsed.password or None
    return redis.StrictRedis(host=host,
                             port=port,
                             db=db,
                             password=password)


def sha1string(string):
    return hashlib.sha1(utf8(string)).hexdigest()


def read_cfg():
    cfg = {}
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(cfg_path, 'r') as f:
            cfg = yaml.load(f)
    except IOError as e:
        err = 'No default configuration file find !'
        logging.debug(err)


def unicode_text(string, encoding='utf8'):
    """
    Make sure string is unicode type, decode with given encoding if it's not.

    If parameter is a object, object.__str__ will been called.
    """
    if isinstance(string, six.text_type):
        return string
    elif isinstance(string, six.binary_type):
        return string.decode(encoding)
    else:
        return six.text_type(string)


def pretty_unicode(string):
    """
    Make sure string is unicode, try to decode with utf8, or unicode escaped string if failed.
    """
    if isinstance(string, six.text_type):
        return string
    try:
        return string.decode("utf8")
    except UnicodeDecodeError:
        return string.decode('Latin-1').encode('unicode_escape').decode("utf8")


def quote_chinese(url, encodeing="utf-8"):
    """Quote non-ascii characters"""
    if isinstance(url, six.text_type):
        return quote_chinese(url.encode(encodeing))
    if six.PY3:
        res = [six.int2byte(b).decode('latin-1') if b < 128 else '%%%02X' % b for b in url]
    else:
        res = [b if ord(b) < 128 else '%%%02X' % ord(b) for b in url]
    return "".join(res)


def utf8(string):
    """
    Make sure string is utf8 encoded bytes.

    If parameter is a object, object.__str__ will been called before encode as bytes
    """
    if isinstance(string, six.text_type):
        return string.encode('utf8')
    elif isinstance(string, six.binary_type):
        return string
    else:
        return six.text_type(string).encode('utf8')


class ObjectDict(dict):
    """
    Object like dict, every dict[key] can visite by dict.key

    If dict[key] is `Get`, calculate it's value.
    """

    def __getattr__(self, name):
        ret = self.__getitem__(name)
        if hasattr(ret, '__get__'):
            return ret.__get__(self, ObjectDict)
        return ret

def load_object(name):
    """Load object from module"""

    if "." not in name:
        raise Exception('load object need module.object')

    module_name, object_name = name.rsplit('.', 1)
    if six.PY2:
        module = __import__(module_name, globals(), locals(), [utf8(object_name)], -1)
    else:
        module = __import__(module_name, globals(), locals(), [object_name])
    return getattr(module, object_name)


def run_in_thread(func, *args, **kwargs):
    """Run function in thread, return a Thread object"""
    from threading import Thread
    thread = Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


def run_in_subprocess(func, *args, **kwargs):
    """Run function in subprocess, return a Process object"""
    from multiprocessing import Process
    thread = Process(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


def encode_multipart_formdata(fields, files):
    body, content_type = RequestEncodingMixin._encode_files(files, fields)
    return content_type, body


def quote_chinese(url, encodeing="utf-8"):
    """Quote non-ascii characters"""
    if isinstance(url, six.text_type):
        return quote_chinese(url.encode(encodeing))
    if six.PY3:
        res = [six.int2byte(b).decode('latin-1') if b < 128 else '%%%02X' % b for b in url]
    else:
        res = [b if ord(b) < 128 else '%%%02X' % ord(b) for b in url]
    return "".join(res)