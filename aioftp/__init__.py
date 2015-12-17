"""ftp client/server for asyncio"""

from .client import *  # noqa
from .server import *  # noqa
from .errors import *  # noqa
from .common import *  # noqa
from .pathio import *  # noqa

__version__ = "0.4.0"
version = tuple(map(int, str.split(__version__, ".")))

__all__ = (
    client.__all__ +
    server.__all__ +
    errors.__all__ +
    common.__all__ +
    pathio.__all__ +
    ("version", "__version__")
)
