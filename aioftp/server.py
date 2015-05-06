import asyncio
import pathlib


from . import common
from . import errors


def add_prefix(message):

    return str.format("aioftp server: {}", message)


class Permission:

    def __init__(self, path=".", *, readable=True, writable=True):

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
        self.permissions = permissions or [Permission()]

    def get_permissions(self, path):

        path = pathlib.Path(path)
        parents = filter(lambda p: p.is_parent(path), self.permissions)
        perm = min(parents, key=lambda p: len(path.relative_to(p.path).parts))
        return perm


class BaseServer:

    @asyncio.coroutine
    def start(self, host=None, port=None, **kw):

        self.connected = set()
        coro = asyncio.start_server(self.save_dispatcher, host, port, **kw)
        self.server = yield from coro
        host, port = self.server.sockets[0].getsockname()
        message = str.format("serving on {}:{}", host, port)
        common.logger.info(add_prefix(message))

    def close(self):

        self.server.close()

    @asyncio.coroutine
    def wait_closed(self):

        yield from self.server.wait_closed()

    @asyncio.coroutine
    def save_dispatcher(self, reader, writer):

        try:

            self.connected.add((reader, writer))
            yield from self.dispatcher(reader, writer)

        finally:

            self.connected.discard((reader, writer))
            writer.close()

    def write_line(self, reader, writer, code, line, last=False,
                   encoding="utf-8"):

        separator = " " if last else "-"
        message = str.strip(code + separator + line)
        common.logger.info(add_prefix(message))
        writer.write(str.encode(message + "\r\n", encoding=encoding))

    @asyncio.coroutine
    def write_response(self, reader, writer, code, lines=""):

        lines = common.wrap_with_container(lines)
        for line in lines:

            self.write_line(reader, writer, code, line, line is lines[-1])

        yield from writer.drain()

    @asyncio.coroutine
    def parse_command(self, reader, writer):

        line = yield from asyncio.wait_for(reader.readline(), self.timeout)
        if not line:

            raise errors.ConnectionClosedError()

        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        common.logger.info(add_prefix(s))
        cmd, _, rest = str.partition(s, " ")
        return cmd, rest

    @asyncio.coroutine
    def dispatcher(self, reader, writer):

        host, port = writer.transport.get_extra_info("peername", ("", ""))
        message = str.format("new connection from {}:{}", host, port)
        common.logger.info(add_prefix(message))

        ok = yield from self.greeting(reader, writer)
        while ok:

            cmd, rest = yield from self.parse_command(reader, writer)
            if hasattr(self, cmd):

                ok = yield from getattr(self, cmd)(reader, writer, rest)

            else:

                yield from self.write_response(
                    reader,
                    writer,
                    "502",
                    "Not implemented",
                )

    @asyncio.coroutine
    def greeting(self, reader, writer):

        yield from self.write_response(reader, writer, "220")
        return True


class Server(BaseServer):

    def __init__(self, users=None, timeout=None):

        self.users = users or [User()]
        self.timeout = timeout
