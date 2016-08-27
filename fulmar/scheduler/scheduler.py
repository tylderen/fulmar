# -*- coding: utf-8 -*-

import logging
import time
import threading

from cron import Cron

logger = logging.getLogger(__name__)


class Scheduler(object):
    """Scheduler for fulmar.

    Only one Scheduler should be running in fulmar.
    It schedules all of the tasks, puts tasks from newtask queue and
    cron queue to ready queue.
    And it throw away tasks whose project is marked with 'is_stopped'.
    """

    def __init__(self, newtask_queue, ready_queue, cron_queue, projectdb):
        self._quit = False
        self.newtask_queue = newtask_queue
        self.ready_queue = ready_queue
        self.cron = Cron(cron_queue, ready_queue, projectdb)

    def run(self):
        logger.info('scheduler starting...')

        self.run_cron()

        while not self._quit:
            try:
                task = self.newtask_queue.get()
                if task is not None:
                    logger.info('Need handle task: %s' % str(task))

                    if Cron.is_cron(task):
                        self.cron.put(task)
                    elif Cron.is_stopped(task):
                        pass
                    else:
                        self.ready_queue.put(task)
                else:
                    # No ready task, take a nap.
                    time.sleep(0.2)
            except KeyboardInterrupt:
                logger.info('Keyboard Interrupt, bye bye.')
                self.stop()
            except Exception as e:
                logger.error(str(e))

    def run_cron(self):
        try:
            self.cron_thread = threading.Thread(target=self.cron.run)
            self.cron_thread.setDaemon(True)
            self.cron_thread.start()
        except RuntimeError:
            raise RuntimeError('Thread is called more than once on the same thread object')

    def stop(self):
        self._quit = True