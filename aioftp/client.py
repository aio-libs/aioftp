import asyncio
import re
import collections
import pathlib
import logging

from . import errors
from . import pathio
from .common import *  # noqa


__all__ = (
    "Client",
    "DataConnectionThrottleStreamIO",
    "Code",
)
logger = logging.getLogger("aioftp.client")


async def open_connection(host, port, loop, create_connection):

    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    transport, _ = await create_connection(lambda: protocol, host, port)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


class Code(str):
    """
    Representation of server status code.
    """

    def matches(self, mask):
        """
        :param mask: Template for comparision. If mask symbol is not digit
            then it passes.
        :type mask: :py:class:`str`

        ::

            >>> Code("123").matches("1")
            True
            >>> Code("123").matches("1x3")
            True
        """
        return all(map(lambda m, c: not str.isdigit(m) or m == c, mask, self))


class DataConnectionThrottleStreamIO(ThrottleStreamIO):
    """
    Add `finish` method to :py:class:`aioftp.ThrottleStreamIO`, which is
    specific for data connection. This requires `client`.

    :param client: client class, which have :py:meth:`aioftp.Client.command`
    :type client: :py:class:`aioftp.BaseClient`

    :param *args: positional arguments passed to
        :py:class:`aioftp.ThrottleStreamIO`

    :param **kwargs: keyword arguments passed to
        :py:class:`aioftp.ThrottleStreamIO`
    """

    def __init__(self, client, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.client = client

    async def finish(self, expected_codes="2xx", wait_codes="1xx"):
        """
        :py:func:`asyncio.coroutine`

        Close connection and wait for `expected_codes` response from server
        passing `wait_codes`.

        :param expected_codes: tuple of expected codes or expected code
        :type expected_codes: :py:class:`tuple` of :py:class:`str` or
            :py:class:`str`

        :param wait_codes: tuple of wait codes or wait code
        :type wait_codes: :py:class:`tuple` of :py:class:`str` or
            :py:class:`str`
        """
        self.close()
        await self.client.command(None, expected_codes, wait_codes)

    async def __aexit__(self, exc_type, exc, tb):

        if exc is None:

            await self.finish()


class BaseClient:

    def __init__(self,
                 *,
                 loop=None,
                 create_connection=None,
                 socket_timeout=None,
                 read_speed_limit=None,
                 write_speed_limit=None,
                 path_timeout=None,
                 path_io_factory=pathio.AsyncPathIO):

        self.loop = loop or asyncio.get_event_loop()
        self.create_connection = create_connection or \
            self.loop.create_connection
        self.socket_timeout = socket_timeout

        self.throttle = StreamThrottle.from_limits(
            read_speed_limit,
            write_speed_limit,
            loop=self.loop
        )

        self.path_timeout = path_timeout
        self.path_io = path_io_factory(timeout=path_timeout, loop=loop)

    async def connect(self, host, port=21):

        self.server_host = host
        self.server_port = port
        reader, writer = await open_connection(
            host,
            port,
            self.loop,
            self.create_connection
        )
        self.stream = ThrottleStreamIO(
            reader,
            writer,
            throttles={"_": self.throttle},
            timeout=self.socket_timeout,
            loop=self.loop
        )

    def close(self):
        """
        Close connection.
        """
        self.stream.close()

    async def parse_line(self):
        """
        :py:func:`asyncio.coroutine`

        Parsing server response line.

        :return: (code, line)
        :rtype: (:py:class:`aioftp.Code`, :py:class:`str`)

        :raises ConnectionResetError: if received data is empty (this
            means, that connection is closed)
        :raises asyncio.TimeoutError: if there where no data for `timeout`
            period
        """
        line = await self.stream.readline()
        if not line:

            self.stream.close()
            raise ConnectionResetError

        s = str.rstrip(bytes.decode(line, encoding="utf-8"))
        logger.info(s)
        return Code(s[:3]), s[3:]

    async def parse_response(self):
        """
        :py:func:`asyncio.coroutine`

        Parsing full server response (all lines).

        :return: (code, lines)
        :rtype: (:py:class:`aioftp.Code`, :py:class:`list` of :py:class:`str`)

        :raises aioftp.StatusCodeError: if received code does not matches all
            already received codes
        """
        code, rest = await self.parse_line()
        info = [rest]
        curr_code = code
        while str.startswith(rest, "-") or not str.isdigit(curr_code):

            curr_code, rest = await self.parse_line()
            if str.isdigit(curr_code):

                info.append(rest)
                if curr_code != code:

                    raise errors.StatusCodeError(code, curr_code, info)

            else:

                info.append(curr_code + rest)

        return code, info

    def check_codes(self, expected_codes, received_code, info):
        """
        Checks if any of expected matches received.

        :param expected_codes: tuple of expected codes
        :type expected_codes: :py:class:`tuple`

        :param received_code: received code for matching
        :type received_code: :py:class:`aioftp.Code`

        :param info: list of response lines from server
        :type info: :py:class:`list`

        :raises aioftp.StatusCodeError: if received code does not matches any
            expected code
        """
        if not any(map(received_code.matches, expected_codes)):

            raise errors.StatusCodeError(expected_codes, received_code, info)

    async def command(self, command=None, expected_codes=(), wait_codes=()):
        """
        :py:func:`asyncio.coroutine`

        Basic command logic.

        1. Send command if not omitted.
        2. Yield response until no wait code matches.
        3. Check code for expected.

        :param command: command line
        :type command: :py:class:`str`

        :param expected_codes: tuple of expected codes or expected code
        :type expected_codes: :py:class:`tuple` of :py:class:`str` or
            :py:class:`str`

        :param wait_codes: tuple of wait codes or wait code
        :type wait_codes: :py:class:`tuple` of :py:class:`str` or
            :py:class:`str`
        """
        expected_codes = wrap_with_container(expected_codes)
        wait_codes = wrap_with_container(wait_codes)

        if command:

            logger.info(command)
            message = command + END_OF_LINE
            await self.stream.write(str.encode(message, encoding="utf-8"))

        if expected_codes or wait_codes:

            code, info = await self.parse_response()
            while any(map(code.matches, wait_codes)):

                code, info = await self.parse_response()

            if expected_codes:

                self.check_codes(expected_codes, code, info)

            return code, info

    def parse_address_response(self, s):
        """
        Parsing ip:port server response.

        :param s: response line
        :type s: :py:class:`str`

        :return: (ip, port)
        :rtype: (:py:class:`str`, :py:class:`int`)
        """
        sub, *_ = re.findall(r"[^(]*\(([^)]*)", s)
        nums = tuple(map(int, str.split(sub, ",")))
        ip = str.join(".", map(str, nums[:4]))
        port = (nums[4] << 8) | nums[5]
        return ip, port

    def parse_directory_response(self, s):
        """
        Parsing directory server response.

        :param s: response line
        :type s: :py:class:`str`

        :rtype: :py:class:`pathlib.PurePosixPath`
        """
        seq_quotes = 0
        start = False
        directory = ""
        for ch in s:

            if not start:

                if ch == '"':

                    start = True

            else:

                if ch == '"':

                    seq_quotes += 1

                else:

                    if seq_quotes == 1:

                        break

                    elif seq_quotes == 2:

                        seq_quotes = 0
                        directory += '"'

                    directory += ch

        return pathlib.PurePosixPath(directory)

    def parse_mlsx_line(self, b):
        """
        Parsing MLS(T|D) response.

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
        """
        if isinstance(b, bytes):

            s = str.rstrip(bytes.decode(b, encoding="utf-8"))

        else:

            s = b

        line = str.rstrip(s)
        facts_found, _, name = str.partition(line, " ")
        entry = {}
        for fact in str.split(facts_found[:-1], ";"):

            key, _, value = str.partition(fact, "=")
            entry[key.lower()] = value

        return pathlib.PurePosixPath(name), entry


class Client(BaseClient):
    """
    FTP client.

    :param loop: loop to use for creating connection and binding with streams
    :type loop: :py:class:`asyncio.BaseEventLoop`

    :param create_connection: factory for creating
        connection.
        Using default :py:meth:`asyncio.BaseEventLoop.create_connection`
        if omitted.
    :type create_connection: :py:func:`callable`

    :param socket_timeout: timeout for read operations
    :type socket_timeout: :py:class:`float`, :py:class:`int` or `None`

    :param read_speed_limit: download speed limit in bytes per second
    :type server_to_client_speed_limit: :py:class:`int` or `None`

    :param write_speed_limit: upload speed limit in bytes per second
    :type client_to_server_speed_limit: :py:class:`int` or `None`

    :param path_timeout: timeout for path-related operations (make directory,
        unlink file, etc.)
    :type path_timeout: :py:class:`float`, :py:class:`int` or
        :py:class:`None`

    :param path_io_factory: factory of «path abstract layer»
    :type path_io_factory: :py:class:`aioftp.AbstractPathIO`
    """

    async def connect(self, host, port=21):
        """
        :py:func:`asyncio.coroutine`

        Connect to server.

        :param host: host name for connection
        :type host: :py:class:`str`

        :param port: port number for connection
        :type port: :py:class:`int`
        """
        await super().connect(host, port)
        code, info = await self.command(None, "220", "120")
        return info

    async def login(self, user="anonymous", password="anon@", account=""):
        """
        :py:func:`asyncio.coroutine`

        Server authentication.

        :param user: username
        :type user: :py:class:`str`

        :param password: password
        :type password: :py:class:`str`

        :param account: account (almost always blank)
        :type account: :py:class:`str`

        :raises aioftp.StatusCodeError: if unknown code received
        """
        code, info = await self.command("USER " + user, ("230", "33x"))
        while code.matches("33x"):

            if code == "331":

                cmd = "PASS " + password

            elif code == "332":

                cmd = "ACCT " + account

            else:

                raise errors.StatusCodeError("33x", code, info)

            code, info = await self.command(cmd, ("230", "33x"))

    async def get_current_directory(self):
        """
        :py:func:`asyncio.coroutine`

        Getting current working directory.

        :rtype: :py:class:`pathlib.PurePosixPath`
        """
        code, info = await self.command("PWD", "257")
        directory = self.parse_directory_response(info[-1])
        return directory

    async def change_directory(self, path=".."):
        """
        :py:func:`asyncio.coroutine`

        Change current directory. Goes «up» if no parameters passed.

        :param path: new directory, goes «up» if omitted
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        if path in ("..", pathlib.PurePosixPath("..")):

            cmd = "CDUP"

        else:

            cmd = "CWD " + str(path)

        await self.command(cmd, "2xx")

    async def make_directory(self, path, *, parents=True):
        """
        :py:func:`asyncio.coroutine`

        Make directory.

        :param path: path to directory to create
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param parents: create parents if does not exists
        :type parents: :py:class:`bool`
        """
        path = pathlib.PurePosixPath(path)
        need_create = []
        while path.name and not await self.exists(path):

            need_create.append(path)
            path = path.parent
            if not parents:

                break

        need_create.reverse()
        for path in need_create:

            await self.command("MKD " + str(path), "257")

    async def remove_directory(self, path):
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing empty directory.

        :param path: empty directory to remove
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("RMD " + str(path), "250")

    def list(self, path="", *, recursive=False):
        """
        :py:func:`asyncio.coroutine`

        List all files and directories in "path".

        :param path: directory or file path
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param recursive: list recursively
        :type recursive: :py:class:`bool`

        :rtype: :py:class:`list` or `async for` context

        ::

            >>> async for path, info in client.list():
            ...     print(path)

        ::

            >>> stats = await client.list()
        """
        class AsyncClientLister(AsyncListerMixin):

            async def _new_stream(cls, local_path):

                cls.path = local_path
                command = str.strip("MLSD " + str(cls.path))
                return await self.get_stream(command, "1xx")

            async def __aiter__(cls):

                cls.stream = await cls._new_stream(path)
                cls.directories = collections.deque()
                return cls

            async def __anext__(cls):

                while True:

                    line = await cls.stream.readline()
                    while not line:

                        await cls.stream.finish()
                        if cls.directories:

                            current_path, info = cls.directories.popleft()
                            cls.stream = await cls._new_stream(current_path)
                            line = await cls.stream.readline()

                        else:

                            raise StopAsyncIteration

                    name, info = self.parse_mlsx_line(line)
                    if info["type"] in ("file", "dir"):

                        stat = cls.path / name, info
                        if info["type"] == "dir" and recursive:

                            cls.directories.append(stat)

                        return stat

        return AsyncClientLister()

    async def stat(self, path):
        """
        :py:func:`asyncio.coroutine`

        Getting path stats.

        :param path: path for getting info
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :return: path info
        :rtype: :py:class:`dict`
        """
        code, info = await self.command("MLST " + str(path), "2xx")
        name, info = self.parse_mlsx_line(str.lstrip(info[1]))
        return info

    async def is_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Checks if path is file.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        info = await self.stat(path)
        return info["type"] == "file"

    async def is_dir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Checks if path is dir.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        info = await self.stat(path)
        return info["type"] == "dir"

    async def exists(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check path for existence.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        code, info = await self.command("MLST " + str(path), ("2xx", "550"))
        exists = code.matches("2xx")
        return exists

    async def rename(self, source, destination):
        """
        :py:func:`asyncio.coroutine`

        Rename (move) file or directory.

        :param source: path to rename
        :type source: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param destination: path new name
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("RNFR " + str(source), "350")
        await self.command("RNTO " + str(destination), "2xx")

    async def remove_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing file.

        :param path: file to remove
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("DELE " + str(path), "2xx")

    async def remove(self, path):
        """
        :py:func:`asyncio.coroutine`

        High level remove method for removing path recursively (file or
        directory).

        :param path: path to remove
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        if await self.exists(path):

            info = await self.stat(path)
            if info["type"] == "file":

                await self.remove_file(path)

            elif info["type"] == "dir":

                for name, info in (await self.list(path)):

                    if info["type"] in ("dir", "file"):

                        await self.remove(name)

                await self.remove_directory(path)

    def upload_stream(self, destination):
        """
        Create stream for write data to `destination` file.

        :param destination: destination path of file on server side
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`aioftp.ThrottleStreamIO`
        """
        return self.get_stream("STOR " + str(destination), "1xx")

    def append_stream(self, destination):
        """
        Create stream for append (write) data to `destination` file.

        :param destination: destination path of file on server side
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`aioftp.ThrottleStreamIO`
        """
        return self.get_stream("APPE " + str(destination), "1xx")

    async def upload(self, source, destination="", *, write_into=False,
                     block_size=DEFAULT_BLOCK_SIZE):
        """
        :py:func:`asyncio.coroutine`

        High level upload method for uploading files and directories
        recursively from file system.

        :param source: source path of file or directory on client side
        :type source: :py:class:`str` or :py:class:`pathlib.Path`

        :param destination: destination path of file or directory on server
            side
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param write_into: write source into destination (if you want upload
            file and change it name, as well with directories)
        :type write_into: :py:class:`bool`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
        source = pathlib.Path(source)
        destination = pathlib.PurePosixPath(destination)
        if not write_into:

            destination = destination / source.name

        if await self.path_io.is_file(source):

            await self.make_directory(destination.parent)
            async with self.path_io.open(source, mode="rb") as file_in, \
                    self.upload_stream(destination) as stream:

                async for block in file_in.iter_by_block(block_size):

                    await stream.write(block)

        elif await self.path_io.is_dir(source):

            await self.make_directory(destination)
            sources = collections.deque([source])
            while sources:

                src = sources.popleft()
                async for path in self.path_io.list(src):

                    if write_into:

                        relative = destination.name / path.relative_to(source)

                    else:

                        relative = path.relative_to(source.parent)

                    if await self.path_io.is_dir(path):

                        await self.make_directory(relative)
                        sources.append(path)

                    else:

                        await self.upload(
                            path,
                            relative,
                            write_into=True,
                            block_size=block_size
                        )

    def download_stream(self, source):
        """
        :py:func:`asyncio.coroutine`

        Create stream for read data from `source` file.

        :param source: source path of file on server side
        :type source: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`aioftp.ThrottleStreamIO`
        """
        return self.get_stream("RETR " + str(source), "1xx")

    async def download(self, source, destination="", *, write_into=False,
                       block_size=DEFAULT_BLOCK_SIZE):
        """
        :py:func:`asyncio.coroutine`

        High level download method for downloading files and directories
        recursively and save them to the file system.

        :param source: source path of file or directory on server side
        :type source: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param destination: destination path of file or directory on client
            side
        :type destination: :py:class:`str` or :py:class:`pathlib.Path`

        :param write_into: write source into destination (if you want download
            file and change it name, as well with directories)
        :type write_into: :py:class:`bool`

        :param block_size: block size for transaction
        :type block_size: :py:class:`int`
        """
        source = pathlib.PurePosixPath(source)
        destination = pathlib.Path(destination)
        if not write_into:

            destination = destination / source.name

        if await self.is_file(source):

            if not await self.path_io.exists(destination.parent):

                await self.path_io.mkdir(destination.parent)

            async with self.path_io.open(destination, mode="wb") as file_out, \
                    self.download_stream(source) as stream:

                async for block in stream.iter_by_block(block_size):

                    await file_out.write(block)

        elif await self.is_dir(source):

            if not await self.path_io.exists(destination):

                await self.path_io.mkdir(destination, parents=True)

            for name, info in (await self.list(source)):

                full = destination / name.relative_to(source)
                if info["type"] in ("file", "dir"):

                    await self.download(
                        name,
                        full,
                        write_into=True,
                        block_size=block_size
                    )

    async def quit(self):
        """
        :py:func:`asyncio.coroutine`

        Send "QUIT" and close connection.
        """
        await self.command("QUIT", "2xx")
        self.close()

    async def get_passive_connection(self, conn_type="I"):
        """
        :py:func:`asyncio.coroutine`

        Getting pair of reader, writer for passive connection with server.

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :rtype: (:py:class:`asyncio.StreamReader`,
            :py:class:`asyncio.StreamWriter`)
        """
        await self.command("TYPE " + conn_type, "200")
        code, info = await self.command("PASV", "227")
        ip, port = self.parse_address_response(info[-1])
        if ip == "0.0.0.0":

            ip = self.server_host

        reader, writer = await open_connection(
            ip,
            port,
            self.loop,
            self.create_connection,
        )
        return reader, writer

    @async_enterable
    async def get_stream(self, *command_args, conn_type="I"):
        """
        :py:func:`asyncio.coroutine`

        Create :py:class:`aioftp.DataConnectionThrottleStreamIO` for straight
        read/write io.

        :param command_args: arguments for :py:meth:`aioftp.Client.command`

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :rtype: :py:class:`aioftp.DataConnectionThrottleStreamIO`
        """
        reader, writer = await self.get_passive_connection(conn_type)
        await self.command(*command_args)
        stream = DataConnectionThrottleStreamIO(
            self,
            reader,
            writer,
            throttles={"_": self.throttle},
            timeout=self.socket_timeout,
            loop=self.loop
        )
        return stream

    async def abort(self, *, wait=True):
        """
        :py:func:`asyncio.coroutine`

        Request data transfer abort.

        :param wait: wait for abort response [426]→226 if `True`
        :type wait: :py:class:`bool`
        """
        if wait:

            await self.command("ABOR", "226", "426")

        else:

            await self.command("ABOR")
