# -*- encoding: utf-8 -*-
from __future__ import unicode_literals

import logging

import tornado.httpclient
import tornado.httputil
import tornado.ioloop

from .requestor import Requestor
from ..utils import lua_rate_limit

logger = logging.getLogger('worker')


class Worker(object):
    default_options = {
        'method': 'GET',
        'headers': {},
        'timeout': 120,
    }
    phantomjs_proxy = None

    def __init__(self, readytask_queue, newtask_queue,
                 projectdb, poolsize=300, timeout=120,
                 proxy=None, async=True, user_agent=None):
        self.readytask_queue = readytask_queue
        self.ioloop = tornado.ioloop.IOLoop()

        self.requestor = Requestor(poolsize=poolsize, timeout=timeout,
                                   proxy=proxy, async=async,
                                   user_agent=user_agent, ioloop=self.ioloop,
                                   newtask_queue=newtask_queue, projectdb=projectdb)

        self._running = False
        self._quit = False

    def run(self):
        """Run ioloop"""
        logger.info("worker starting...")

        def queue_loop():

            if not self.readytask_queue:
                logger.error('No readytask_queue provided!')

            while not self._quit:
                try:
                    if self.requestor.free_size() <= 0:
                        logger.warning('Too many requests is running!')
                        break
                    task = self.readytask_queue.pop()
                    if task:
                        crawl_rate = task.get('crawl_rate')

                        if crawl_rate: # Crawl rate is setted.
                            key_name = crawl_rate.get('key_name')
                            request_number = crawl_rate.get('request_number')
                            time_period = crawl_rate.get('time_period')
                            if lua_rate_limit(keys=[key_name], args=[time_period, request_number]):
                                # Request too fast, push the task back to newtask_queue.
                                # push_job(tasks=[task])
                                self.requestor.add_follows(task)
                                break
                        result = self.requestor.request(task)
                    break
                except Exception as e:
                    logger.exception(e)
                    break
        tornado.ioloop.PeriodicCallback(queue_loop, 100, io_loop=self.ioloop).start()
        self._running = True
        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            logger.info('KeyboardInterrupt. Bye bye.')

        logger.info("worker exiting...")

    def quit(self):
        """Quit worker"""
        self._running = False
        self._quit = True
        self.ioloop.stop()
