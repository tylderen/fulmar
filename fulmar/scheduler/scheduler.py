# -*- coding: utf-8 -*-
import time
import threading
import logging

from cron import Cron

logger = logging.getLogger('scheduler')


class Scheduler(object):

    def __init__(self, newtask_queue, ready_queue, cron_queue, projectdb):
        self._quit = False
        self.newtask_queue = newtask_queue
        self.ready_queue = ready_queue
        self.cron = Cron(cron_queue, ready_queue, projectdb)
        self.cron_thread = threading.Thread(target=self.cron.run)
        self.cron_thread.setDaemon(True)

    def run(self):
        logger.info('scheduler starting...')
        self.run_thead(self.cron_thread)
        while not self._quit:
            try:
                task = self.newtask_queue.get()
                if task is not None:
                    logger.info('Ready task: %s' % str(task))
                    if Cron.is_stopped(task):
                        pass # just throw away the task
                    elif Cron.is_cron(task):
                        self.cron.put(task)
                    else:
                        self.ready_queue.put(task)
                else:
                    # logger.info('No ready task. Take a nap.')
                    time.sleep(0.2)
            except KeyboardInterrupt:
                logger.info('Keyboard Interrupt, bye bye.')
                self.stop()
            except Exception as e:
                logger.error(str(e))

    def run_thead(self, thread):
        try:
            thread.start()
        except RuntimeError:
            raise RuntimeError('thread is called more than once on the same thread object')

    def stop(self):
        self._quit = True