import asyncio
import pathlib
import functools
import contextlib
import inspect


from . import common
from . import errors
from . import pathio


def add_prefix(message):

    return str.format("aioftp server: {}", message)


class Permission:

    def __init__(self, path="/", *, readable=True, writable=True):

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
            "Permission({!r}, readable={!r}, writable={!r})",
            self.path,
            self.readable,
            self.writable,
        )


class User:

    def __init__(self, login=None, password=None, *,
                 base_path=pathlib.Path("."), home_path=pathlib.Path("/"),
                 permissions=None):

        self.login = login
        self.password = password
        self.base_path = pathlib.Path(base_path)
        self.home_path = pathlib.Path(home_path)
        self.permissions = permissions or [Permission()]

    def get_permissions(self, path):

        path = pathlib.Path(path)
        parents = filter(lambda p: p.is_parent(path), self.permissions)
        perm = min(
            parents,
            key=lambda p: len(path.relative_to(p.path).parts),
            default=Permission(),
        )
        return perm

    def __repr__(self):

        return str.format(
            "User({!r}, {!r}, base_path={!r}, home_path={!r}, "
            "permissions={!r})",
            self.login,
            self.password,
            self.base_path,
            self.home_path,
            self.permissions,
        )


class BaseServer:

    @asyncio.coroutine
    def start(self, host=None, port=0, **kw):

        self.connections = {}
        self.host = host
        self.port = port
        self.server = yield from asyncio.start_server(
            self.dispatcher,
            host,
            port,
            loop=self.loop,
            **kw
        )
        host, port = self.server.sockets[0].getsockname()
        message = str.format("serving on {}:{}", host, port)
        common.logger.info(add_prefix(message))

    def close(self):

        self.server.close()

    @asyncio.coroutine
    def wait_closed(self):

        yield from self.server.wait_closed()

    @asyncio.coroutine
    def write_line(self, reader, writer, line, encoding="utf-8"):

        common.logger.info(add_prefix(line))
        writer.write(str.encode(line + "\r\n", encoding=encoding))
        yield from writer.drain()

    @asyncio.coroutine
    def write_response(self, reader, writer, code, lines="", list=False):

        lines = common.wrap_with_container(lines)
        write = functools.partial(self.write_line, reader, writer)
        if list:

            head, *body, tail = lines
            yield from write(code + "-" + head)
            for line in body:

                yield from write(" " + line)

            yield from write(code + " " + tail)

        else:

            *body, tail = lines
            for line in body:

                yield from write(code + "-" + line)

            yield from write(code + " " + tail)

    @asyncio.coroutine
    def parse_command(self, reader, writer):

        line = yield from asyncio.wait_for(reader.readline(), self.timeout)
        if not line:

            raise errors.ConnectionClosedError()

        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        common.logger.info(add_prefix(s))
        cmd, _, rest = str.partition(s, " ")
        return str.lower(cmd), rest

    @asyncio.coroutine
    def dispatcher(self, reader, writer):

        host, port = writer.transport.get_extra_info("peername", ("", ""))
        message = str.format("new connection from {}:{}", host, port)
        common.logger.info(add_prefix(message))

        key = reader, writer
        connection = {
            "client_host": host,
            "client_port": port,
            "server_host": self.host,
            "server_port": self.port,
            "command_connection": (reader, writer),
            "timeout": self.timeout,
            "path_io": self.path_io,
            "loop": self.loop,
        }
        self.connections[key] = connection
        write = functools.partial(self.write_response, reader, writer)

        try:

            ok, *args = yield from self.greeting(connection, "")
            yield from write(*args)

            while ok:

                cmd, rest = yield from self.parse_command(reader, writer)
                if cmd == "pass":

                    # is there a better solution?
                    cmd = "pass_"

                if hasattr(self, cmd):

                    ok, *args = yield from getattr(self, cmd)(connection, rest)
                    yield from write(*args)

                else:

                    template = "'{}' not implemented"
                    yield from write("502", str.format(template, cmd))

        finally:

            writer.close()
            self.connections.pop(key)

    @asyncio.coroutine
    def greeting(self, connection, rest):

        raise NotImplementedError


