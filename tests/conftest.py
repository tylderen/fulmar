import pytest
from fulmar.utils import connect_redis


@pytest.fixture
def redis_conn(scope="module"):
    conn = connect_redis()
    return conn