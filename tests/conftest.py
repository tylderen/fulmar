import pytest

from fulmar.utils import connect_redis


@pytest.fixture(scope="module")
def redis_conn():
    conn = connect_redis()
    return conn
