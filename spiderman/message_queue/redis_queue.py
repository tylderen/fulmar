# -*- encoding: utf-8 -*-

import msgpack



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
        return msgpack.loads(task)

    def __len__(self):
        """Return the length of the queue"""
        raise NotImplementedError

    def push(self, task):
        """Push a task"""
        raise NotImplementedError

    def pop(self, timeout=0):
        """Pop a task"""
        raise NotImplementedError

    def clear(self):
        """Clear queue/stack"""
        self.server.delete(self.key)

class SpidermanQueue(QueueBase):
    """FIFO queue"""

    def __len__(self):
        """Return the length of the queue"""
        return self.server.llen(self.key)

    def push(self, task):
        """Push a task"""
        self.server.lpush(self.key, self._pack(task))

    def pop(self, timeout=0):
        """Pop a task"""
        if timeout > 0:
            data = self.server.brpop(self.key, timeout)
            if isinstance(data, tuple):
                data = data[1]
        else:
            data = self.server.rpop(self.key)
        if data:
            return self._unpack(data)


class SpidermanReadyQueue(QueueBase):
    """Priority queue abstraction using redis' sorted set"""
    def __len__(self):
        """Return the length of the queue"""
        return self.server.zcard(self.key)

    def push(self, task):
        """Push a task"""
        priority = task.get('priority', 2)
        print task
        print priority
        data = self._pack(task)
        pairs = {data: priority}
        self.server.zadd(self.key, **pairs)

    def pop(self, timeout=0):
        """
        Pop a task
        timeout not support in this queue class
        """
        # use atomic range/remove using multi/exec
        pipe = self.server.pipeline()
        pipe.multi()
        pipe.zrange(self.key, 0, 0).zremrangebyrank(self.key, 0, 0)
        results, count = pipe.execute()
        if results:
            return self._unpack(results[0])
        else:
            return None

