# -*- coding: utf-8 -*-

import time
import logging

logger = logging.getLogger(__name__)


class Cron(object):
    """Crontab for Scheduler.

    Put timer tasks to the ready queue. And check projects
    which are marked with 'is_stopped' periodically.
    """

    curr_stopped_project = []

    @classmethod
    def is_cron(cls, task):
        is_cron = task.get('schedule', {}).get('is_cron')
        if is_cron:
            return True
        return False

    @classmethod
    def is_stopped(cls, task):
        project_name = task.get('project_name')
        if project_name in cls.curr_stopped_project:
            return True
        return False

    def __init__(self, cron_queue, ready_queue, projectdb, default_sleep_time=30):
        self.cron_queue = cron_queue
        self.ready_queue = ready_queue
        self.projectdb = projectdb
        self.default_sleep_time = default_sleep_time

    def get_stopped_projects(self):
        stoped_projects = []
        projects = self.projectdb.get_all()
        for project_name, project_data in projects.iteritems():
            if project_data.get('is_stopped'):
                stoped_projects.append(project_name)
        return stoped_projects

    def get_crawl_timestamp(self, task):
        """Get crawl timestamp from task."""
        now = self.curr_time()
        schedule = task.get('schedule', {})
        crawl_at = schedule.get('crawl_at', None)
        crawl_later = schedule.get('crawl_later', None)
        crawl_timestamp = now

        if crawl_at:
            if isinstance(crawl_at, (int, float)) and crawl_at > 0: # timestamp
                crawl_timestamp = crawl_at
            else:
                raise TypeError('crawl_at must be timestamp.')
        elif crawl_later:
            crawl_timestamp = now + crawl_later

        return crawl_timestamp

    def run(self):
        """The main method for the class."""
        while True:
            now = self.curr_time()
            Cron.curr_stopped_project = self.get_stopped_projects()

            task, crawl_timestamp = self.cron_queue.get()

            if task:
                try:
                    if not self.is_stopped(task):

                        later_time = crawl_timestamp - now
                        if later_time < self.default_sleep_time:
                            crawl_period = task.get('schedule', {}).get('crawl_period')

                            if isinstance(crawl_period, (int, float)) and crawl_period > 0:
                                # if task's 'crawl_period' is set, put it back to cron queue.
                                crawl_timestamp += crawl_period
                                self.cron_queue.put(task, crawl_timestamp)

                            later_time = max(0, later_time)

                            # Before put the task to reay queue, sleep a certain time
                            # to make it ready.
                            time.sleep(later_time)

                            self.ready_queue.put(task)
                        else:
                            self.cron_queue.put(task, crawl_timestamp)
                            time.sleep(self.default_sleep_time)
                except Exception as e:
                    logger.error(e)
            else:
                # cron queue is empty, take a nap.
                time.sleep(2)

    def put(self, task, crawl_timestamp=None):
        if not crawl_timestamp:
            craw_timestamp = self.get_crawl_timestamp(task)
        self.cron_queue.put(task, craw_timestamp)

    def curr_time(self):
        return time.time()
