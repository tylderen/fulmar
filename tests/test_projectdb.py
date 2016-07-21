# -*- coding: utf-8 -*-
import pytest

from fulmar.scheduler.projectdb  import Projectdb


def test_projectdb(redis_conn):
    projectdb = Projectdb(redis_conn, 'test_projectdb')
    projectdb.clear()
    assert len(projectdb) == 0

    with pytest.raises(TypeError):
        projectdb.set('test_project', 'test_project')

    data = {'project_name': 'test_project_name', 'script': 'Python raw code', }
    with pytest.raises(Exception):
        projectdb.set('test_project_1', data)

    data.update({'project_id': 'test_project_id'})
    projectdb.set('test_project_1', data)
    assert len(projectdb) == 1
    assert projectdb.get('test_project_1') == data

    data.update({'script': 'Version 2: Python raw code'})
    projectdb.set('test_project_1', data)
    assert len(projectdb) == 1
    assert projectdb.get('test_project_1') == data

    projectdb.delete('test_project_1')
    assert len(projectdb) == 0