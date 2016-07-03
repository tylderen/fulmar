# -*- coding: utf-8 -*-
import time
import logging

logger = logging.getLogger('scheduler')


class Scheduler(object):
    def __init__(self, newtask_queue, ready_queue):
        self._quit = False
        self.newtask_queue = newtask_queue
        self.ready_queue = ready_queue

    def run(self):
        logger.info('scheduler starting...')
        while not self._quit:
            try:
                task = self.newtask_queue.pop()
                if task is not None:
                    logger.info('Ready task: %s' % str(task))
                    self.ready_queue.push(task)
                else:
                    # logger.info('No ready task.')
                    time.sleep(0.2)
            except Exception as e:
                logger.error(str(e))