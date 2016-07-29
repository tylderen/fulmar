# -*- encoding: utf-8 -*-
from .redis_queue import NewTaskQueue, ReadyQueue, CronQueue

try:
    from urllib import parse as urlparse
except ImportError:
    import urlparse

try:
    from ..utils import redis_conn
except ImportError:
    from ..utils import connect_redis
    redis_conn = connect_redis()

newtask_queue = NewTaskQueue(redis_conn, 'fulmar_newtask_queue')
ready_queue = ReadyQueue(redis_conn, 'fulmar_readytask_queue')
cron_queue = CronQueue(redis_conn, 'fulmar_cron_queue')
