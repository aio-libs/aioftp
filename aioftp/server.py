import asyncio
import pathlib
import functools
import contextlib
import inspect
import datetime
import socket
import collections
import concurrent


from . import common
from . import errors
from . import pathio


__all__ = (
    "Permission",
    "User",
    "Connection",
    "ConnectionConditions",
    "PathConditions",
    "PathPermissions",
    "Server",
)


def add_prefix(message):

    return str.format("aioftp server: {}", message)


class Permission:
    """
    Path permission

    :param path: path
    :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

    :param readable: is readable
    :type readable: :py:class:`bool`

    :param writable: is writable
    :type writable: :py:class:`bool`
    """

    def __init__(self, path="/", *, readable=True, writable=True):

        self.path = pathlib.PurePosixPath(path)
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
            "{}({!r}, readable={!r}, writable={!r})",
            self.__class__.__name__,
            self.path,
            self.readable,
            self.writable,
        )


class User:
    """
    User description.

    :param login: user login
    :type login: :py:class:`str`

    :param password: user password
    :type password: :py:class:`str`

    :param base_path: real user path for file io operations
    :type base_path: :py:class:`str` or :py:class:`pathlib.Path`

    :param home_path: virtual user path for client representation (must be
        absolute)
    :type home_path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

    :param permissions: list of path permissions
    :type permissions: :py:class:`tuple` or :py:class:`list` of
        :py:class:`aioftp.Permission`

    :param maximum_connections: Maximum connections per user
    :type maximum_connections: :py:class:`int`
    """

    def __init__(self, login=None, password=None, *,
                 base_path=pathlib.Path("."),
                 home_path=pathlib.PurePosixPath("/"), permissions=None,
                 maximum_connections=None):

        self.login = login
        self.password = password
        self.base_path = pathlib.Path(base_path)
        self.home_path = pathlib.PurePosixPath(home_path)
        if not self.home_path.is_absolute():

            raise errors.PathIsNotAbsolute(home_path)

        self.permissions = permissions or [Permission()]
        self.maximum_connections = maximum_connections

    def get_permissions(self, path):
        """
        Return nearest parent permission for `path`.

        :param path: path which permission you want to know
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`aioftp.Permission`
        """
        path = pathlib.PurePosixPath(path)
        parents = filter(lambda p: p.is_parent(path), self.permissions)
        perm = min(
            parents,
            key=lambda p: len(path.relative_to(p.path).parts),
            default=Permission(),
        )
        return perm

    def __repr__(self):

        return str.format(
            "{}({!r}, {!r}, base_path={!r}, home_path={!r}, permissions={!r}, "
            "maximum_connections={!r})",
            self.__class__.__name__,
            self.login,
            self.password,
            self.base_path,
            self.home_path,
            self.permissions,
            self.maximum_connections,
        )


