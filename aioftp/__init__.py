"""ftp client/server for asyncio"""
# flake8: noqa

from aioftp.client import *
from aioftp.common import *
from aioftp.errors import *
from aioftp.pathio import *
from aioftp.server import *
from aioftp.client import __all__ as client_all
from aioftp.server import __all__ as server_all
from aioftp.errors import __all__ as errors_all
from aioftp.common import __all__ as common_all
from aioftp.pathio import __all__ as pathio_all


__version__ = "0.21.4"
version = tuple(map(int, __version__.split(".")))

__all__ = client_all + server_all + errors_all + common_all + pathio_all + ("version", "__version__")
