# -*- encoding: utf-8 -*-
# Author: Binux<i@binux.me>
#         http://binux.me

import imp
import inspect
import linecache
import logging
import time
import traceback
import six

from fulmar.log import SaveLogHandler, LogFormatter

logger = logging.getLogger(__name__)


class ProjectManager(object):
    """
    load projects from projectdb, update project if needed.
    """
    @staticmethod
    def build_module(project, env={}):
        '''Build project script as module'''
        from fulmar import base_spider
        assert 'project_name' in project, 'need name of project'
        assert 'script' in project, 'need script of project'
        assert 'project_id' in project, 'need id of project'

        env = dict(env)
        env.update({
            'debug': project.get('status', 'DEBUG') == 'DEBUG',
        })

        loader = ProjectLoader(project)
        module = loader.load_module(project['project_name'])
        # logger inject
        module.log_buffer = []
        module.logging = module.logger = logging.Logger(project['project_name'])
        '''
        if env.get('enable_stdout_capture', False):
            logger.info(env)
            handler = SaveLogHandler(module.log_buffer)
            handler.setFormatter(LogFormatter(color=False))
        else:
        '''
        handler = logging.StreamHandler()
        handler.setFormatter(LogFormatter(color=True))
        module.logger.addHandler(handler)

        if '__handler_cls__' not in module.__dict__:
            BaseSpider = module.__dict__.get('BaseSpider', base_spider.BaseSpider)
            for each in list(six.itervalues(module.__dict__)):
                if inspect.isclass(each) and each is not BaseSpider \
                        and issubclass(each, BaseSpider):
                    module.__dict__['__handler_cls__'] = each
        _class = module.__dict__.get('__handler_cls__')
        assert _class is not None, "need BaseSpider in project module."

        instance = _class()
        instance.__env__ = env
        if not instance.project_name:
            instance.project_name = project['project_name']
        if not instance.project_id:
            instance.project_id = project['project_id']
        instance.project = project

        return {
            'loader': loader,
            'module': module,
            'class': _class,
            'instance': instance,
            'exception': None,
            'exception_log': '',
            'info': project,
        }

    def __init__(self, projectdb, env):
        self.projectdb = projectdb
        self.env = env
        self.projects = {}

    def _need_update(self, project_name, project_id=None):
        '''Check if project_name need update'''
        if project_name not in self.projects:
            return True
        elif project_id and project_id != self.projects[project_name]['info']['project_id']:
            return True
        return False

    def _update_project(self, project_name):
        '''Update one project from database'''
        project = self.projectdb.get(project_name)
        if not project:
            return None
        return self._load_project(project)

    def _load_project(self, project):
        '''Load project into self.projects from project info dict'''
        try:
            ret = self.build_module(project, self.env)
            self.projects[project['project_name']] = ret
        except Exception as e:
            logger.exception("load project %s error", project.get('project_name', None))
            ret = {
                'loader': None,
                'module': None,
                'class': None,
                'instance': None,
                'exception': e,
                'exception_log': traceback.format_exc(),
                'info': project,
                'load_time': time.time(),
            }
            self.projects[project['project_name']] = ret
            return False
        logger.debug('project: %s updated.', project.get('project_name', None))
        return True

    def get(self, project_name, project_id):
        '''get project data object, return None if not exists'''
        if self._need_update(project_name, project_id):
            self._update_project(project_name)
        return self.projects.get(project_name, None)


class ProjectLoader(object):
    '''ProjectLoader class for sys.meta_path'''

    def __init__(self, project, mod=None):
        self.project = project
        self.name = project['project_name']
        self.mod = mod

    def load_module(self, fullname):
        if self.mod is None:
            self.mod = mod = imp.new_module(fullname)
        else:
            mod = self.mod
        mod.__file__ = '<%s>' % self.name
        mod.__loader__ = self
        mod.__project__ = self.project
        mod.__package__ = ''
        code = self.get_code(fullname)
        six.exec_(code, mod.__dict__)
        linecache.clearcache()
        return mod

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        return compile(self.get_source(fullname), '<%s>' % self.name, 'exec')

    def get_source(self, fullname):
        script = self.project['script']
        if isinstance(script, six.text_type):
            return script.encode('utf8')
        return script
