# -*- encoding: utf-8 -*-
from __future__ import unicode_literals
import logging
import tornado.httpclient
import tornado.httputil
import tornado.ioloop

from .requestor import Requestor

try:
    from ..utils import lua_rate_limit
except ImportError:
    from ..message_queue import redis_conn
    from ..utils import LUA_RATE_LIMIT_SCRIPT
    lua_rate_limit = redis_conn.register_script(LUA_RATE_LIMIT_SCRIPT)

logger = logging.getLogger('worker')


class Worker(object):
    default_options = {
        'method': 'GET',
        'headers': {},
        'timeout': 180,
    }
    phantomjs_proxy = None

    def __init__(self, readytask_queue, newtask_queue,
                 resultdb, projectdb, poolsize=300,
                 timeout=180, proxy=None, async=True,
                 user_agent=None):
        self.readytask_queue = readytask_queue
        self.ioloop = tornado.ioloop.IOLoop()

        self.requestor = Requestor(poolsize=poolsize, timeout=timeout,
                                   proxy=proxy, async=async,
                                   user_agent=user_agent, ioloop=self.ioloop,
                                   newtask_queue=newtask_queue, resultdb=resultdb,
                                   projectdb=projectdb)

    def run(self):
        """Run ioloop"""
        logger.info("worker starting...")

        def queue_loop():
            if not self.readytask_queue:
                logger.error('No readytask_queue provided!')

            try:
                if self.requestor.free_size() <= 0:
                    logger.warning('Too many requests is running!')
                    return
                task = self.readytask_queue.get()
                if task:
                    crawl_rate = task.get('crawl_rate')
                    if crawl_rate:
                        limit_level = crawl_rate.get('limit_level')
                        request_number = crawl_rate.get('request_number')
                        time_period = crawl_rate.get('time_period')
                        if lua_rate_limit(keys=[limit_level], args=[time_period, request_number]):
                            # Request too fast, put the task back to newtask_queue.
                            self.requestor.add_follows(task)
                    result = self.requestor.request(task)
            except Exception as e:
                logger.exception(e)

        tornado.ioloop.PeriodicCallback(queue_loop, 50, io_loop=self.ioloop).start()

        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            logger.info('KeyboardInterrupt. Bye bye.')
        finally:
            self.stop()

        logger.info("worker exiting...")

    def stop(self):
        """Quit worker"""
        self.ioloop.stop()
