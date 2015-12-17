import asyncio
import pathlib
import functools
import datetime
import socket
import collections
import enum
import logging


from . import errors
from . import pathio
from .common import *  # noqa


__all__ = (
    "Permission",
    "User",
    "AbstractUserManager",
    "Connection",
    "AvailableConnections",
    "ConnectionConditions",
    "PathConditions",
    "PathPermissions",
    "Server",
)
logger = logging.getLogger("aioftp.server")


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

    :param read_speed_limit: read speed limit per user in bytes per second
    :type read_speed_limit: :py:class:`int` or :py:class:`None`

    :param write_speed_limit: write speed limit per user in bytes per second
    :type write_speed_limit: :py:class:`int` or :py:class:`None`

    :param read_speed_limit_per_connection: read speed limit per user
        connection in bytes per second
    :type read_speed_limit_per_connection: :py:class:`int` or :py:class:`None`

    :param write_speed_limit_per_connection: write speed limit per user
        connection in bytes per second
    :type write_speed_limit_per_connection: :py:class:`int` or :py:class:`None`
    """

    def __init__(self,
                 login=None,
                 password=None, *,
                 base_path=pathlib.Path("."),
                 home_path=pathlib.PurePosixPath("/"),
                 permissions=None,
                 maximum_connections=None,
                 read_speed_limit=None,
                 write_speed_limit=None,
                 read_speed_limit_per_connection=None,
                 write_speed_limit_per_connection=None):

        self.login = login
        self.password = password
        if isinstance(base_path, str):

            self.base_path = pathlib.Path(base_path)

        else:

            self.base_path = base_path

        self.home_path = pathlib.PurePosixPath(home_path)
        if not self.home_path.is_absolute():

            raise errors.PathIsNotAbsolute(home_path)

        self.permissions = permissions or [Permission()]
        self.maximum_connections = maximum_connections

        self.read_speed_limit = read_speed_limit
        self.write_speed_limit = write_speed_limit
        self.read_speed_limit_per_connection = read_speed_limit_per_connection
        self.write_speed_limit_per_connection = \
            write_speed_limit_per_connection

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
            "maximum_connections={!r}, read_speed_limit={!r}, "
            "write_speed_limit={!r}, read_speed_limit_per_connection={!r}, "
            "write_speed_limit_per_connection={!r})",
            self.__class__.__name__,
            self.login,
            self.password,
            self.base_path,
            self.home_path,
            self.permissions,
            self.maximum_connections,
            self.read_speed_limit,
            self.write_speed_limit,
            self.read_speed_limit_per_connection,
            self.write_speed_limit_per_connection
        )


class AbstractUserManager:
    """
    Abstract user manager.

    :param timeout: timeout used by `with_timeout` decorator
    :type timeout: :py:class:`float`, :py:class:`int` or :py:class:`None`

    :param loop: loop to use
    :type loop: :py:class:`asyncio.BaseEventLoop`
    """

    GetUserResponse = enum.Enum(
        "UserManagerResponse",
        "OK PASSWORD_REQUIRED ERROR"
    )

    def __init__(self, *, timeout=None, loop=None):

        self.timeout = timeout
        self.loop = loop or asyncio.get_event_loop()

    async def get_user(self, login):
        """
        :py:func:`asyncio.coroutine`

        Get user and response for USER call

        :param login: user's login
        :type login: :py:class:`str`
        """
        raise NotImplementedError

    async def authenticate(self, user, password):
        """
        :py:func:`asyncio.coroutine`

        Check if user can be authenticated with provided password

        :param user: user
        :type user: :py:class:`aioftp.User`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    async def notify_logout(self, user):
        """
        :py:func:`asyncio.coroutine`

        Called when user connection is closed if user was initiated

        :param user: user
        :type user: :py:class:`aioftp.User`
        """
        pass