class ConnectionConditions:

    user_required = ("user", "no user (use USER firstly)")
    login_required = ("logged", "not logged in")
    passive_server_started = (
        "passive_server",
        "no listen socket created (use PASV firstly)"
    )
    passive_connection_made = (
        "passive_connection",
        "no passive connection created (connect firstly)"
    )
    rename_from_required = ("rename_from", "no filename (use RNFR firstly)")

    def __init__(self, *fields):

        self.fields = fields

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest):

            for name, message in self.fields:

                if name not in connection:

                    template = "bad sequence of commands ({})"
                    return True, "503", str.format(template, message)

            return (yield from f(cls, connection, rest))

        return wrapper


class PathConditions:

    path_must_exists = ("exists", False, "path does not exists")
    path_must_not_exists = ("exists", True, "path already exists")
    path_must_be_dir = ("is_dir", False, "path is not a directory")
    path_must_be_file = ("is_file", False, "path is not a file")

    def __init__(self, *conditions):

        self.conditions = conditions

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest):

            real_path, virtual_path = cls.get_paths(connection, rest)
            path_io = connection["path_io"]
            for name, fail, message in self.conditions:

                if (yield from getattr(path_io, name)(real_path)) == fail:

                    return True, "550", message

            return (yield from f(cls, connection, rest))

        return wrapper


class PathPermissions:

    readable = "readable"
    writable = "writable"

    def __init__(self, *permissions):

        self.permissions = permissions

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest):

            real_path, virtual_path = cls.get_paths(connection, rest)
            user = connection["user"]
            current_permission = user.get_permissions(virtual_path)
            for permission in self.permissions:

                if not getattr(current_permission, permission):

                    return True, "550", "permission denied"

                return (yield from f(cls, connection, rest))

        return wrapper


def unpack_keywords(f):

    @asyncio.coroutine
    @functools.wraps(f)
    def wrapper(self, connection, rest):

        sig = inspect.signature(f)
        unpacked = {}
        for name, parameter in sig.parameters.items():

            if parameter.kind == inspect.Parameter.KEYWORD_ONLY:

                unpacked[name] = connection[name]

        return (yield from f(self, connection, rest, **unpacked))

    return wrapper


