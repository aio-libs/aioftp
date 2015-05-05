import asyncio
import pathlib
import enum


from . import common


@enum.unique
class UserPolitic(enum.Enum):

    FORBIDDEN = 0
    ALLOWED = 1


class Permission:

    def __init__(self, path, *,
                 readable=UserPolitic.ALLOWED,
                 writable=UserPolitic.ALLOWED):

        self.path = pathlib.Path(path)
        self.readable = readable
        self.writable = writable

    def is_parent(self, other):

        try:

            other.relative_to(self.path)
            return True

        except ValueError:

            return False

    def __repr__(self):

        return str.format(
            "Permission({}, readable={}, writable={}",
            self.path,
            self.readable,
            self.writable,
        )


class User:

    def __init__(self, login=None, password=None, *,
                 base_path=pathlib.Path("."), home_path=pathlib.Path("."),
                 permissions=None):

        self.login = login
        self.password = password
        self.base_path = base_path
        self.home_path = home_path
        self.permissions = permissions or [Permission(".")]

    def get_permissions(self, path):

        path = pathlib.Path(path)
        parents = filter(lambda p: p.is_parent(path), self.permissions)
        perm = min(parents, key=lambda p: len(path.relative_to(p.path).parts))
        return perm


class Server:

    def __init__(self):

        pass
