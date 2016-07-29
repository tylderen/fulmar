# -*- coding: utf-8 -*-
import time
import datetime
import logging

logger = logging.getLogger(__name__)


class Cron(object):

    @staticmethod
    def is_cron(task):
        is_cron = task.get('schedule', {}).get('is_cron')
        if is_cron:
            return True
        return False

    def __init__(self, cron_queue, ready_queue, default_sleep_time=60):
        self.cron_queue = cron_queue
        self.ready_queue = ready_queue
        self.default_sleep_time = default_sleep_time

    def get_crawl_timestamp(self, task):

        now = self.time()

        schedule = task.get('schedule', {})
        crawl_at = schedule.get('crawl_at', None)
        crawl_later = schedule.get('crawl_later', None)
        crawl_timestamp = now
        if crawl_at:
            if isinstance(crawl_at, dict):
                try:
                    crawl_datetime = datetime.datetime(*crawl_at)
                    crawl_timestamp = time.mktime(crawl_datetime.timetuple())
                except:
                    pass
            elif isinstance(crawl_at, (int, float)) and crawl_at > 0: # timestamp
                crawl_timestamp = crawl_at
        elif crawl_later:
            crawl_timestamp = now + crawl_later

        return crawl_timestamp

    def run(self):
        while True:
            now = self.time()

            task, crawl_timestamp = self.cron_queue.get()
            if task:
                try:
                    later_time = crawl_timestamp - now

                    if later_time < self.default_sleep_time:
                        crawl_period = task.get('schedule', {}).get('crawl_period')
                        if isinstance(crawl_period, (int, float)) and crawl_period > 0:
                            crawl_timestamp += crawl_period
                            self.cron_queue.put(task, crawl_timestamp)

                        later_time = max(0, later_time)
                        time.sleep(later_time)
                        self.ready_queue.put(task)
                    else:
                        self.cron_queue.put(task, crawl_timestamp)
                        time.sleep(self.default_sleep_time)
                except Exception as e:
                    logger.error(e)

    def put(self, task, crawl_timestamp=None):
        if not crawl_timestamp:
            craw_timestamp = self.get_crawl_timestamp(task)
        self.cron_queue.put(task, craw_timestamp)

    def time(self):
        return time.time()
