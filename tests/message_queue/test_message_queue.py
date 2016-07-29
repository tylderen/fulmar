# -*- coding: utf-8 -*-
import pytest

from fulmar.message_queue.redis_queue  import NewTaskQueue, ReadyQueue, CronQueue


def test_newtask_queue(redis_conn):
    newtask_queue = NewTaskQueue(redis_conn, 'test_newtask_queue')
    newtask_queue.clear()
    assert len(newtask_queue) == 0
    newtask_queue.put('task_1')
    newtask_queue.put({'task': '任务2'})
    newtask_queue.put({'task': '任务3'}, ['task_4'])
    assert len(newtask_queue) == 4

    assert newtask_queue.get() == 'task_1'
    assert newtask_queue.get() == {'task': u'任务2'}
    assert newtask_queue.get() == {'task': u'任务3'}
    assert newtask_queue.get() == ['task_4']
    assert len(newtask_queue) == 0

def test_ready_queue(redis_conn):
    ready_queue = ReadyQueue(redis_conn, 'test_ready_queue')
    ready_queue.clear()
    assert len(ready_queue) == 0

    with pytest.raises(TypeError):
        ready_queue.put('task_str')
    with pytest.raises(TypeError):
        ready_queue.put({'name': 'task_2', 'priority': '3'})

    ready_queue.put({'name': 'task_1'})
    ready_queue.put({'name': 'task_2', 'priority': 3})
    ready_queue.put({'name': 'task_3', 'priority': 4})
    assert len(ready_queue) == 3

    assert ready_queue.get() == {'name': 'task_3', 'priority': 4}
    assert ready_queue.get() == {'name': 'task_2', 'priority': 3}
    assert ready_queue.get() == {'name': 'task_1'}
    assert len(ready_queue) == 0


def test_cron_queue(redis_conn):
    cron_queue = CronQueue(redis_conn, 'test_cron_queue')
    cron_queue.clear()
    assert len(cron_queue) == 0

    with pytest.raises(TypeError):
        cron_queue.put('task_str')
    with pytest.raises(TypeError):
        cron_queue.put({'name': 'task_2', 'crawl_': '3'}, '100000')

    cron_queue.put({'name': 'task_2', 'priority': 3, 'crawl_later': 3}, 100001)
    cron_queue.put({'name': 'task_3', 'priority': 4, 'crawl_later': 4}, 100002)

    assert len(cron_queue) == 2

    assert cron_queue.get() == ({'name': 'task_2', 'priority': 3, 'crawl_later': 3}, 100001)
    assert cron_queue.get() == ({'name': 'task_3', 'priority': 4, 'crawl_later': 4}, 100002)
    assert len(cron_queue) == 0
