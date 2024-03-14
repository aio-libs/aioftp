"""ftp client/server for asyncio"""

# flake8: noqa

import importlib.metadata

from .client import BaseClient, Client, Code, DataConnectionThrottleStreamIO
from .common import (
    DEFAULT_ACCOUNT,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USER,
    END_OF_LINE,
    AbstractAsyncLister,
    AsyncListerMixin,
    AsyncStreamIterator,
    StreamIO,
    StreamThrottle,
    Throttle,
    ThrottleStreamIO,
    async_enterable,
    setlocale,
    with_timeout,
    wrap_with_container,
)
from .errors import AIOFTPException, NoAvailablePort, PathIOError, PathIsNotAbsolute, StatusCodeError
from .pathio import (
    AbstractPathIO,
    AsyncPathIO,
    MemoryPathIO,
    PathIO,
    PathIONursery,
)
from .server import (
    AbstractUserManager,
    AvailableConnections,
    Connection,
    ConnectionConditions,
    MemoryUserManager,
    PathConditions,
    PathPermissions,
    Permission,
    Server,
    User,
    worker,
)

__version__ = importlib.metadata.version(__package__)  # pyright: ignore[reportArgumentType]
version = tuple(map(int, __version__.split(".")))


__all__ = (
    # client
    "BaseClient",
    "Client",
    "DataConnectionThrottleStreamIO",
    "Code",
    # server
    "Server",
    "Permission",
    "User",
    "AbstractUserManager",
    "MemoryUserManager",
    "Connection",
    "AvailableConnections",
    "ConnectionConditions",
    "PathConditions",
    "PathPermissions",
    "worker",
    # errors
    "AIOFTPException",
    "StatusCodeError",
    "PathIsNotAbsolute",
    "PathIOError",
    "NoAvailablePort",
    # common
    "with_timeout",
    "StreamIO",
    "Throttle",
    "StreamThrottle",
    "ThrottleStreamIO",
    "END_OF_LINE",
    "DEFAULT_BLOCK_SIZE",
    "wrap_with_container",
    "AsyncStreamIterator",
    "AbstractAsyncLister",
    "AsyncListerMixin",
    "async_enterable",
    "DEFAULT_PORT",
    "DEFAULT_USER",
    "DEFAULT_PASSWORD",
    "DEFAULT_ACCOUNT",
    "setlocale",
    # pathio
    "AbstractPathIO",
    "PathIO",
    "AsyncPathIO",
    "MemoryPathIO",
    "PathIONursery",
    #
    "version",
    "__version__",
)