class MemoryUserManager(AbstractUserManager):
    """
    A built-in user manager that keeps predefined set of users in memory.

    :param users: container of users
    :type users: :py:class:`list`, :py:class:`tuple`, etc. of
        :py:class:`aioftp.User`

    """

    def __init__(self, users, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.users = users or [User()]
        self.available_connections = dict(
            (user, AvailableConnections(user.maximum_connections))
            for user in self.users
        )

    async def get_user(self, login):

        user = None
        for u in self.users:

            if u.login is None and user is None:

                user = u

            elif u.login == login:

                user = u
                break

        if user is None:

            state = AbstractUserManager.GetUserResponse.ERROR
            info = "no such username"

        elif self.available_connections[user].locked():

            state = AbstractUserManager.GetUserResponse.ERROR
            template = "too much connections for '{}'"
            info = str.format(template, user.login or "anonymous")

        elif user.login is None:

            state = AbstractUserManager.GetUserResponse.OK
            info = "anonymous login"

        elif user.password is None:

            state = AbstractUserManager.GetUserResponse.OK
            info = "login without password"

        else:

            state = AbstractUserManager.GetUserResponse.PASSWORD_REQUIRED
            info = "password required"

        if state != AbstractUserManager.GetUserResponse.ERROR:

            self.available_connections[user].acquire()

        return state, user, info

    async def authenticate(self, user, password):

        return user.password == password

    async def notify_logout(self, user):

        self.available_connections[user].release()


class Connection(collections.defaultdict):
    """
    Connection state container for transparent work with futures for async
    wait

    :param loop: event loop
    :type loop: :py:class:`asyncio.BaseEventLoop`

    :param kwargs: initialization parameters

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

        self["loop"].set_result(loop or asyncio.get_event_loop())
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

                self[name] = super().default_factory()

            self[name].set_result(value)

    def __delattr__(self, name):

        if name in self:

            self.pop(name)


class AvailableConnections:
    """
    Semaphore-like object. Have no blocks, only raises ValueError on bounds
    crossing. If value is :py:class:`None` have no limits (bounds checks).

    :param value:
    :type value: :py:class:`int` or :py:class:`None`
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


class AbstractServer:

    async def start(self, host=None, port=0, **kwargs):
        """
        :py:func:`asyncio.coroutine`

        Start server.

        :param host: ip address to bind for listening.
        :type host: :py:class:`str`

        :param port: port number to bind for listening.
        :type port: :py:class:`int`

        :param kwargs: keyword arguments, they passed to
            :py:func:`asyncio.start_server`
        """
        self.connections = {}
        self.server_host = host
        self.server_port = port
        self.server = await asyncio.start_server(
            self.dispatcher,
            host,
            port,
            loop=self.loop,
            **kwargs
        )

        for sock in self.server.sockets:

            if sock.family == socket.AF_INET:

                host, port = sock.getsockname()
                message = str.format("serving on {}:{}", host, port)
                logger.info(message)

    def close(self):
        """
        Shutdown the server and close all connections. Use this method with
        :py:meth:`aioftp.Server.wait_closed`
        """
        self.server.close()
        for connection in self.connections.values():

            connection._dispatcher.cancel()

    async def wait_closed(self):
        """
        :py:func:`asyncio.coroutine`

        Wait server to stop.
        """
        await self.server.wait_closed()

    async def write_line(self, stream, line, encoding="utf-8"):

        logger.info(line)
        await stream.write(str.encode(line + END_OF_LINE, encoding=encoding))

    async def write_response(self, stream, code, lines="", list=False):
        """
        :py:func:`asyncio.coroutine`

        Complex method for sending response.

        :param stream: command connection stream
        :type stream: :py:class:`aioftp.StreamIO`

        :param code: server response code
        :type code: :py:class:`str`

        :param lines: line or lines, which are response information
        :type lines: :py:class:`str` or :py:class:`collections.Iterable`

        :param list: if true, then lines will be sended without code prefix.
            This is useful for **LIST** FTP command and some others.
        :type list: :py:class:`bool`
        """
        lines = wrap_with_container(lines)
        write = functools.partial(self.write_line, stream)
        if list:

            head, *body, tail = lines
            await write(code + "-" + head)
            for line in body:

                await write(" " + line)

            await write(code + " " + tail)

        else:

            *body, tail = lines
            for line in body:

                await write(code + "-" + line)

            await write(code + " " + tail)

    async def parse_command(self, stream):
        """
        :py:func:`asyncio.coroutine`

        Complex method for getting command.

        :param stream: connection steram
        :type stream: :py:class:`asyncio.StreamIO`

        :return: (code, rest)
        :rtype: (:py:class:`str`, :py:class:`str`)
        """
        line = await stream.readline()
        if not line:

            raise ConnectionResetError

        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        logger.info(s)
        cmd, _, rest = str.partition(s, " ")
        return str.lower(cmd), rest

    async def response_writer(self, stream, response_queue):
        """
        :py:func:`asyncio.coroutine`

        Worker for write_response with current connection. Get data to response
        from queue, this is for right order of responses. Exits if received
        :py:class:`None`.

        :param stream: command connection stream
        :type connection: :py:class:`aioftp.StreamIO`

        :param response_queue:
        :type response_queue: :py:class:`asyncio.Queue`
        """
        while True:

            args = await response_queue.get()
            try:

                await self.write_response(stream, *args)

            finally:

                response_queue.task_done()

    async def dispatcher(self, reader, writer):

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

    :param fail_info: return information string if failure. If
        :py:class:`None`, then use default string
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

        @functools.wraps(f)
        async def wrapper(cls, connection, rest, *args):

            futures = {connection[name]: msg for name, msg in self.fields}
            aggregate = asyncio.gather(*futures, loop=connection.loop)

            if self.wait:

                timeout = connection.wait_future_timeout

            else:

                timeout = 0

            try:

                await asyncio.wait_for(
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

            return await f(cls, connection, rest, *args)

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

        @functools.wraps(f)
        async def wrapper(cls, connection, rest, *args):

            real_path, virtual_path = cls.get_paths(connection, rest)
            for name, fail, message in self.conditions:

                coro = getattr(connection.path_io, name)
                if await coro(real_path) == fail:

                    connection.response("550", message)
                    return True

            return await f(cls, connection, rest, *args)

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

        @functools.wraps(f)
        async def wrapper(cls, connection, rest, *args):

            real_path, virtual_path = cls.get_paths(connection, rest)
            current_permission = connection.user.get_permissions(virtual_path)
            for permission in self.permissions:

                if not getattr(current_permission, permission):

                    connection.response("550", "permission denied")
                    return True

                return await f(cls, connection, rest, *args)

        return wrapper


def worker(f):
    """
    Decorator. Abortable worker. If wrapped task will be cancelled by
    dispatcher, decorator will send ftp codes of successful interrupt.

    ::

        >>> @worker
        ... async def worker(self, connection, rest):
        ...     ...

    """

    @functools.wraps(f)
    async def wrapper(cls, connection, rest):

        try:

            await f(cls, connection, rest)

        except asyncio.CancelledError:

            connection.response("426", "transfer aborted")
            connection.response("226", "abort successful")

    return wrapper


class Server(AbstractServer):
    """
    FTP server.

    :param users: list of users or user manager object
    :type users: :py:class:`tuple` or :py:class:`list` of
        :py:class:`aioftp.User` or instance of
        :py:class:`aioftp.AbstractUserManager` subclass

    :param loop: loop to use for creating connection and binding with streams
    :type loop: :py:class:`asyncio.BaseEventLoop`

    :param block_size: bytes count for socket read operations
    :type block_size: :py:class:`int`

    :param socket_timeout: timeout for socket read and write operations
    :type socket_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param idle_timeout: timeout for socket read operations, another
        words: how long user can keep silence without sending commands
    :type idle_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param wait_future_timeout: wait for data connection to establish
    :type wait_future_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param path_timeout: timeout for path-related operations (make directory,
        unlink file, etc.)
    :type path_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param path_io_factory: factory of «path abstract layer»
    :type path_io_factory: :py:class:`aioftp.AbstractPathIO`

    :param maximum_connections: Maximum command connections per server
    :type maximum_connections: :py:class:`int`

    :param read_speed_limit: server read speed limit in bytes per second
    :type read_speed_limit: :py:class:`int` or :py:class:`None`

    :param write_speed_limit: server write speed limit in bytes per second
    :type write_speed_limit: :py:class:`int` or :py:class:`None`

    :param read_speed_limit_per_connection: server read speed limit per
        connection in bytes per second
    :type read_speed_limit_per_connection: :py:class:`int` or :py:class:`None`

    :param write_speed_limit_per_connection: server write speed limit per
        connection in bytes per second
    :type write_speed_limit_per_connection: :py:class:`int` or :py:class:`None`
    """
    path_facts = (
        ("st_size", "Size"),
        ("st_mtime", "Modify"),
        ("st_ctime", "Create"),
    )

    def __init__(self,
                 users=None,
                 *,
                 loop=None,
                 block_size=DEFAULT_BLOCK_SIZE,
                 socket_timeout=None,
                 idle_timeout=None,
                 wait_future_timeout=1,
                 path_timeout=None,
                 path_io_factory=pathio.AsyncPathIO,
                 maximum_connections=None,
                 read_speed_limit=None,
                 write_speed_limit=None,
                 read_speed_limit_per_connection=None,
                 write_speed_limit_per_connection=None):

        self.loop = loop or asyncio.get_event_loop()
        self.block_size = block_size
        self.socket_timeout = socket_timeout
        self.idle_timeout = idle_timeout
        self.wait_future_timeout = wait_future_timeout
        self.path_io = path_io_factory(timeout=path_timeout, loop=self.loop)

        if isinstance(users, AbstractUserManager):

            self.user_manager = users

        else:

            self.user_manager = MemoryUserManager(users, loop=self.loop)

        self.available_connections = AvailableConnections(maximum_connections)

        self.throttle = StreamThrottle.from_limits(
            read_speed_limit,
            write_speed_limit,
            loop=self.loop
        )
        self.throttle_per_connection = StreamThrottle.from_limits(
            read_speed_limit_per_connection,
            write_speed_limit_per_connection,
            loop=self.loop
        )
        self.throttle_per_user = {}

    async def dispatcher(self, reader, writer):

        host, port = writer.transport.get_extra_info("peername", ("", ""))
        message = str.format("new connection from {}:{}", host, port)
        logger.info(message)

        key = stream = ThrottleStreamIO(
            reader,
            writer,
            throttles=dict(
                server_global=self.throttle,
                server_per_connection=self.throttle_per_connection.clone()
            ),
            read_timeout=self.idle_timeout,
            write_timeout=self.socket_timeout,
            loop=self.loop
        )
        response_queue = asyncio.Queue(loop=self.loop)
        connection = Connection(
            client_host=host,
            client_port=port,
            server_host=self.server_host,
            server_port=self.server_port,
            command_connection=stream,
            socket_timeout=self.socket_timeout,
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
            self.response_writer(stream, response_queue),
            self.parse_command(stream),
        }
        self.connections[key] = connection

        try:

            while True:

                done, pending = await asyncio.wait(
                    pending | connection.extra_workers,
                    return_when=asyncio.FIRST_COMPLETED,
                    loop=connection.loop
                )
                connection.extra_workers -= done

                for task in done:

                    try:

                        try:

                            result = task.result()

                        except:

                            logger.exception("dispatcher caught exception")
                            raise

                    except errors.PathIOError:

                        connection.response("451", "file system error")
                        continue

                    # this is "command" result
                    if isinstance(result, bool):

                        if not result:

                            await response_queue.join()
                            return

                    # this is parse_command result
                    elif isinstance(result, tuple):

                        pending.add(self.parse_command(stream))

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
            logger.info(message)

            if not connection.loop.is_closed():

                for task in pending | connection.extra_workers:

                    if isinstance(task, asyncio.Task):

                        task.cancel()

                if connection.future.passive_server.done():

                    connection.passive_server.close()

                if connection.future.data_connection.done():

                    connection.data_connection.close()

                stream.close()

            if connection.acquired:

                self.available_connections.release()

            if connection.future.user.done():

                await self.user_manager.notify_logout(connection.user)

            self.connections.pop(key)

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

    async def greeting(self, connection, rest):

        if self.available_connections.locked():

            ok, code, info = False, "421", "Too many connections"

        else:

            ok, code, info = True, "220", "welcome"
            connection.acquired = True
            self.available_connections.acquire()

        connection.response(code, info)
        return ok

    async def user(self, connection, rest):

        if connection.future.user.done():

            await self.user_manager.notify_logout(connection.user)

        del connection.user
        del connection.logged

        state, user, info = await self.user_manager.get_user(rest)
        if state == AbstractUserManager.GetUserResponse.OK:

            code = "230"
            connection.logged = True
            connection.user = user

        elif state == AbstractUserManager.GetUserResponse.PASSWORD_REQUIRED:

            code = "331"
            connection.user = user

        elif state == AbstractUserManager.GetUserResponse.ERROR:

            code = "530"

        else:

            message = str.format("Unknown response {}", state)
            raise NotImplementedError(message)

        if connection.future.user.done():

            connection.current_directory = connection.user.home_path

            if connection.user not in self.throttle_per_user:

                throttle = StreamThrottle.from_limits(
                    connection.user.read_speed_limit,
                    connection.user.write_speed_limit,
                    loop=connection.loop
                )
                self.throttle_per_user[connection.user] = throttle

            connection.command_connection.throttles.update(
                user_global=self.throttle_per_user[connection.user],
                user_per_connection=StreamThrottle.from_limits(
                    connection.user.read_speed_limit_per_connection,
                    connection.user.write_speed_limit_per_connection,
                    loop=connection.loop
                )
            )

        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.user_required)
    async def pass_(self, connection, rest):

        auth = self.user_manager.authenticate(connection.user, rest)
        if connection.future.logged.done():

            code, info = "503", "already logged in"

        elif await auth:

            connection.logged = True
            code, info = "230", "normal login"

        else:

            code, info = "530", "wrong password"

        connection.response(code, info)
        return True

    async def quit(self, connection, rest):

        connection.response("221", "bye")
        return False

    @ConnectionConditions(ConnectionConditions.login_required)
    async def pwd(self, connection, rest):

        code, info = "257", str.format("\"{}\"", connection.current_directory)
        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.readable)
    async def cwd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.current_directory = virtual_path
        connection.response("250", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def cdup(self, connection, rest):

        return await self.cwd(connection, connection.current_directory.parent)

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    async def mkd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        await connection.path_io.mkdir(real_path, parents=True)
        connection.response("257", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_dir)
    @PathPermissions(PathPermissions.writable)
    async def rmd(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        await connection.path_io.rmdir(real_path)
        connection.response("250", "")
        return True

    async def build_mlsx_string(self, connection, path):

        stats = {}
        if await connection.path_io.is_file(path):

            stats["Type"] = "file"

        elif await connection.path_io.is_dir(path):

            stats["Type"] = "dir"

        else:

            raise errors.PathIsNotFileOrDir(path)

        raw = await connection.path_io.stat(path)
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
    async def mlsd(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @worker
        async def mlsd_worker(self, connection, rest):

            stream = connection.data_connection
            del connection.data_connection

            async with stream:

                async for path in connection.path_io.list(real_path):

                    s = await self.build_mlsx_string(connection, path)
                    await stream.write(str.encode(s + END_OF_LINE, "utf-8"))

            connection.response("200", "mlsd transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = mlsd_worker(self, connection, rest)
        task = connection.loop.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "mlsd transfer started")
        return True

    async def build_list_string(self, connection, path):

        fields = []
        is_dir = await connection.path_io.is_dir(path)
        dir_flag = "d" if is_dir else "-"

        stats = await connection.path_io.stat(path)
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
    async def list(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @worker
        async def list_worker(self, connection, rest):

            stream = connection.data_connection
            del connection.data_connection

            async with stream:

                async for path in connection.path_io.list(real_path):

                    s = await self.build_list_string(connection, path)
                    await stream.write(str.encode(s + END_OF_LINE, "utf-8"))

            connection.response("226", "list transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = list_worker(self, connection, rest)
        task = connection.loop.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "list transfer started")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.readable)
    async def mlst(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        s = await self.build_mlsx_string(connection, real_path)
        connection.response("250", ["start", s, "end"], True)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(PathConditions.path_must_exists)
    @PathPermissions(PathPermissions.writable)
    async def rnfr(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        connection.rename_from = real_path
        connection.response("350", "rename from accepted")
        return True

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.rename_from_required)
    @PathConditions(PathConditions.path_must_not_exists)
    @PathPermissions(PathPermissions.writable)
    async def rnto(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        rename_from = connection.rename_from
        del connection.rename_from

        await connection.path_io.rename(rename_from, real_path)
        connection.response("250", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    @PathConditions(
        PathConditions.path_must_exists,
        PathConditions.path_must_be_file)
    @PathPermissions(PathPermissions.writable)
    async def dele(self, connection, rest):

        real_path, virtual_path = self.get_paths(connection, rest)
        await connection.path_io.unlink(real_path)
        connection.response("250", "")
        return True

    @ConnectionConditions(
        ConnectionConditions.login_required,
        ConnectionConditions.passive_server_started)
    @PathPermissions(PathPermissions.writable)
    async def stor(self, connection, rest, mode="wb"):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @worker
        async def stor_worker(self, connection, rest):

            stream = connection.data_connection
            del connection.data_connection

            file_out = connection.path_io.open(real_path, mode=mode)
            async with file_out, stream:

                async for data in stream.iter_by_block(connection.block_size):

                    await file_out.write(data)

            connection.response("226", "data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        if await connection.path_io.is_dir(real_path.parent):

            coro = stor_worker(self, connection, rest)
            task = connection.loop.create_task(coro)
            connection.extra_workers.add(task)
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
    async def retr(self, connection, rest):

        @ConnectionConditions(
            ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @worker
        async def retr_worker(self, connection, rest):

            stream = connection.data_connection
            del connection.data_connection

            file_in = connection.path_io.open(real_path, mode="rb")
            async with file_in, stream:

                async for data in file_in.iter_by_block(connection.block_size):

                    await stream.write(data)

            connection.response("226", "data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = retr_worker(self, connection, rest)
        task = connection.loop.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "data transfer started")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def type(self, connection, rest):

        if rest == "I":

            connection.transfer_type = rest
            code, info = "200", ""

        else:

            code, info = "502", str.format("type '{}' not implemented", rest)

        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def pasv(self, connection, rest):

        async def handler(reader, writer):

            if connection.future.data_connection.done():

                writer.close()

            else:

                connection.data_connection = ThrottleStreamIO(
                    reader,
                    writer,
                    throttles=connection.command_connection.throttles,
                    timeout=connection.socket_timeout,
                    loop=connection.loop
                )

        if not connection.future.passive_server.done():

            connection.passive_server = await asyncio.start_server(
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
    async def abor(self, connection, rest):

        if connection.extra_workers:

            for worker in connection.extra_workers:

                worker.cancel()

        else:

            connection.response("226", "nothing to abort")

        return True

    async def appe(self, connection, rest):

        return await self.stor(connection, rest, "ab")
