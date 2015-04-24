"""ftp client/server for asyncio"""

from .client import Client
from .errors import StatusCodeError
from .common import Code

version = (0, 0, 1)
__version__ = str.join(".", map(str, version))