class Server(BaseServer):

    path_facts = (
        ("st_size", "Size"),
        ("st_mtime", "Modify"),
        ("st_ctime", "Create"),
    )

    def __init__(self, users=None, loop=None, *, timeout=None,
                 path_io_factory=pathio.AsyncPathIO):

        self.users = users or [User()]
        self.loop = loop or asyncio.get_event_loop()
        self.timeout = timeout
        self.path_io = path_io_factory(loop)

    def get_paths(self, connection, path):

        virtual_path = pathlib.Path(path)
        user = connection["user"]
        if not virtual_path.is_absolute():

            virtual_path = connection["current_directory"] / virtual_path

        real_path = user.base_path / virtual_path.relative_to("/")
        return real_path, virtual_path

    @asyncio.coroutine
    def greeting(self, connection, rest):

        return True, "220", "welcome"

    @asyncio.coroutine
    def user(self, connection, rest):

        current_user = None
        for user in self.users:

            if user.login is None and current_user is None:

                current_user = user

            elif user.login == rest:

                current_user = user
                break

        if current_user is None:

            code, info = "530", "no such username"
            ok = False

        elif current_user.login is None:

            connection["logged"] = True
            connection["current_directory"] = current_user.home_path
            connection["user"] = current_user
            code, info = "230", "anonymous login"
            ok = True

        else:

            connection["user"] = current_user
            code, info = "331", "require password"
            ok = True

        return ok, code, info

    @ConnectionConditions(ConnectionConditions.user_required)
    @unpack_keywords
    @asyncio.coroutine
    def pass_(self, connection, rest, *, user):

        if user.password == rest:

            connection["logged"] = True
            connection["current_directory"] = user.home_path
            connection["user"] = user
            code, info = "230", "normal login"

        else:

            code, info = "530", "wrong password"

        return True, code, info

    @asyncio.coroutine
    def quit(self, connection, rest):

        return False, "221", "bye"

    @ConnectionConditions(ConnectionConditions.login_required)
    @unpack_keywords
    @asyncio.coroutine
    def pwd(self, connection, rest, *, current_directory):

        return True, "257", str.format("\"{}\"", current_directory)

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.readable)
    @unpack_keywords
    @asyncio.coroutine
    def cwd(self, connection, rest, *, path_io):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection["current_directory"] = virtual_path
        return True, "250", ""

    @ConnectionConditions(ConnectionConditions.login_required)
    @unpack_keywords
    @asyncio.coroutine
    def cdup(self, connection, rest, *, current_directory):

        return (yield from self.cwd(connection, current_directory.parent))

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    @unpack_keywords
    @asyncio.coroutine
    def mkd(self, connection, rest, *, path_io):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from path_io.mkdir(real_path, parents=True)
        return True, "257", ""

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.writable)
    @unpack_keywords
    @asyncio.coroutine
    def rmd(self, connection, rest, *, path_io):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from path_io.rmdir(real_path)
        return True, "257", ""

    @unpack_keywords
    @asyncio.coroutine
    def build_mlsx_string(self, connection, path, *, path_io):

        stats = {}
        if (yield from path_io.is_file(path)):

            stats["Type"] = "file"

        elif (yield from path_io.is_dir(path)):

            stats["Type"] = "dir"

        else:

            raise errors.UnknownPathType(
                str.format(
                    "{} ({})",
                    path,
                    stats["Type"],
                )
            )

        raw_stats = yield from path_io.stat(path)
        for attr, fact in Server.path_facts:

            stats[fact] = getattr(raw_stats, attr)

        s = ""
        for fact, value in stats.items():

            s += str.format("{}={};", fact, value)

        s += " " + path.name
        return s

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started,
        ConnectionConditions.passive_connection_made)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    @unpack_keywords
    @asyncio.coroutine
    def mlsd(self, connection, rest, *, path_io):

        @asyncio.coroutine
        def mlsd_writer():

            data_reader, data_writer = connection.pop("passive_connection")
            with contextlib.closing(data_writer) as data_writer:

                for path in (yield from path_io.list(real_path)):

                    s = yield from self.build_mlsx_string(connection, path)
                    data_writer.write(str.encode(s + "\n", "utf-8"))
                    yield from data_writer.drain()

            reader, writer = connection["command_connection"]
            code, info = "200", "mlsd data transer done"
            yield from self.write_response(reader, writer, code, info)

        real_path, virtual_path = self.get_paths(connection, rest)
        # ensure_future
        asyncio.async(mlsd_writer(), loop=connection["loop"])
        return True, "150", "mlsd transer started"

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def mlst(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        s = yield from self.build_mlsx_string(connection, real_path)
        return True, "250", ["start", s, "end"], True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def rnfr(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection["rename_from"] = real_path
        return True, "350", "rename from accepted"

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.rename_from_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    @unpack_keywords
    @asyncio.coroutine
    def rnto(self, connection, rest, *, path_io):

        real_path, virtual_path = self.get_paths(connection, rest)
        rename_from = connection.pop("rename_from")
        yield from path_io.rename(rename_from, real_path)
        return True, "250", ""

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_not_exists,
        PathConditions.path_must_be_file)
    @PathPermissions(PathPermissions.writable)
    @unpack_keywords
    @asyncio.coroutine
    def dele(self, connection, rest, *, path_io):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from path_io.unlink(real_path)
        return True, "250", ""

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started,
        ConnectionConditions.passive_connection_made)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def stor(self, connection, rest):

        pass

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started,
        ConnectionConditions.passive_connection_made)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def retr(self, connection, rest):

        pass

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def type(self, connection, rest):

        if rest == "I":

            connection["transfer_type"] = rest
            code, info = "200", ""

        else:

            code, info = "502", str.format("type '{}' not implemented", rest)

        return True, code, info

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def pasv(self, connection, rest):

        @asyncio.coroutine
        def handler(reader, writer):

            if "passive_connection" in connection:

                writer.close()

            else:

                connection["passive_connection"] = reader, writer

        if "passive_server" not in connection:

            connection["passive_server"] = yield from asyncio.start_server(
                handler,
                connection["server_host"],
                0,
                loop=self.loop,
            )
            code, info = "227", ["listen socket created"]

        else:

            code, info = "227", ["listen socket already exists"]

        host, port = connection["passive_server"].sockets[0].getsockname()
        nums = tuple(map(int, str.split(host, "."))) + (port >> 8, port & 0xff)
        info.append(str.format("({})", str.join(",", map(str, nums))))
        return True, code, info

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def abor(self, connection, rest):

        pass
