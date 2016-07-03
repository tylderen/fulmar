# -*- encoding: utf-8 -*-
import logging
import time
logger = logging.getLogger(__name__)

from .response import rebuild_response
from .project_manager import ProjectManager


class Processor(object):
    PROCESS_TIME_LIMIT = 30
    EXCEPTION_LIMIT = 3

    def __init__(self, newtask_queue, projectdb, enable_stdout_capture=True):
        self.newtask_queue = newtask_queue
        self.enable_stdout_capture = enable_stdout_capture
        self.project_manager = ProjectManager(projectdb, dict(
            enable_stdout_capture=self.enable_stdout_capture,
        ))

    def handle_result(self, task, result):
        '''Deal one result'''
        start_time = time.time()
        response = rebuild_response(result)
        try:
            assert 'taskid' in task, 'need taskid in task'
            project_name = task['project_name']
            project_id = task['project_id']

            project_data = self.project_manager.get(project_name, project_id)
            assert project_data, "No such project!"

            if project_data.get('exception'):
                logger.error(project_data.get('exception_log'))
            else:
                logger.info('Sccceed in getting project data')
                ret = project_data['instance'].run_task(
                    project_data['module'], task, response)
        except Exception as e:
            logger.exception(e)
        process_time = time.time() - start_time
        logger.info('Process time cost: %s' % str(process_time))