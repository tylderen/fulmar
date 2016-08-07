# -*- encoding: utf-8 -*-
import msgpack

try:
    from ..utils import redis_conn
except ImportError:
    from ..utils import connect_redis
    redis_conn = connect_redis()

PROJECT_DB = 'fulmar_projectdb'


class Projectdb(object):
    def __init__(self, server, projectdb):
        """
        Parameters:
            server -- redis connection
            projectdb -- fulmar projectdb name
        """
        self.server = server
        self.projectdb = projectdb

    def __len__(self):
        return self.server.hlen(self.projectdb)

    def __bool__(self):
        return True

    def __nonzero__(self):
        return True

    def _pack(self, task):
        """pack a task"""
        return msgpack.dumps(task)

    def _unpack(self, task):
        """unpack a task previously packed"""
        return msgpack.loads(task, encoding='utf8')

    def get(self, project_name):
        project_data = self.server.hget(self.projectdb, project_name)
        if not project_data:
            return None
        return self._unpack(project_data)

    def get_all(self):
        projects = {}
        projects_data = self.server.hgetall(self.projectdb)
        for name, data in projects_data.iteritems():
            projects.update({name: self._unpack(data)})
        return projects

    def set(self, project_name, project_data):
        if not isinstance(project_data, dict):
            raise TypeError('project_data\'s type must be dict.')
        if project_data.get('project_id') \
           and project_data.get('project_name') \
           and project_data.get('script'):
            data = self._pack(project_data)
            self.server.hset(self.projectdb, project_name, data)
        else:
            raise Exception('project_data must contain project_id, project_name and script !')

    def delete(self, project_name):
        self.server.hdel(self.projectdb, project_name)

    def clear(self):
        """Please be careful. Clear projectdb !"""
        self.server.delete(self.projectdb)


projectdb = Projectdb(redis_conn, PROJECT_DB)
