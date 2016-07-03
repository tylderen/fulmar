# -*- encoding: utf-8 -*-

import msgpack
from ..utils import redis


class Projectdb(object):
    def __init__(self, server, projectdb):
        """
        Parameters:
            server -- redis connection
            projectdb -- fulmar projectdb name
            project -- project name for this queue (e.g. "%(spider)s:queue")
        """
        self.server = server
        self.projectdb = projectdb

    def _pack(self, task):
        """pack a task"""
        return msgpack.dumps(task)

    def _unpack(self, task):
        """unpack a task previously packed"""
        return msgpack.loads(task)

    def get(self, project_name):
        project_data = self.server.hget(self.projectdb, project_name)
        if not project_data:
            return None
        return self._unpack(project_data)

    def set(self, project_name, project_data):
        data = self._pack(project_data)
        self.server.hset(self.projectdb, project_name, data)

    def delete(self, project_name):
        self.server.hdel(self.projectdb, project_name)

projectdb = Projectdb(redis, 'fulmar_projectdb')