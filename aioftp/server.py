import asyncio
import logging
import pathlib
import enum


logger = logging.getLogger("aioftp")


@enum.unique
class DefaultUserPolitic(enum.Enum):

    FORBIDDEN = 0
    ALLOWED = 1


class User:

    def __init__(self, base_path, read_paths=(), write_paths=(),
                 default_read_permission=DefaultUserPolitic.ALLOWED,
                 default_write_permission=DefaultUserPolitic.ALLOWED):

        pass


class Server:

    def __init__(self):

        pass
