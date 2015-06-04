"""ftp client/server for asyncio"""

from .client import Client
from .server import Server, User, Permission, unpack_keywords, \
    PathPermissions
from .errors import StatusCodeError, PathIsNotFileOrDir, PathIsNotAbsolute
from .common import Code
from .pathio import AbstractPathIO, PathIO, AsyncPathIO, MemoryPathIO

version = (0, 0, 1)
__version__ = str.join(".", map(str, version))
