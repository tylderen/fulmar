# -*- encoding: utf-8 -*-

from ..utils import redis
from redis_queue import fulmarQueue, fulmarReadyQueue

newtask_queue = fulmarQueue(redis, 'fulmar_newtask_queue')
ready_queue = fulmarReadyQueue(redis, 'fulmar_readytask_queue')