class UserManager:
    """
    Abstract user manager.
    """

    @asyncio.coroutine
    def get_user(self, login):
        """
        :py:func:`asyncio.coroutine`

        Get user and response for USER call

        :param login: user's login
        :type login: :py:class:`str`

        :return: (user, logged, code, info)
        :rtype: (:py:class:`aioftp.User`, :py:class:`bool`, :py:class:`str`,
            :py:class:`str`)
        """
        raise NotImplementedError

    @asyncio.coroutine
    def authenticate(self, user, password):
        """
        :py:func:`asyncio.coroutine`

        Check if user can be authenticated with provided password

        :param user: user
        :type user: :py:class:`aioftp.User`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def notify_logout(self, user):
        """
        :py:func:`asyncio.coroutine`

        Called when user connection is closed if user was initiated

        :param user: user
        :type user: :py:class:`aioftp.User`
        """
        pass


class MemoryUserManager(UserManager):
    """
    A built-in user manager that keeps predefined set of users in memory.
    """

    def __init__(self, users):

        self.users = users or [User()]
        self.available_connections = dict(
            (user, AvailableConnections(user.maximum_connections))
            for user in self.users
        )

    @asyncio.coroutine
    def get_user(self, login):

        user = None
        for u in self.users:

            if u.login is None and user is None:

                user = u

            elif u.login == login:

                user = u
                break

        if user is None:

            raise IndexError("530", "no such username")

        elif self.available_connections[user].locked():

            template = "too much connections for '{}'"
            message = str.format(template, user.login or "anonymous")
            raise IndexError("530", message)

        elif user.login is None:

            logged, code, info = True, "230", "anonymous login"

        elif user.password is None:

            logged, code, info = True, "230", "login without password"

        else:

            logged, code, info = False, "331", "require password"

        self.available_connections[user].acquire()
        return user, logged, code, info

    @asyncio.coroutine
    def authenticate(self, user, password):

        return user.password == password

    @asyncio.coroutine
    def notify_logout(self, user):

        self.available_connections[user].release()


class Connection(collections.defaultdict):
    """
    Connection state container for transparent work with futures for async
    wait

    :param loop: event loop
    :type loop: :py:class:`asyncio.BaseEventLoop`

    Container based on :py:class:`collections.defaultdict`, which holds
    :py:class:`asyncio.Future` as default factory. There is two layers of
    abstraction:

    * Low level based on simple dictionary keys to attributes mapping and
        available at Connection.future.
    * High level based on futures result and dictionary keys to attributes
        mapping and available at Connection.

    To clarify, here is groups of equal expressions
    ::

        >>> connection.future.foo
        >>> connection["foo"]

        >>> connection.foo
        >>> connection["foo"].result()

        >>> del connection.future.foo
        >>> del connection.foo
        >>> del connection["foo"]
    """

    __slots__ = ("future",)

    class Container:

        def __init__(self, storage):

            self.storage = storage

        def __getattr__(self, name):

            return self.storage[name]

        def __delattr__(self, name):

            self.storage.pop(name)

    def __init__(self, *, loop=None, **kwargs):

        super().__init__(functools.partial(asyncio.Future, loop=loop))
        self.future = Connection.Container(self)

        self["loop"].set_result(loop)
        for k, v in kwargs.items():

            self[k].set_result(v)

    def __getattr__(self, name):

        if name in self:

            return self[name].result()

        else:

            raise AttributeError(str.format("'{}' not in storage", name))

    def __setattr__(self, name, value):

        if name in Connection.__slots__:

            super().__setattr__(name, value)

        else:

            if self[name].done():

                self[name] = self.default_factory()

            self[name].set_result(value)

    def __delattr__(self, name):

        if name in self:

            self.pop(name)

        else:

            super().__delattr__(name)


class AvailableConnections:
    """
    Semaphore-like object. Have no blocks, only raises ValueError on bounds
        crossing. If value is `None` have no limits (bounds checks).

    :param value:
    :type value: :py:class:`int` or `None`
    """

    def __init__(self, value=None):

        self.value = self.maximum_value = value

    def locked(self):
        """
        Returns True if semaphore-like can not be acquired.

        :rtype: :py:class:`bool`
        """
        return self.value == 0

    def acquire(self):
        """
        Acquire, decrementing the internal counter by one.
        """
        if self.value is not None:

            self.value -= 1
            if self.value < 0:

                raise ValueError("Too much acquires")

    def release(self):
        """
        Release, incrementing the internal counter by one.
        """
        if self.value is not None:

            self.value += 1
            if self.value > self.maximum_value:

                raise ValueError("Too much releases")


class BaseServer:

    @asyncio.coroutine
    def start(self, host=None, port=0, **kw):
        """
        :py:func:`asyncio.coroutine`

        Start server.

        :param host: ip address to bind for listening.
        :type host: :py:class:`str`

        :param port: port number to bind for listening.
        :type port: :py:class:`int`

        :param kw: keyword arguments, they passed to
            :py:func:`asyncio.start_server`
        """
        self.connections = {}
        self.server_host = host
        self.server_port = port
        self.server = yield from asyncio.start_server(
            self.dispatcher,
            host,
            port,
            loop=self.loop,
            **kw
        )

        for sock in self.server.sockets:

            if sock.family == socket.AF_INET:

                host, port = sock.getsockname()
                message = str.format("serving on {}:{}", host, port)
                common.logger.info(add_prefix(message))

    def close(self):
        """
        Shutdown the server and close all connections. Use this method with
        :py:meth:`aioftp.Server.wait_closed`
        """
        self.server.close()
        for connection in self.connections.values():

            connection._dispatcher.cancel()

    @asyncio.coroutine
    def wait_closed(self):
        """
        :py:func:`asyncio.coroutine`

        Wait server to stop.
        """
        yield from self.server.wait_closed()

    @asyncio.coroutine
    def write_line(self, reader, writer, line, encoding="utf-8", *,
                   loop, socket_timeout=None):

        common.logger.info(add_prefix(line))
        message = line + common.end_of_line
        writer.write(str.encode(message, encoding=encoding))
        yield from asyncio.wait_for(
            writer.drain(),
            socket_timeout,
            loop=loop,
        )

    @asyncio.coroutine
    def write_response(self, reader, writer, code, lines="", list=False, *,
                       loop, socket_timeout=None):
        """
        :py:func:`asyncio.coroutine`

        Complex method for sending response.

        :param reader: connection steram reader
        :type reader: :py:class:`asyncio.StreamReader`

        :param writer: connection stream writer
        :type writer: :py:class:`asyncio.StreamWriter`

        :param code: server response code
        :type code: :py:class:`str`

        :param lines: line or lines, which are response information
        :type lines: :py:class:`str` or :py:class:`collections.Iterable`

        :param list: if true, then lines will be sended without code prefix.
            This is useful for **LIST** FTP command and some others.
        :type list: :py:class:`bool`

        :param loop: event loop
        :type loop: :py:class:`asyncio.BaseEventLoop`

        :param socket_timeout: timeout for socket write operations
        :type socket_timeout: :py:class:`float` or :py:class:`int`
        """
        lines = common.wrap_with_container(lines)
        write = functools.partial(
            self.write_line,
            reader,
            writer,
            loop=loop,
            socket_timeout=socket_timeout,
        )
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
    def parse_command(self, reader, writer, *, loop, idle_timeout=None):
        """
        :py:func:`asyncio.coroutine`

        Complex method for getting command.

        :param reader: connection steram reader
        :type reader: :py:class:`asyncio.StreamReader`

        :param writer: connection stream writer
        :type writer: :py:class:`asyncio.StreamWriter`

        :param loop: event loop
        :type loop: :py:class:`asyncio.BaseEventLoop`

        :param idle_timeout: timeout for socket read operations, another
            words: how long user can keep silence without sending commands
        :type idle_timeout: :py:class:`float` or :py:class:`int`

        :return: (code, rest)
        :rtype: (:py:class:`str`, :py:class:`str`)
        """
        line = yield from asyncio.wait_for(
            reader.readline(),
            idle_timeout,
            loop=loop,
        )
        if not line:

            raise ConnectionResetError

        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        common.logger.info(add_prefix(s))
        cmd, _, rest = str.partition(s, " ")
        return str.lower(cmd), rest

    def CommandParser(self, connection):
        """
        Shorthand for parse_command with current connection

        :param connection:
        :type connection: :py:class:`aioftp.Connection`

        :return: :py:meth:`aioftp.Server.parse_command` coroutine
        :rtype: :py:func:`asyncio.coroutine`
        """
        return self.parse_command(
            *connection.command_connection,
            loop=connection.loop,
            idle_timeout=connection.idle_timeout
        )

    @asyncio.coroutine
    def response_writer(self, connection, response_queue):
        """
        :py:func:`asyncio.coroutine`

        Worker for write_response with current connection. Get data to response
        from queue, this is for right order of responses. Exits if received
        `None`.

        :param connection:
        :type connection: :py:class:`aioftp.Connection`

        :param response_queue:
        :type response_queue: :py:class:`asyncio.Queue`

        :return: :py:meth:`aioftp.Server.write_response` coroutine
        :rtype: :py:func:`asyncio.coroutine`
        """
        while True:

            args = yield from response_queue.get()
            if args is None:

                break

            yield from self.write_response(
                *(connection.command_connection + args),
                loop=connection.loop,
                socket_timeout=connection.socket_timeout
            )

    def _generate_tasks(self, connection, pending):

        for o in pending | connection.extra_workers:

            if asyncio.iscoroutine(o):

                yield connection.loop.create_task(o)

            else:

                yield o

        connection.extra_workers.clear()

    @asyncio.coroutine
    def dispatcher(self, reader, writer):

        host, port = writer.transport.get_extra_info("peername", ("", ""))
        message = str.format("new connection from {}:{}", host, port)
        common.logger.info(add_prefix(message))

        key = reader, writer
        response_queue = asyncio.Queue(loop=self.loop)
        connection = Connection(
            client_host=host,
            client_port=port,
            server_host=self.server_host,
            server_port=self.server_port,
            command_connection=(reader, writer),
            socket_timeout=self.socket_timeout,
            path_timeout=self.path_timeout,
            idle_timeout=self.idle_timeout,
            wait_future_timeout=self.wait_future_timeout,
            block_size=self.block_size,
            path_io=self.path_io,
            loop=self.loop,
            extra_workers=set(),
            response=lambda *args: response_queue.put_nowait(args),
            acquired=False,
            _dispatcher=asyncio.Task.current_task(loop=self.loop),
        )

        pending = {
            self.greeting(connection, ""),
            self.response_writer(connection, response_queue),
            self.CommandParser(connection),
        }
        self.connections[key] = connection

        try:

            ok = True
            while ok or not response_queue.empty():

                pending = set(self._generate_tasks(connection, pending))
                done, pending = yield from asyncio.wait(
                    pending,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                    loop=connection.loop
                )
                for task in done:

                    result = task.result()

                    # this is "command" result
                    if isinstance(result, bool):

                        ok = result
                        if not ok:

                            # bad solution, but have no better ideas right now
                            connection.response(None)
                            break

                    # this is parse_command result
                    else:

                        pending.add(self.CommandParser(connection))

                        cmd, rest = result
                        if cmd == "pass":

                            # is there a better solution?
                            cmd = "pass_"

                        if hasattr(self, cmd):

                            pending.add(getattr(self, cmd)(connection, rest))

                        else:

                            message = str.format("'{}' not implemented", cmd)
                            connection.response("502", message)

        finally:

            message = str.format("closing connection from {}:{}", host, port)
            common.logger.info(add_prefix(message))

            if not connection.loop.is_closed():

                for task in pending:

                    if isinstance(task, asyncio.Task):

                        task.cancel()

                if connection.future.passive_server.done():

                    connection.passive_server.close()

                if connection.future.data_connection.done():

                    r, w = connection.data_connection
                    w.close()

                writer.close()

            if connection.acquired:

                self.available_connections.release()

            if connection.future.user.done():

                yield from self.user_manager.notify_logout(connection.user)

            self.connections.pop(key)

    @asyncio.coroutine
    def greeting(self, connection, rest):

        raise NotImplementedError


class ConnectionConditions:
    """
    Decorator for checking `connection` keys for existence or wait for them.
    Available options:

    :param fields: * `ConnectionConditions.user_required` — required "user"
          key, user already identified
        * `ConnectionConditions.login_required` — required "logged" key, user
          already logged in.
        * `ConnectionConditions.passive_server_started` — required
          "passive_server" key, user already send PASV and server awaits
          incomming connection
        * `ConnectionConditions.data_connection_made` — required
          "data_connection" key, user already connected to passive connection
        * `ConnectionConditions.rename_from_required` — required "rename_from"
          key, user already tell filename for rename

    :param wait: Indicates if should wait for parameters for
        `connection.wait_future_timeout`
    :type wait: :py:class:`bool`

    :param fail_code: return code if failure
    :type fail_code: :py:class:`str`

    :param fail_info: return information string if failure. If `None`, then
        use default string
    :type fail_info: :py:class:`str`

    ::

        >>> @ConnectionConditions(
        ...     ConnectionConditions.login_required,
        ...     ConnectionConditions.passive_server_started,
        ...     ConnectionConditions.data_connection_made,
        ...     wait=True)
        ... def foo(self, connection, rest):
        ...     ...
    """
    user_required = ("user", "no user (use USER firstly)")
    login_required = ("logged", "not logged in")
    passive_server_started = (
        "passive_server",
        "no listen socket created (use PASV firstly)"
    )
    data_connection_made = ("data_connection", "no data connection made")
    rename_from_required = ("rename_from", "no filename (use RNFR firstly)")

    def __init__(self, *fields, wait=False, fail_code="503", fail_info=None):

        self.fields = fields
        self.wait = wait
        self.fail_code = fail_code
        self.fail_info = fail_info

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest, *args):

            futures = {connection[name]: msg for name, msg in self.fields}
            aggregate = asyncio.gather(*futures, loop=connection.loop)

            if self.wait:

                timeout = connection.wait_future_timeout

            else:

                timeout = 0

            try:

                yield from asyncio.wait_for(
                    asyncio.shield(aggregate, loop=connection.loop),
                    timeout,
                    loop=connection.loop
                )

            except asyncio.TimeoutError:

                for future, message in futures.items():

                    if not future.done():

                        if self.fail_info is None:

                            template = "bad sequence of commands ({})"
                            info = str.format(template, message)

                        else:

                            info = self.fail_info

                        connection.response(self.fail_code, info)
                        return True

            return (yield from f(cls, connection, rest, *args))

        return wrapper


class PathConditions:
    """
    Decorator for checking paths. Available options:

    * `path_must_exists`
    * `path_must_not_exists`
    * `path_must_be_dir`
    * `path_must_be_file`

    ::

        >>> @PathConditions(
        ...     PathConditions.path_must_exists,
        ...     PathConditions.path_must_be_dir)
        ... def foo(self, connection, path):
        ...     ...
    """
    path_must_exists = ("exists", False, "path does not exists")
    path_must_not_exists = ("exists", True, "path already exists")
    path_must_be_dir = ("is_dir", False, "path is not a directory")
    path_must_be_file = ("is_file", False, "path is not a file")

    def __init__(self, *conditions):

        self.conditions = conditions

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest, *args):

            real_path, virtual_path = cls.get_paths(connection, rest)
            for name, fail, message in self.conditions:

                result = yield from asyncio.wait_for(
                    getattr(connection.path_io, name)(real_path),
                    connection.path_timeout,
                    loop=connection.loop
                )
                if result == fail:

                    connection.response("550", message)
                    return True

            return (yield from f(cls, connection, rest, *args))

        return wrapper


class PathPermissions:
    """
    Decorator for checking path permissions. There is two permissions right
    now:

    * `PathPermissions.readable`
    * `PathPermissions.writable`

    Decorator will check the permissions and return proper code and information
    to client if permission denied

    ::

        >>> @PathPermissions(
        ...     PathPermissions.readable,
        ...     PathPermissions.writable)
        ... def foo(self, connection, path):
        ...     ...
    """
    readable = "readable"
    writable = "writable"

    def __init__(self, *permissions):

        self.permissions = permissions

    def __call__(self, f):

        @asyncio.coroutine
        @functools.wraps(f)
        def wrapper(cls, connection, rest, *args):

            real_path, virtual_path = cls.get_paths(connection, rest)
            current_permission = connection.user.get_permissions(virtual_path)
            for permission in self.permissions:

                if not getattr(current_permission, permission):

                    connection.response("550", "permission denied")
                    return True

                return (yield from f(cls, connection, rest, *args))

        return wrapper


class Server(BaseServer):
    """
    FTP server.

    :param users: list of users or user manager object
    :type users: :py:class:`tuple` or :py:class:`list` of
        :py:class:`aioftp.User` or :py:class:`aioftp.server.UserManager`

    :param loop: loop to use for creating connection and binding with streams
    :type loop: :py:class:`asyncio.BaseEventLoop`

    :param block_size: bytes count for socket read operations
    :type block_size: :py:class:`int`

    :param socket_timeout: timeout for socket read and write operations
    :type socket_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param path_timeout: timeout for path-related operations (make directory,
        unlink file, etc.)
    :type path_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param idle_timeout: timeout for socket read operations, another
        words: how long user can keep silence without sending commands
    :type idle_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param wait_future_timeout: wait for data connection to establish
    :type wait_future_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param path_io_factory: factory of «path abstract layer»
    :type path_io_factory: :py:class:`aioftp.AbstractPathIO`

    :param maximum_connections: Maximum command connections per server
    :type maximum_connections: :py:class:`int`
    """
    path_facts = (
        ("st_size", "Size"),
        ("st_mtime", "Modify"),
        ("st_ctime", "Create"),
    )

    def __init__(self, users=None, *, loop=None,
                 block_size=common.default_block_size, socket_timeout=None,
                 path_timeout=None, idle_timeout=None, wait_future_timeout=1,
                 path_io_factory=pathio.AsyncPathIO, maximum_connections=None):

        if isinstance(users, UserManager):
            self.user_manager = users
        else:
            self.user_manager = MemoryUserManager(users)

        self.loop = loop or asyncio.get_event_loop()
        self.block_size = block_size
        self.socket_timeout = socket_timeout
        self.path_timeout = path_timeout
        self.idle_timeout = idle_timeout
        self.wait_future_timeout = wait_future_timeout
        self.path_io = path_io_factory(self.loop)

        self.maximum_connections = maximum_connections
        self.available_connections = AvailableConnections(maximum_connections)

    def get_paths(self, connection, path):
        """
        Return *real* and *virtual* paths, resolves ".." with "up" action.
        *Real* path is path for path_io, when *virtual* deals with
        "user-view" and user requests

        :param connection: internal options for current connected user
        :type connection: :py:class:`dict`

        :param path: received path from user
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :return: (real_path, virtual_path)
        :rtype: (:py:class:`pathlib.Path`, :py:class:`pathlib.PurePosixPath`)
        """
        virtual_path = pathlib.PurePosixPath(path)
        if not virtual_path.is_absolute():

            virtual_path = connection.current_directory / virtual_path

        resolved_virtual_path = pathlib.PurePosixPath("/")
        for part in virtual_path.parts[1:]:

            if part == "..":

                resolved_virtual_path = resolved_virtual_path.parent

            else:

                resolved_virtual_path /= part

        base_path = connection.user.base_path
        real_path = base_path / resolved_virtual_path.relative_to("/")
        return real_path, resolved_virtual_path

    @asyncio.coroutine
    def greeting(self, connection, rest):

        if self.available_connections.locked():

            ok, code, info = False, "421", "Too many connections"

        else:

            ok, code, info = True, "220", "welcome"
            connection.acquired = True
            self.available_connections.acquire()

        connection.response(code, info)
        return ok

    @asyncio.coroutine
    def user(self, connection, rest):

        ok = False
        try:

            args = yield from self.user_manager.get_user(rest)
            connection.user, connection.logged, code, info = args
            connection.current_directory = connection.user.home_path
            ok = True

        except IndexError as e:

            code, info = e.args

        connection.response(code, info)
        return ok

    @ConnectionConditions(ConnectionConditions.user_required)
    @asyncio.coroutine
    def pass_(self, connection, rest):

        if (yield from self.user_manager.authenticate(connection.user, rest)):

            connection.logged = True
            code, info = "230", "normal login"

        else:

            code, info = "530", "wrong password"

        connection.response(code, info)
        return True

    @asyncio.coroutine
    def quit(self, connection, rest):

        connection.response("221", "bye")
        return False

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def pwd(self, connection, rest):

        code, info = "257", str.format("\"{}\"", connection.current_directory)
        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def cwd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.current_directory = virtual_path
        connection.response("250", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def cdup(self, connection, rest):

        parent = connection.current_directory.parent
        return (yield from self.cwd(connection, parent))

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def mkd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from asyncio.wait_for(
            connection.path_io.mkdir(real_path, parents=True),
            connection.path_timeout,
            loop=connection.loop,
        )
        connection.response("257", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def rmd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from asyncio.wait_for(
            connection.path_io.rmdir(real_path),
            connection.path_timeout,
            loop=connection.loop,
        )
        connection.response("250", "")
        return True

    @asyncio.coroutine
    def build_mlsx_string(self, connection, path):

        stats = {}
        if (yield from asyncio.wait_for(connection.path_io.is_file(path),
                                        connection.path_timeout,
                                        loop=connection.loop)):

            stats["Type"] = "file"

        elif (yield from asyncio.wait_for(connection.path_io.is_dir(path),
                                          connection.path_timeout,
                                          loop=connection.loop)):

            stats["Type"] = "dir"

        else:

            raise errors.PathIsNotFileOrDir(path)

        raw = yield from asyncio.wait_for(
            connection.path_io.stat(path),
            connection.path_timeout,
            loop=connection.loop,
        )
        for attr, fact in Server.path_facts:

            stats[fact] = getattr(raw, attr)

        s = ""
        for fact, value in stats.items():

            s += str.format("{}={};", fact, value)

        s += " " + path.name
        return s

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def mlsd(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @asyncio.coroutine
        def mlsd_worker(self, connection, rest):

            data_reader, data_writer = connection.data_connection
            del connection.data_connection
            with contextlib.closing(data_writer) as data_writer:

                paths = yield from asyncio.wait_for(
                    connection.path_io.list(real_path),
                    connection.path_timeout,
                    loop=connection.loop,
                )
                for path in paths:

                    s = yield from self.build_mlsx_string(connection, path)
                    message = s + common.end_of_line
                    data_writer.write(str.encode(message, "utf-8"))
                    yield from asyncio.wait_for(
                        data_writer.drain(),
                        connection.socket_timeout,
                        loop=connection.loop,
                    )

            connection.response("200", "mlsd data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.extra_workers.add(mlsd_worker(self, connection, rest))
        connection.response("150", "mlsd transfer started")
        return True

    @asyncio.coroutine
    def build_list_string(self, connection, path):

        fields = []
        is_dir = yield from asyncio.wait_for(
            connection.path_io.is_dir(path),
            connection.path_timeout,
            loop=connection.loop,
        )
        dir_flag = "d" if is_dir else "-"

        stats = yield from asyncio.wait_for(
            connection.path_io.stat(path),
            connection.path_timeout,
            loop=connection.loop,
        )
        default = list("xwr") * 3
        for i in range(9):

            if (stats.st_mode >> i) & 1 == 0:

                default[i] = "-"

        fields.append(dir_flag + str.join("", reversed(default)))
        fields.append(str(stats.st_nlink))
        fields.append("none")
        fields.append("none")
        fields.append(str(stats.st_size))

        t = datetime.datetime.fromtimestamp(stats.st_ctime)
        fields.append(t.strftime("%b %d %Y"))
        fields.append(path.name)
        s = str.join(" ", fields)
        return s

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def list(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @asyncio.coroutine
        def list_worker(self, connection, rest):

            data_reader, data_writer = connection.data_connection
            del connection.data_connection
            with contextlib.closing(data_writer) as data_writer:

                paths = yield from asyncio.wait_for(
                    connection.path_io.list(real_path),
                    connection.path_timeout,
                    loop=connection.loop,
                )

                for path in paths:

                    s = yield from self.build_list_string(connection, path)
                    message = s + common.end_of_line
                    data_writer.write(str.encode(message, "utf-8"))
                    yield from asyncio.wait_for(
                        data_writer.drain(),
                        connection.socket_timeout,
                        loop=connection.loop,
                    )

            connection.response("226", "list data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.extra_workers.add(list_worker(self, connection, rest))
        connection.response("150", "list transfer started")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def mlst(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        s = yield from self.build_mlsx_string(connection, real_path)
        connection.response("250", ["start", s, "end"], True)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def rnfr(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.rename_from = real_path
        connection.response("350", "rename from accepted")
        return True

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.rename_from_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def rnto(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        rename_from = connection.rename_from
        del connection.rename_from

        yield from asyncio.wait_for(
            connection.path_io.rename(rename_from, real_path),
            connection.path_timeout,
            loop=connection.loop,
        )
        connection.response("250", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_file)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def dele(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        yield from asyncio.wait_for(
            connection.path_io.unlink(real_path),
            connection.path_timeout,
            loop=connection.loop,
        )
        connection.response("250", "")
        return True

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started)
    @PathPermissions(PathPermissions.writable)
    @asyncio.coroutine
    def stor(self, connection, rest, mode="wb"):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @asyncio.coroutine
        def stor_worker(self, connection, rest):

            data_reader, data_writer = connection.data_connection
            del connection.data_connection
            try:

                fout = yield from asyncio.wait_for(
                    connection.path_io.open(real_path, mode=mode),
                    connection.path_timeout,
                    loop=connection.loop,
                )
                while True:

                    data = yield from asyncio.wait_for(
                        data_reader.read(connection.block_size),
                        connection.socket_timeout,
                        loop=connection.loop,
                    )
                    if not data:

                        info = "data transfer done"
                        break

                    if connection.future.abort.done() and connection.abort:

                        connection.abort = False
                        info = "data transfer aborted"
                        break

                    yield from asyncio.wait_for(
                        connection.path_io.write(fout, data),
                        connection.path_timeout,
                        loop=connection.loop,
                    )

            finally:

                data_writer.close()
                yield from asyncio.wait_for(
                    connection.path_io.close(fout),
                    connection.path_timeout,
                    loop=connection.loop,
                )

            connection.response("226", info)
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        parent_is_dir = yield from asyncio.wait_for(
            connection.path_io.is_dir(real_path.parent),
            connection.path_timeout,
            loop=connection.loop,
        )
        if parent_is_dir:

            connection.extra_workers.add(stor_worker(self, connection, rest))
            code, info = "150", "data transfer started"

        else:

            code, info = "550", "path unreachable"

        connection.response(code, info)
        return True

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_file)
    @PathPermissions(PathPermissions.readable)
    @asyncio.coroutine
    def retr(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @asyncio.coroutine
        def retr_worker(self, connection, rest):

            data_reader, data_writer = connection.data_connection
            del connection.data_connection
            try:

                fin = yield from asyncio.wait_for(
                    connection.path_io.open(real_path, mode="rb"),
                    connection.path_timeout,
                    loop=connection.loop,
                )
                while True:

                    data = yield from asyncio.wait_for(
                        connection.path_io.read(fin, connection.block_size),
                        connection.path_timeout,
                        loop=connection.loop,
                    )
                    if not data:

                        info = "data transfer done"
                        break

                    if connection.future.abort.done() and connection.abort:

                        connection.abort = False
                        info = "data transfer aborted"
                        break

                    data_writer.write(data)
                    yield from asyncio.wait_for(
                        data_writer.drain(),
                        connection.socket_timeout,
                        loop=connection.loop,
                    )

            finally:

                data_writer.close()
                yield from asyncio.wait_for(
                    connection.path_io.close(fin),
                    connection.path_timeout,
                    loop=connection.loop,
                )

            connection.response("226", info)
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.extra_workers.add(retr_worker(self, connection, rest))
        connection.response("150", "data transfer started")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def type(self, connection, rest):

        if rest == "I":

            connection.transfer_type = rest
            code, info = "200", ""

        else:

            code, info = "502", str.format("type '{}' not implemented", rest)

        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def pasv(self, connection, rest):

        @asyncio.coroutine
        def handler(reader, writer):

            if connection.future.data_connection.done():

                writer.close()

            else:

                connection.data_connection = reader, writer

        if not connection.future.passive_server.done():

            connection.passive_server = yield from asyncio.start_server(
                handler,
                connection.server_host,
                0,
                loop=connection.loop,
            )
            code, info = "227", ["listen socket created"]

        else:

            code, info = "227", ["listen socket already exists"]

        for sock in connection.passive_server.sockets:

            if sock.family == socket.AF_INET:

                host, port = sock.getsockname()
                break

        nums = tuple(map(int, str.split(host, "."))) + (port >> 8, port & 0xff)
        info.append(str.format("({})", str.join(",", map(str, nums))))

        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @asyncio.coroutine
    def abor(self, connection, rest):

        connection.abort = True
        connection.response("150", "abort requested")
        return True

    @asyncio.coroutine
    def appe(self, connection, rest):

        return (yield from self.stor(connection, rest, "ab"))
