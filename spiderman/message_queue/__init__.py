# -*- encoding: utf-8 -*-

from ..utils import redis
from redis_queue import SpidermanQueue, SpidermanReadyQueue

newtask_queue = SpidermanQueue(redis, 'spiderman_newtask_queue')
ready_queue = SpidermanReadyQueue(redis, 'spiderman_readytask_queue')