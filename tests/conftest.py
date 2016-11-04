import pytest
import httpbin

from fulmar.utils import connect_redis, run_in_subprocess


@pytest.fixture(scope="module")
def redis_conn():
    conn = connect_redis()
    return conn
