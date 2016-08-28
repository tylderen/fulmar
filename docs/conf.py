import sys
from unittest.mock import MagicMock

class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
            return Mock()

MOCK_MODULES = ['pycurl', 'lxml', 'psycopg2']
sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)