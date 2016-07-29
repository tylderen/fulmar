# -*- encoding: utf-8 -*-
import msgpack
import logging

logger = logging.getLogger(__name__)

class QueueBase(object):
    """Per-spider queue/stack base class"""

    def __init__(self, server, key):
        """Initialize per-spider redis queue.
        Parameters:
            server -- redis connection
            spider -- spider instance
            key -- key for this queue (e.g. "%(spider)s:queue")
        """
        self.server = server
        # todo: the name of the list or set
        self.key = key

    def _pack(self, task):
        """pack a task"""
        return msgpack.dumps(task)

    def _unpack(self, task):
        """unpack a task previously packed"""
        return msgpack.loads(task, encoding='utf8')

    def __bool__(self):
        return True

    def __nonzero__(self):
        return True

    def __len__(self):
        """Return the length of the queue"""
        raise NotImplementedError

    def put(self, task):
        """Put a task"""
        raise NotImplementedError

    def get(self, timeout=0):
        """Get a task"""
        raise NotImplementedError

    def clear(self):
        """Clear queue/stack"""
        self.server.delete(self.key)


class NewTaskQueue(QueueBase):
    """FIFO queue"""

    def __len__(self):
        """Return the length of the queue"""
        return self.server.llen(self.key)

    def put(self, *tasks):
        """Put tasks"""
        packed_tasks = []
        for task in tasks:
            packed_tasks.append(self._pack(task))
        if packed_tasks:
            self.server.lpush(self.key, *packed_tasks)

    def get(self, timeout=0):
        """Get a task"""
        if timeout > 0:
            data = self.server.brpop(self.key, timeout)
            if isinstance(data, tuple):
                data = data[1]
        else:
            data = self.server.rpop(self.key)
        if data:
            return self._unpack(data)


class ReadyQueue(QueueBase):
    """Priority queue abstraction using redis' sorted set"""
    def __len__(self):
        """Return the length of the queue"""
        return self.server.zcard(self.key)

    def put(self, task):
        """Put a task"""
        if not isinstance(task, dict):
            raise TypeError('task\'s type must be dict.' )
        priority = task.get('priority', 2)
        if not isinstance(priority, int):
            raise TypeError('priority\'s type must be int.')
        data = self._pack(task)
        pairs = {data: priority}
        self.server.zadd(self.key, **pairs)

    def get(self, timeout=0):
        """
        Get a task
        timeout not support in this queue class
        """
        # use atomic range/remove using multi/exec
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.zrange(self.key, 0, 0, desc=True).zremrangebyrank(self.key, -1, -1)
        #pipe.zremrangebyrank(self.key, -1, -1)
        results, count = pipe.execute()
        if results:
            return self._unpack(results[0])
        else:
            return None


class CronQueue(QueueBase):

    def __len__(self):
        """Return the length of the queue"""
        return self.server.zcard(self.key)
    def range(self, start=0, end=-1):
        task_pair = []
        range = self.server.zrange(self.key, start, end, withscores=True)
        for task, crawl_timestamp in range:
            task = self._unpack(task)
            task_pair.append((task, crawl_timestamp))
        return task_pair

    def put(self, task, when):
        """Put a task"""

        if not isinstance(task, dict):
            raise TypeError('task\'s type must be dict.')
        if not isinstance(when, (int, float)):
            raise TypeError('when\'s type must be timestamp.')

        data = self._pack(task)
        pairs = {data: when}
        self.server.zadd(self.key, **pairs)

    def get(self, timeout=0):
        """
        Get a task
        timeout not support in this queue class
        """
        # use atomic range/remove using multi/exec
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.zrange(self.key, 0, 0, withscores=True).zremrangebyrank(self.key, 0, 0)
        results, count = pipe.execute()
        if results:
            return self._unpack(results[0][0]), results[0][1]
        else:
            return None, None

    def delete_one(self, task):
        data = self._pack(task)
        self.server.zrem(self.key, data)

