import abc
import asyncio
import collections
import enum
import errno
import functools
import logging
import pathlib
import socket
import stat
import sys
import time

from . import errors, pathio
from .common import (
    DEFAULT_BLOCK_SIZE,
    END_OF_LINE,
    HALF_OF_YEAR_IN_SECONDS,
    StreamThrottle,
    ThrottleStreamIO,
    setlocale,
    wrap_with_container,
)

__all__ = (
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
    "Server",
)

IS_PY37_PLUS = sys.version_info[:2] >= (3, 7)
if IS_PY37_PLUS:
    get_current_task = asyncio.current_task
else:
    get_current_task = asyncio.Task.current_task

logger = logging.getLogger(__name__)


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
        return f"{self.__class__.__name__}({self.path!r}, " \
               f"readable={self.readable!r}, writable={self.writable!r})"


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
        self.base_path = pathlib.Path(base_path)
        self.home_path = pathlib.PurePosixPath(home_path)
        if not self.home_path.is_absolute():
            raise errors.PathIsNotAbsolute(home_path)
        self.permissions = permissions or [Permission()]
        self.maximum_connections = maximum_connections
        self.read_speed_limit = read_speed_limit
        self.write_speed_limit = write_speed_limit
        self.read_speed_limit_per_connection = read_speed_limit_per_connection
        # damn 80 symbols
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
        return f"{self.__class__.__name__}({self.login!r}, " \
               f"{self.password!r}, base_path={self.base_path!r}, " \
               f"home_path={self.home_path!r}, " \
               f"permissions={self.permissions!r}, " \
               f"maximum_connections={self.maximum_connections!r}, " \
               f"read_speed_limit={self.read_speed_limit!r}, " \
               f"write_speed_limit={self.write_speed_limit!r}, " \
               f"read_speed_limit_per_connection=" \
               f"{self.read_speed_limit_per_connection!r}, " \
               f"write_speed_limit_per_connection=" \
               f"{self.write_speed_limit_per_connection!r})"


class AbstractUserManager(abc.ABC):
    """
    Abstract user manager.

    :param timeout: timeout used by `with_timeout` decorator
    :type timeout: :py:class:`float`, :py:class:`int` or :py:class:`None`
    """

    GetUserResponse = enum.Enum(
        "UserManagerResponse",
        "OK PASSWORD_REQUIRED ERROR"
    )

    def __init__(self, *, timeout=None):
        self.timeout = timeout

    @abc.abstractmethod
    async def get_user(self, login):
        """
        :py:func:`asyncio.coroutine`

        Get user and response for USER call

        :param login: user's login
        :type login: :py:class:`str`
        """

    @abc.abstractmethod
    async def authenticate(self, user, password):
        """
        :py:func:`asyncio.coroutine`

        Check if user can be authenticated with provided password

        :param user: user
        :type user: :py:class:`aioftp.User`

        :param password: password
        :type password: :py:class:`str`

        :rtype: :py:class:`bool`
        """

    async def notify_logout(self, user):
        """
        :py:func:`asyncio.coroutine`

        Called when user connection is closed if user was initiated

        :param user: user
        :type user: :py:class:`aioftp.User`
        """


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
            info = f"too much connections for {user.login or 'anonymous'!r}"
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

    def __init__(self, **kwargs):
        super().__init__(asyncio.Future)
        self.future = Connection.Container(self)
        for k, v in kwargs.items():
            self[k].set_result(v)

    def __getattr__(self, name):
        if name in self:
            return self[name].result()
        else:
            raise AttributeError(f"{name!r} not in storage")

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
                raise ValueError("Too many acquires")

    def release(self):
        """
        Release, incrementing the internal counter by one.
        """
        if self.value is not None:
            self.value += 1
            if self.value > self.maximum_value:
                raise ValueError("Too many releases")


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
            aggregate = asyncio.gather(*futures)
            if self.wait:
                timeout = connection.wait_future_timeout
            else:
                timeout = 0

            try:
                await asyncio.wait_for(
                    asyncio.shield(aggregate),
                    timeout,
                )
            except asyncio.TimeoutError:
                for future, message in futures.items():
                    if not future.done():
                        if self.fail_info is None:
                            info = f"bad sequence of commands ({message})"
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


class Server:
    """
    FTP server.

    :param users: list of users or user manager object
    :type users: :py:class:`tuple` or :py:class:`list` of
        :py:class:`aioftp.User` or instance of
        :py:class:`aioftp.AbstractUserManager` subclass

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

    :param data_ports: port numbers that are available for passive connections
    :type data_ports: :py:class:`collections.Iterable` or :py:class:`None`

    :param encoding: encoding to use for convertion strings to bytes
    :type encoding: :py:class:`str`

    :param ssl: can be set to an :py:class:`ssl.SSLContext` instance
        to enable TLS over the accepted connections.
        Please look :py:meth:`asyncio.loop.create_server` docs.
    :type ssl: :py:class:`ssl.SSLContext`
    """
    def __init__(self,
                 users=None,
                 *,
                 block_size=DEFAULT_BLOCK_SIZE,
                 socket_timeout=None,
                 idle_timeout=None,
                 wait_future_timeout=1,
                 path_timeout=None,
                 path_io_factory=pathio.PathIO,
                 maximum_connections=None,
                 read_speed_limit=None,
                 write_speed_limit=None,
                 read_speed_limit_per_connection=None,
                 write_speed_limit_per_connection=None,
                 data_ports=None,
                 encoding="utf-8",
                 ssl=None):
        self.block_size = block_size
        self.socket_timeout = socket_timeout
        self.idle_timeout = idle_timeout
        self.wait_future_timeout = wait_future_timeout
        self.path_io_factory = pathio.PathIONursery(path_io_factory)
        self.path_timeout = path_timeout
        if data_ports is not None:
            self.available_data_ports = asyncio.PriorityQueue()
            for data_port in data_ports:
                self.available_data_ports.put_nowait((0, data_port))
        else:
            self.available_data_ports = None

        if isinstance(users, AbstractUserManager):
            self.user_manager = users
        else:
            self.user_manager = MemoryUserManager(users)

        self.available_connections = AvailableConnections(maximum_connections)
        self.throttle = StreamThrottle.from_limits(
            read_speed_limit,
            write_speed_limit,
        )
        self.throttle_per_connection = StreamThrottle.from_limits(
            read_speed_limit_per_connection,
            write_speed_limit_per_connection,
        )
        self.throttle_per_user = {}
        self.encoding = encoding
        self.ssl = ssl
        self.commands_mapping = {
            "abor": self.abor,
            "appe": self.appe,
            "cdup": self.cdup,
            "cwd": self.cwd,
            "dele": self.dele,
            "epsv": self.epsv,
            "list": self.list,
            "mkd": self.mkd,
            "mlsd": self.mlsd,
            "mlst": self.mlst,
            "pass": self.pass_,
            "pasv": self.pasv,
            "pbsz": self.pbsz,
            "prot": self.prot,
            "pwd": self.pwd,
            "quit": self.quit,
            "rest": self.rest,
            "retr": self.retr,
            "rmd": self.rmd,
            "rnfr": self.rnfr,
            "rnto": self.rnto,
            "stor": self.stor,
            "syst": self.syst,
            "type": self.type,
            "user": self.user,
        }

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
        self._start_server_extra_arguments = kwargs
        self.connections = {}
        self.server_host = host
        self.server_port = port
        self.server = await asyncio.start_server(
            self.dispatcher,
            host,
            port,
            ssl=self.ssl,
            **self._start_server_extra_arguments,
        )
        for sock in self.server.sockets:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                host, port, *_ = sock.getsockname()
                if not self.server_port:
                    self.server_port = port
                if not self.server_host:
                    self.server_host = host
                logger.info("serving on %s:%s", host, port)

    async def serve_forever(self):
        """
        :py:func:`asyncio.coroutine`

        Proxy to :py:class:`asyncio.Server` `serve_forever` method.
        """
        return await self.server.serve_forever()

    async def run(self, host=None, port=0, **kwargs):
        """
        :py:func:`asyncio.coroutine`

        Single entrypoint to start, serve and close.

        :param host: ip address to bind for listening.
        :type host: :py:class:`str`

        :param port: port number to bind for listening.
        :type port: :py:class:`int`

        :param kwargs: keyword arguments, they passed to
            :py:func:`asyncio.start_server`
        """
        await self.start(host=host, port=port, **kwargs)
        try:
            await self.serve_forever()
        finally:
            await self.close()

    @property
    def address(self):
        """
        Server listen socket host and port as :py:class:`tuple`
        """
        return self.server_host, self.server_port

    async def close(self):
        """
        :py:func:`asyncio.coroutine`

        Shutdown the server and close all connections.
        """
        self.server.close()
        tasks = [asyncio.create_task(self.server.wait_closed())]
        for connection in self.connections.values():
            connection._dispatcher.cancel()
            tasks.append(connection._dispatcher)
        logger.debug("waiting for %d tasks", len(tasks))
        await asyncio.wait(tasks)

    async def write_line(self, stream, line):
        logger.debug(line)
        await stream.write((line + END_OF_LINE).encode(encoding=self.encoding))

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

    async def parse_command(self, stream, censor_commands=("pass",)):
        """
        :py:func:`asyncio.coroutine`

        Complex method for getting command.

        :param stream: connection stream
        :type stream: :py:class:`asyncio.StreamIO`

        :param censor_commands: An optional list of commands to censor.
        :type censor_commands: :py:class:`tuple` of :py:class:`str`

        :return: (code, rest)
        :rtype: (:py:class:`str`, :py:class:`str`)
        """
        line = await stream.readline()
        if not line:
            raise ConnectionResetError
        s = line.decode(encoding=self.encoding).rstrip()
        cmd, _, rest = s.partition(" ")

        if cmd.lower() in censor_commands:
            stars = "*" * len(rest)
            logger.debug("%s %s", cmd, stars)
        else:
            logger.debug("%s %s", cmd, rest)

        return cmd.lower(), rest

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
        """
        :py:func:`asyncio.coroutine`

        Server connection handler (main routine per user).
        """
        host, port, *_ = writer.transport.get_extra_info("peername", ("", ""))
        current_server_host, *_ = writer.transport.get_extra_info("sockname")
        logger.info("new connection from %s:%s", host, port)
        key = stream = ThrottleStreamIO(
            reader,
            writer,
            throttles=dict(
                server_global=self.throttle,
                server_per_connection=self.throttle_per_connection.clone()
            ),
            read_timeout=self.idle_timeout,
            write_timeout=self.socket_timeout,
        )
        response_queue = asyncio.Queue()
        connection = Connection(
            client_host=host,
            client_port=port,
            server_host=current_server_host,
            passive_server_port=0,
            server_port=self.server_port,
            command_connection=stream,
            socket_timeout=self.socket_timeout,
            idle_timeout=self.idle_timeout,
            wait_future_timeout=self.wait_future_timeout,
            block_size=self.block_size,
            path_io_factory=self.path_io_factory,
            path_timeout=self.path_timeout,
            extra_workers=set(),
            response=lambda *args: response_queue.put_nowait(args),
            acquired=False,
            restart_offset=0,
            _dispatcher=get_current_task(),
        )
        connection.path_io = self.path_io_factory(timeout=self.path_timeout,
                                                  connection=connection)
        pending = {
            asyncio.create_task(self.greeting(connection, "")),
            asyncio.create_task(self.response_writer(stream, response_queue)),
            asyncio.create_task(self.parse_command(stream)),
        }
        self.connections[key] = connection
        try:
            while True:
                done, pending = await asyncio.wait(
                    pending | connection.extra_workers,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                connection.extra_workers -= done
                for task in done:
                    try:
                        result = task.result()
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
                        pending.add(
                            asyncio.create_task(self.parse_command(stream))
                        )
                        cmd, rest = result
                        f = self.commands_mapping.get(cmd)
                        if f is not None:
                            pending.add(
                                asyncio.create_task(f(connection, rest))
                            )
                            if cmd not in ("retr", "stor", "appe"):
                                connection.restart_offset = 0
                        else:
                            message = f"{cmd!r} not implemented"
                            connection.response("502", message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("dispatcher caught exception")
        finally:
            logger.info("closing connection from %s:%s", host, port)
            tasks_to_wait = []
            if not asyncio.get_running_loop().is_closed():
                for task in pending | connection.extra_workers:
                    task.cancel()
                    tasks_to_wait.append(task)
                if connection.future.passive_server.done():
                    connection.passive_server.close()
                    if self.available_data_ports is not None:
                        port = connection.passive_server_port
                        self.available_data_ports.put_nowait((0, port))
                if connection.future.data_connection.done():
                    connection.data_connection.close()
                stream.close()
            if connection.acquired:
                self.available_connections.release()
            if connection.future.user.done():
                task = asyncio.create_task(
                    self.user_manager.notify_logout(connection.user)
                )
                tasks_to_wait.append(task)
            self.connections.pop(key)
            if tasks_to_wait:
                await asyncio.wait(tasks_to_wait)

    @staticmethod
    def get_paths(connection, path):
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
        # replace with `is_relative_to` check after 3.9+ requirements lands
        try:
            real_path.relative_to(base_path)
        except ValueError:
            real_path = base_path
            resolved_virtual_path = pathlib.PurePosixPath("/")
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
            message = f"Unknown response {state}"
            raise NotImplementedError(message)

        if connection.future.user.done():
            connection.current_directory = connection.user.home_path
            if connection.user not in self.throttle_per_user:
                throttle = StreamThrottle.from_limits(
                    connection.user.read_speed_limit,
                    connection.user.write_speed_limit,
                )
                self.throttle_per_user[connection.user] = throttle

            connection.command_connection.throttles.update(
                user_global=self.throttle_per_user[connection.user],
                user_per_connection=StreamThrottle.from_limits(
                    connection.user.read_speed_limit_per_connection,
                    connection.user.write_speed_limit_per_connection,
                )
            )
        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.user_required)
    async def pass_(self, connection, rest):
        if connection.future.logged.done():
            code, info = "503", "already logged in"
        elif await self.user_manager.authenticate(connection.user, rest):
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
        code, info = "257", f"\"{connection.current_directory}\""
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

    @staticmethod
    def _format_mlsx_time(local_seconds):
        return time.strftime("%Y%m%d%H%M%S", time.gmtime(local_seconds))

    def _build_mlsx_facts_from_stats(self, stats):
        return {
            "Size": stats.st_size,
            "Create": self._format_mlsx_time(stats.st_ctime),
            "Modify": self._format_mlsx_time(stats.st_mtime),
        }

    async def build_mlsx_string(self, connection, path):
        if not await connection.path_io.exists(path):
            facts = {}
        else:
            stats = await connection.path_io.stat(path)
            facts = self._build_mlsx_facts_from_stats(stats)
        if await connection.path_io.is_file(path):
            facts["Type"] = "file"
        elif await connection.path_io.is_dir(path):
            facts["Type"] = "dir"
        else:
            facts["Type"] = "unknown"

        s = ""
        for name, value in facts.items():
            s += f"{name}={value};"
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
                    b = (s + END_OF_LINE).encode(encoding=self.encoding)
                    await stream.write(b)
            connection.response("200", "mlsd transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = mlsd_worker(self, connection, rest)
        task = asyncio.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "mlsd transfer started")
        return True

    @staticmethod
    def build_list_mtime(st_mtime, now=None):
        if now is None:
            now = time.time()
        mtime = time.localtime(st_mtime)
        with setlocale("C"):
            if now - HALF_OF_YEAR_IN_SECONDS < st_mtime <= now:
                s = time.strftime("%b %e %H:%M", mtime)
            else:
                s = time.strftime("%b %e  %Y", mtime)
        return s

    async def build_list_string(self, connection, path):
        stats = await connection.path_io.stat(path)
        mtime = self.build_list_mtime(stats.st_mtime)
        fields = (
            stat.filemode(stats.st_mode),
            str(stats.st_nlink),
            "none",
            "none",
            str(stats.st_size),
            mtime,
            path.name
        )
        s = " ".join(fields)
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
                    b = (s + END_OF_LINE).encode(encoding=self.encoding)
                    await stream.write(b)
            connection.response("226", "list transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = list_worker(self, connection, rest)
        task = asyncio.create_task(coro)
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
            if connection.restart_offset:
                file_mode = "r+b"
            else:
                file_mode = mode
            file_out = connection.path_io.open(real_path, mode=file_mode)
            async with file_out, stream:
                if connection.restart_offset:
                    await file_out.seek(connection.restart_offset)
                async for data in stream.iter_by_block(connection.block_size):
                    await file_out.write(data)
            connection.response("226", "data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        if await connection.path_io.is_dir(real_path.parent):
            coro = stor_worker(self, connection, rest)
            task = asyncio.create_task(coro)
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
                if connection.restart_offset:
                    await file_in.seek(connection.restart_offset)
                async for data in file_in.iter_by_block(connection.block_size):
                    await stream.write(data)
            connection.response("226", "data transfer done")
            return True

        real_path, virtual_path = self.get_paths(connection, rest)
        coro = retr_worker(self, connection, rest)
        task = asyncio.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "data transfer started")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def type(self, connection, rest):
        if rest in ("I", "A"):
            connection.transfer_type = rest
            code, info = "200", ""
        else:
            code, info = "502", f"type {rest!r} not implemented"
        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def pbsz(self, connection, rest):
        connection.response("200", "")
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def prot(self, connection, rest):
        if rest == "P":
            code, info = "200", ""
        else:
            code, info = "502", ""
        connection.response(code, info)
        return True

    async def _start_passive_server(self, connection, handler_callback):
        if self.available_data_ports is not None:
            viewed_ports = set()
            while True:
                try:
                    priority, port = self.available_data_ports.get_nowait()
                    if port in viewed_ports:
                        raise errors.NoAvailablePort
                    viewed_ports.add(port)
                    passive_server = await asyncio.start_server(
                        handler_callback,
                        connection.server_host,
                        port,
                        ssl=self.ssl,
                        **self._start_server_extra_arguments,
                    )
                    connection.passive_server_port = port
                    break
                except asyncio.QueueEmpty:
                    raise errors.NoAvailablePort
                except OSError as err:
                    self.available_data_ports.put_nowait((priority + 1, port))
                    if err.errno != errno.EADDRINUSE:
                        raise
        else:
            passive_server = await asyncio.start_server(
                handler_callback,
                connection.server_host,
                connection.passive_server_port,
                ssl=self.ssl,
                **self._start_server_extra_arguments,
            )
        return passive_server

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
                )

        if not connection.future.passive_server.done():
            coro = self._start_passive_server(connection, handler)
            try:
                connection.passive_server = await coro
            except errors.NoAvailablePort:
                connection.response("421", ["no free ports"])
                return False
            code, info = "227", ["listen socket created"]
        else:
            code, info = "227", ["listen socket already exists"]

        for sock in connection.passive_server.sockets:
            if sock.family == socket.AF_INET:
                host, port = sock.getsockname()
                break
        else:
            connection.response("503", ["this server started in ipv6 mode"])
            return False

        nums = tuple(map(int, host.split("."))) + (port >> 8, port & 0xff)
        info.append(f"({','.join(map(str, nums))})")
        if connection.future.data_connection.done():
            connection.data_connection.close()
            del connection.data_connection
        connection.response(code, info)
        return True

    @ConnectionConditions(ConnectionConditions.login_required)
    async def epsv(self, connection, rest):

        async def handler(reader, writer):
            if connection.future.data_connection.done():
                writer.close()
            else:
                connection.data_connection = ThrottleStreamIO(
                    reader,
                    writer,
                    throttles=connection.command_connection.throttles,
                    timeout=connection.socket_timeout,
                )

        if rest:
            code, info = "522", ["custom protocols support not implemented"]
            connection.response(code, info)
            return False
        if not connection.future.passive_server.done():
            coro = self._start_passive_server(connection, handler)
            try:
                connection.passive_server = await coro
            except errors.NoAvailablePort:
                connection.response("421", ["no free ports"])
                return False
            code, info = "229", ["listen socket created"]
        else:
            code, info = "229", ["listen socket already exists"]

        for sock in connection.passive_server.sockets:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                _, port, *_ = sock.getsockname()
                break

        info[0] += f" (|||{port}|)"
        if connection.future.data_connection.done():
            connection.data_connection.close()
            del connection.data_connection
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

    async def rest(self, connection, rest):
        if rest.isdigit():
            connection.restart_offset = int(rest)
            connection.response("350", f"restarting at {rest}")
        else:
            connection.restart_offset = 0
            message = f"syntax error, can't restart at {rest!r}"
            connection.response("501", message)
        return True

    async def syst(self, connection, rest):
        """Return system type (always returns UNIX type: L8)."""
        connection.response("215", "UNIX Type: L8")
        return True
