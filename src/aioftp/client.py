import asyncio
import calendar
import collections
import contextlib
import datetime
import logging
import pathlib
import re
from functools import partial
from ssl import SSLContext
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Deque,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)

from typing_extensions import NotRequired, Self, TypeAlias, TypedDict, override

from . import errors, pathio
from .common import (
    DEFAULT_ACCOUNT,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USER,
    END_OF_LINE,
    HALF_OF_YEAR_IN_SECONDS,
    TWO_YEARS_IN_SECONDS,
    AsyncListerMixin,
    StreamThrottle,
    ThrottleStreamIO,
    async_enterable,
    setlocale,
    wrap_with_container,
)
from .types import AsyncEnterableProtocol

try:
    from siosocks.io.asyncio import open_connection  # type: ignore
except ImportError:
    from asyncio import open_connection


__all__ = (
    "BaseClient",
    "Client",
    "DataConnectionThrottleStreamIO",
    "Code",
)
logger = logging.getLogger(__name__)

_PathType: TypeAlias = Union[str, pathlib.PurePath]
_ConnectionType: TypeAlias = Literal["I", "A", "E", "L"]

_InfoFileType: TypeAlias = Literal["file", "dir", "link", "unknown"]


class WindowsInfoDict(TypedDict):
    type: _InfoFileType
    size: NotRequired[str]
    modify: str


UnixInfoDict = TypedDict(
    "UnixInfoDict",
    {
        "type": _InfoFileType,
        "size": str,
        "modify": str,
        "unix.mode": int,
        "unix.links": str,
        "unix.owner": str,
        "unix.group": str,
    },
)

InfoDict: TypeAlias = Union[WindowsInfoDict, UnixInfoDict]

_ParserType: TypeAlias = Callable[[bytes], Tuple[pathlib.PurePosixPath, InfoDict]]


class Code(str):
    """
    Representation of server status code.
    """

    def matches(self, mask: str) -> bool:
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
        return all(map(lambda m, c: not m.isdigit() or m == c, mask, self))


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

    client: "BaseClient"

    def __init__(self, client: "BaseClient", *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.client = client

    async def finish(
        self,
        expected_codes: Code = Code("2xx"),
        wait_codes: Union[Tuple[Code], Code] = Code("1xx"),
    ) -> None:
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

    @override
    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if exc is None:
            await self.finish()
        else:
            self.close()


CodesORCode: TypeAlias = Union[Tuple[Code, ...], Code]
EmptyCodes: TypeAlias = Tuple[()]


class BaseClient:
    socket_timeout: Optional[int]
    connection_timeout: Optional[int]
    throttle: StreamThrottle
    path_timeout: Optional[int]

    path_io: pathio.AbstractPathIO
    encoding: str
    stream: Optional[ThrottleStreamIO]
    ssl: Optional[SSLContext]
    parse_list_line_custom: Optional[_ParserType]
    parse_list_line_custom_first: bool
    _passive_commands: Sequence[str]
    _open_connection: "partial[Coroutine[None, None, Tuple[asyncio.StreamReader, asyncio.StreamWriter]]]"
    server_host: Optional[str] = None
    server_port: Optional[int] = None

    def __init__(
        self,
        *,
        socket_timeout: Optional[int] = None,
        connection_timeout: Optional[int] = None,
        read_speed_limit: Optional[int] = None,
        write_speed_limit: Optional[int] = None,
        path_timeout: Optional[int] = None,
        path_io_factory: Type[pathio.AbstractPathIO] = pathio.PathIO,
        encoding: str = "utf-8",
        ssl: Optional[SSLContext] = None,
        parse_list_line_custom: Optional[_ParserType] = None,
        parse_list_line_custom_first: bool = True,
        passive_commands: Sequence[str] = ("epsv", "pasv"),
        **siosocks_asyncio_kwargs: Any,
    ):
        self.socket_timeout = socket_timeout
        self.connection_timeout = connection_timeout
        self.throttle = StreamThrottle.from_limits(
            read_speed_limit,
            write_speed_limit,
        )
        self.path_timeout = path_timeout
        self.path_io = path_io_factory(timeout=path_timeout)
        self.encoding = encoding
        self.stream = None
        self.ssl = ssl
        self.parse_list_line_custom = parse_list_line_custom
        self.parse_list_line_custom_first = parse_list_line_custom_first
        self._passive_commands = passive_commands
        self._open_connection = partial(open_connection, ssl=self.ssl, **siosocks_asyncio_kwargs)

    async def connect(self, host: str, port: int = DEFAULT_PORT) -> Optional[List[str]]:
        self.server_host = host
        self.server_port = port
        reader, writer = await asyncio.wait_for(
            self._open_connection(host, port),
            self.connection_timeout,
        )
        self.stream = ThrottleStreamIO(
            reader,
            writer,
            throttles={"_": self.throttle},
            timeout=self.socket_timeout,
        )
        return None

    def close(self) -> None:
        """
        Close connection.
        """
        if self.stream is not None:
            self.stream.close()

    async def parse_line(self) -> Tuple[Code, str]:
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
        line = await self.stream.readline()  # type: ignore
        if not line:
            self.stream.close()  # type: ignore
            raise ConnectionResetError
        s = line.decode(encoding=self.encoding).rstrip()
        logger.debug(s)
        return Code(s[:3]), s[3:]

    async def parse_response(self) -> Tuple[Code, List[str]]:
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
        while rest.startswith("-") or not curr_code.isdigit():
            curr_code, rest = await self.parse_line()
            if curr_code.isdigit():
                info.append(rest)
                if curr_code != code:
                    raise errors.StatusCodeError(code, curr_code, info)
            else:
                info.append(curr_code + rest)
        return code, info

    def check_codes(
        self,
        expected_codes: Union[Tuple[Code, ...], Code],
        received_code: Code,
        info: List[str],
    ) -> None:
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

    @overload
    async def command(  # type: ignore
        self,
        command: Optional[str] = None,
        expected_codes: Tuple[()] = (),
        wait_codes: Tuple[()] = (),
        censor_after: Optional[int] = None,
    ) -> None: ...

    @overload
    async def command(
        self,
        command: Optional[str] = None,
        expected_codes: CodesORCode = (),
        wait_codes: CodesORCode = (),
        censor_after: Optional[int] = None,
    ) -> Tuple[Code, List[str]]: ...

    async def command(
        self,
        command: Optional[str] = None,
        expected_codes: Union[EmptyCodes, CodesORCode] = (),
        wait_codes: Union[EmptyCodes, CodesORCode] = (),
        censor_after: Optional[int] = None,
    ) -> Optional[Tuple[Code, List[str]]]:
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

        :param censor_after: index after which the line should be censored
            when logging
        :type censor_after: :py:class:`None` or :py:class:`int`
        """
        expected_codes = wrap_with_container(expected_codes)
        wait_codes = wrap_with_container(wait_codes)
        if command:
            if censor_after:
                # Censor the user's command
                raw = command[:censor_after]
                stars = "*" * len(command[censor_after:])
                logger.debug("%s%s", raw, stars)
            else:
                logger.debug(command)
            message = command + END_OF_LINE
            await self.stream.write(message.encode(encoding=self.encoding))  # type: ignore
        if expected_codes or wait_codes:
            code, info = await self.parse_response()
            while any(map(code.matches, wait_codes)):
                code, info = await self.parse_response()
            if expected_codes:
                self.check_codes(expected_codes, code, info)
            return code, info
        return None

    @staticmethod
    def parse_epsv_response(s: str) -> Tuple[None, int]:
        """
        Parsing `EPSV` (`message (|||port|)`) response.

        :param s: response line
        :type s: :py:class:`str`

        :return: (ip, port)
        :rtype: (:py:class:`None`, :py:class:`int`)
        """
        matches = tuple(re.finditer(r"\((.)\1\1\d+\1\)", s))
        s = matches[-1].group()
        port = int(s[4:-2])
        return None, port

    @staticmethod
    def parse_pasv_response(s: str) -> Tuple[str, int]:
        """
        Parsing `PASV` server response.

        :param s: response line
        :type s: :py:class:`str`

        :return: (ip, port)
        :rtype: (:py:class:`str`, :py:class:`int`)
        """
        sub, *_ = re.findall(r"[^(]*\(([^)]*)", s)
        nums = tuple(map(int, sub.split(",")))
        ip = ".".join(map(str, nums[:4]))
        port = (nums[4] << 8) | nums[5]
        return ip, port

    @staticmethod
    def parse_directory_response(s: str) -> pathlib.PurePosixPath:
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

    @staticmethod
    def parse_unix_mode(s: str) -> int:
        """
        Parsing unix mode strings ("rwxr-x--t") into hexacimal notation.

        :param s: mode string
        :type s: :py:class:`str`

        :return mode:
        :rtype: :py:class:`int`
        """
        parse_rw = {"rw": 6, "r-": 4, "-w": 2, "--": 0}
        mode = 0
        mode |= parse_rw[s[0:2]] << 6
        mode |= parse_rw[s[3:5]] << 3
        mode |= parse_rw[s[6:8]]
        if s[2] == "s":
            mode |= 0o4100
        elif s[2] == "x":
            mode |= 0o0100
        elif s[2] != "-":
            raise ValueError

        if s[5] == "s":
            mode |= 0o2010
        elif s[5] == "x":
            mode |= 0o0010
        elif s[5] != "-":
            raise ValueError

        if s[8] == "t":
            mode |= 0o1000
        elif s[8] == "x":
            mode |= 0o0001
        elif s[8] != "-":
            raise ValueError

        return mode

    @staticmethod
    def format_date_time(d: datetime.datetime) -> str:
        """
        Formats dates from strptime in a consistent format

        :param d: return value from strptime
        :type d: :py:class:`datetime`

        :rtype: :py:class`str`
        """
        return d.strftime("%Y%m%d%H%M00")

    @classmethod
    def parse_ls_date(cls, s: str, *, now: Optional[datetime.datetime] = None) -> str:
        """
        Parsing dates from the ls unix utility. For example,
        "Nov 18  1958", "Jan 03 2018", and "Nov 18 12:29".

        :param s: ls date
        :type s: :py:class:`str`

        :rtype: :py:class:`str`
        """
        with setlocale("C"):
            try:
                if now is None:
                    now = datetime.datetime.now()
                if s.startswith("Feb 29"):
                    # Need to find the nearest previous leap year
                    prev_leap_year = now.year
                    while not calendar.isleap(prev_leap_year):
                        prev_leap_year -= 1
                    d = datetime.datetime.strptime(
                        f"{prev_leap_year} {s}",
                        "%Y %b %d %H:%M",
                    )
                    # Check if it's next leap year
                    diff = (now - d).total_seconds()
                    if diff > TWO_YEARS_IN_SECONDS:
                        d = d.replace(year=prev_leap_year + 4)
                else:
                    d = datetime.datetime.strptime(s, "%b %d %H:%M")
                    d = d.replace(year=now.year)
                    diff = (now - d).total_seconds()
                    if diff > HALF_OF_YEAR_IN_SECONDS:
                        d = d.replace(year=now.year + 1)
                    elif diff < -HALF_OF_YEAR_IN_SECONDS:
                        d = d.replace(year=now.year - 1)
            except ValueError:
                d = datetime.datetime.strptime(s, "%b %d  %Y")
        return cls.format_date_time(d)

    def parse_list_line_unix(self, b: bytes) -> Tuple[pathlib.PurePosixPath, UnixInfoDict]:
        """
        Attempt to parse a LIST line (similar to unix ls utility).

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
        """
        s = b.decode(encoding=self.encoding).rstrip()
        info: dict[str, Any] = {}
        if s[0] == "-":
            info["type"] = "file"
        elif s[0] == "d":
            info["type"] = "dir"
        elif s[0] == "l":
            info["type"] = "link"
        else:
            info["type"] = "unknown"

        # TODO: handle symlinks(beware the symlink loop)
        info["unix.mode"] = self.parse_unix_mode(s[1:10])
        s = s[10:].lstrip()
        i = s.index(" ")
        info["unix.links"] = s[:i]

        if not info["unix.links"].isdigit():
            raise ValueError

        s = s[i:].lstrip()
        i = s.index(" ")
        info["unix.owner"] = s[:i]
        s = s[i:].lstrip()
        i = s.index(" ")
        info["unix.group"] = s[:i]
        s = s[i:].lstrip()
        i = s.index(" ")
        info["size"] = s[:i]

        if not info["size"].isdigit():
            raise ValueError

        s = s[i:].lstrip()
        info["modify"] = self.parse_ls_date(s[:12].strip())
        s = s[12:].strip()
        if info["type"] == "link":
            i = s.rindex(" -> ")
            link_dst = s[i + 4 :]
            link_src = s[:i]
            i = -2 if link_dst[-1] == "'" or link_dst[-1] == '"' else -1
            info["type"] = "dir" if link_dst[i] == "/" else "file"
            s = link_src
        return pathlib.PurePosixPath(s), UnixInfoDict(
            {
                "type": info["type"],
                "size": info["size"],
                "modify": info["modify"],
                "unix.mode": info["unix.mode"],
                "unix.links": info["unix.links"],
                "unix.owner": info["unix.owner"],
                "unix.group": info["unix.group"],
            },
        )

    def parse_list_line_windows(self, b: bytes) -> Tuple[pathlib.PurePosixPath, WindowsInfoDict]:
        """
        Parsing Microsoft Windows `dir` output

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
        """
        line = b.decode(encoding=self.encoding).rstrip("\r\n")
        date_time_end = line.index("M")
        date_time_list_str = line[: date_time_end + 1].strip().split(" ")
        date_time_str = " ".join([x for x in date_time_list_str if len(x) > 0])
        line = line[date_time_end + 1 :].lstrip()
        with setlocale("C"):
            strptime = datetime.datetime.strptime
            date_time = strptime(date_time_str, "%m/%d/%Y %I:%M %p")
        info: dict[str, Any] = {}
        info["modify"] = self.format_date_time(date_time)
        next_space = line.index(" ")
        if line.startswith("<DIR>"):
            info["type"] = "dir"
        else:
            info["type"] = "file"
            info["size"] = line[:next_space].replace(",", "")
            if not info["size"].isdigit():
                raise ValueError
        # This here could cause a problem if a filename started with
        # whitespace, but if we were to try to detect such a condition
        # we would have to make strong assumptions about the input format
        filename = line[next_space:].lstrip()
        if filename == "." or filename == "..":
            raise ValueError

        windows_info: WindowsInfoDict = {
            "type": info["type"],
            "modify": info["modify"],
        }
        if "size" in info:
            windows_info["size"] = info["size"]

        return pathlib.PurePosixPath(filename), windows_info

    def parse_list_line(self, b: bytes) -> Tuple[pathlib.PurePosixPath, InfoDict]:
        """
        Parse LIST response with both Microsoft Windows® parser and
        UNIX parser

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
        """
        ex: List[Exception] = []
        parsers: List[Optional[_ParserType]] = [
            self.parse_list_line_unix,
            self.parse_list_line_windows,
        ]
        if self.parse_list_line_custom_first:
            parsers = [self.parse_list_line_custom] + parsers
        else:
            parsers = parsers + [self.parse_list_line_custom]
        for parser in parsers:
            if parser is None:
                continue
            try:
                return parser(b)
            except (ValueError, KeyError, IndexError) as e:
                ex.append(e)
        raise ValueError("All parsers failed to parse", b, ex)

    def parse_mlsx_line(self, b: Union[bytes, str]) -> Tuple[pathlib.PurePosixPath, InfoDict]:
        """
        Parsing MLS(T|D) response.

        :param b: response line
        :type b: :py:class:`bytes` or :py:class:`str`

        :return: (path, info)
        :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
        """
        if isinstance(b, bytes):
            s = b.decode(encoding=self.encoding)
        else:
            s = b
        line = s.rstrip()
        facts_found, _, name = line.partition(" ")
        entry: Dict[str, str] = {}
        for fact in facts_found[:-1].split(";"):
            key, _, value = fact.partition("=")
            entry[key.lower()] = value

        return pathlib.PurePosixPath(name), cast(InfoDict, entry)


class Client(BaseClient):
    """
    FTP client.

    :param socket_timeout: timeout for read operations
    :type socket_timeout: :py:class:`float`, :py:class:`int` or `None`

    :param connection_timeout: timeout for connection
    :type connection_timeout: :py:class:`float`, :py:class:`int` or `None`

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

    :param encoding: encoding to use for convertion strings to bytes
    :type encoding: :py:class:`str`

    :param ssl: if given and not false, a SSL/TLS transport is created
        (by default a plain TCP transport is created).
        If ssl is a ssl.SSLContext object, this context is used to create
        the transport; if ssl is True, a default context returned from
        ssl.create_default_context() is used.
        Please look :py:meth:`asyncio.loop.create_connection` docs.
    :type ssl: :py:class:`bool` or :py:class:`ssl.SSLContext`

    :param parse_list_line_custom: callable, which receive exactly one
        argument: line of type bytes. Should return tuple of Path object and
        dictionary with fields "modify", "type", "size". For more
        information see sources.
    :type parse_list_line_custom: callable
    :param parse_list_line_custom_first: Should be custom parser tried first
        or last
    :type parse_list_line_custom_first: :py:class:`bool`
    :param **siosocks_asyncio_kwargs: siosocks key-word only arguments
    """

    @override
    async def connect(self, host: str, port: int = DEFAULT_PORT) -> List[str]:
        """
        :py:func:`asyncio.coroutine`

        Connect to server.

        :param host: host name for connection
        :type host: :py:class:`str`

        :param port: port number for connection
        :type port: :py:class:`int`
        """
        await super().connect(host, port)
        _, info = await self.command(None, Code("220"), Code("120"))
        return info

    async def login(
        self,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        account: str = DEFAULT_ACCOUNT,
    ) -> None:
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
        code, info = await self.command("USER " + user, (Code("230"), Code("33x")))
        while code.matches("33x"):
            censor_after = None
            if code == "331":
                cmd = "PASS " + password
                censor_after = 5
            elif code == "332":
                cmd = "ACCT " + account
            else:
                raise errors.StatusCodeError(Code("33x"), code, info)
            code, info = await self.command(
                cmd,
                (Code("230"), Code("33x")),
                censor_after=censor_after,
            )

    async def get_current_directory(self) -> pathlib.PurePosixPath:
        """
        :py:func:`asyncio.coroutine`

        Getting current working directory.

        :rtype: :py:class:`pathlib.PurePosixPath`
        """
        _, info = await self.command("PWD", Code("257"))
        directory = self.parse_directory_response(info[-1])
        return directory

    async def change_directory(self, path: _PathType = "..") -> None:
        """
        :py:func:`asyncio.coroutine`

        Change current directory. Goes «up» if no parameters passed.

        :param path: new directory, goes «up» if omitted
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        path = pathlib.PurePosixPath(path)
        if path == pathlib.PurePosixPath(".."):
            cmd = "CDUP"
        else:
            cmd = "CWD " + str(path)
        await self.command(cmd, Code("2xx"))

    async def make_directory(self, path: _PathType, *, parents: bool = True) -> None:
        """
        :py:func:`asyncio.coroutine`

        Make directory.

        :param path: path to directory to create
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param parents: create parents if does not exists
        :type parents: :py:class:`bool`
        """
        path = pathlib.PurePosixPath(path)
        need_create: List[_PathType] = []
        while path.name and not await self.exists(path):
            need_create.append(path)
            path = path.parent
            if not parents:
                break
        need_create.reverse()
        for path in need_create:
            await self.command("MKD " + str(path), Code("257"))

    async def remove_directory(self, path: _PathType) -> None:
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing empty directory.

        :param path: empty directory to remove
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("RMD " + str(path), Code("250"))

    def list(
        self,
        path: _PathType = "",
        *,
        recursive: bool = False,
        raw_command: Optional[str] = None,
    ) -> AsyncListerMixin[Tuple[pathlib.PurePath, InfoDict]]:
        """
        :py:func:`asyncio.coroutine`

        List all files and directories in "path". If "path" is a file,
        then result will be empty

        :param path: directory
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param recursive: list recursively
        :type recursive: :py:class:`bool`

        :param raw_command: optional ftp command to use in place of
            fallback logic (must be one of "MLSD", "LIST")
        :type raw_command: :py:class:`str`

        :rtype: :py:class:`list` or `async for` context

        ::

            >>> # lazy list
            >>> async for path, info in client.list():
            ...     # no interaction with client should be here(!)

            >>> # eager list
            >>> for path, info in (await client.list()):
            ...     # interaction with client allowed, since all paths are
            ...     # collected already

        ::

            >>> stats = await client.list()
        """

        class AsyncLister(
            AsyncIterator[Tuple[pathlib.PurePath, InfoDict]],
            AsyncListerMixin[Tuple[pathlib.PurePath, InfoDict]],
        ):
            stream: Optional[DataConnectionThrottleStreamIO] = None
            directories: Deque[Tuple[_PathType, InfoDict]]
            parse_line: Callable[[bytes], Tuple[pathlib.PurePath, InfoDict]]
            client: Client = self

            async def _new_stream(
                self,
                local_path: _PathType,
            ) -> Optional[DataConnectionThrottleStreamIO]:
                self.path = local_path
                self.parse_line = self.client.parse_mlsx_line
                if raw_command not in [None, "MLSD", "LIST"]:
                    raise ValueError(
                        f"raw_command must be one of MLSD or LIST, but got {raw_command}",
                    )
                if raw_command in [None, "MLSD"]:
                    try:
                        command = ("MLSD " + str(self.path)).strip()
                        return await self.client.get_stream(command, Code("1xx"))
                    except errors.StatusCodeError as e:
                        code = e.received_codes[-1]
                        if not code.matches("50x") or raw_command is not None:
                            raise
                if raw_command in [None, "LIST"]:
                    self.parse_line = self.client.parse_list_line
                    command = ("LIST " + str(self.path)).strip()
                    return await self.client.get_stream(command, Code("1xx"))
                return None

            @override
            def __aiter__(self) -> Self:
                self.directories = collections.deque()
                return self

            @override
            async def __anext__(self) -> Tuple[pathlib.PurePath, InfoDict]:
                if self.stream is None:
                    self.stream = await self._new_stream(path)

                while True:
                    line = await self.stream.readline()  # type: ignore
                    while not line:
                        await self.stream.finish()  # type: ignore
                        if self.directories:
                            current_path, info = self.directories.popleft()
                            self.stream = await self._new_stream(current_path)
                            line = await self.stream.readline()  # type: ignore
                        else:
                            raise StopAsyncIteration

                    name, info = self.parse_line(line)
                    # skipping . and .. as these are symlinks in Unix
                    if str(name) in (".", ".."):
                        continue
                    stat = self.path / name, info
                    if info["type"] == "dir" and recursive:
                        self.directories.append(stat)
                    return stat

        return AsyncLister()

    async def stat(self, path: _PathType) -> InfoDict:
        """
        :py:func:`asyncio.coroutine`

        Getting path stats.

        :param path: path for getting info
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :return: path info
        :rtype: :py:class:`dict`
        """
        path = pathlib.PurePosixPath(path)
        try:
            _, info_ = await self.command("MLST " + str(path), Code("2xx"))
            _, info = self.parse_mlsx_line(info_[1].lstrip())
            return info
        except errors.StatusCodeError as e:
            if not e.received_codes[-1].matches("50x"):
                raise

        for p, info in await self.list(path.parent):
            if p.name == path.name:
                return info
        else:
            raise errors.StatusCodeError(
                Code("2xx"),
                Code("550"),
                "path does not exists",
            )

    async def is_file(self, path: _PathType) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Checks if path is file.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        info = await self.stat(path)
        return info["type"] == "file"

    async def is_dir(self, path: _PathType) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Checks if path is dir.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        info = await self.stat(path)
        return info["type"] == "dir"

    async def exists(self, path: _PathType) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Check path for existence.

        :param path: path to check
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :rtype: :py:class:`bool`
        """
        try:
            await self.stat(path)
            return True
        except errors.StatusCodeError as e:
            if e.received_codes[-1].matches("550"):
                return False
            raise

    async def rename(self, source: _PathType, destination: _PathType) -> None:
        """
        :py:func:`asyncio.coroutine`

        Rename (move) file or directory.

        :param source: path to rename
        :type source: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param destination: path new name
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("RNFR " + str(source), Code("350"))
        await self.command("RNTO " + str(destination), Code("2xx"))

    async def remove_file(self, path: _PathType) -> None:
        """
        :py:func:`asyncio.coroutine`

        Low level remove method for removing file.

        :param path: file to remove
        :type path: :py:class:`str` or :py:class:`pathlib.PurePosixPath`
        """
        await self.command("DELE " + str(path), Code("2xx"))

    async def remove(self, path: _PathType) -> None:
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
                for name, info in await self.list(path):
                    if info["type"] in ("dir", "file"):
                        await self.remove(name)
                await self.remove_directory(path)

    def upload_stream(
        self,
        destination: _PathType,
        *,
        offset: int = 0,
    ) -> AsyncEnterableProtocol[DataConnectionThrottleStreamIO]:
        """
        Create stream for write data to `destination` file.

        :param destination: destination path of file on server side
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param offset: byte offset for stream start position
        :type offset: :py:class:`int`

        :rtype: :py:class:`aioftp.DataConnectionThrottleStreamIO`
        """
        return self.get_stream(
            "STOR " + str(destination),
            "1xx",
            offset=offset,
        )

    def append_stream(
        self,
        destination: _PathType,
        *,
        offset: int = 0,
    ) -> AsyncEnterableProtocol[DataConnectionThrottleStreamIO]:
        """
        Create stream for append (write) data to `destination` file.

        :param destination: destination path of file on server side
        :type destination: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param offset: byte offset for stream start position
        :type offset: :py:class:`int`

        :rtype: :py:class:`aioftp.DataConnectionThrottleStreamIO`
        """
        return self.get_stream(
            "APPE " + str(destination),
            "1xx",
            offset=offset,
        )

    async def upload(
        self,
        source: _PathType,
        destination: _PathType = "",
        *,
        write_into: bool = False,
        block_size: int = DEFAULT_BLOCK_SIZE,
    ) -> None:
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
        source_path = pathlib.Path(source)
        destination_path = pathlib.PurePosixPath(destination)
        if not write_into:
            destination_path = destination_path / source_path.name
        if await self.path_io.is_file(source_path):
            await self.make_directory(destination_path.parent)
            async with self.path_io.open(source_path, mode="rb") as file_in, self.upload_stream(
                destination_path,
            ) as stream:
                async for block in file_in.iter_by_block(block_size):
                    await stream.write(block)
        elif await self.path_io.is_dir(source_path):
            await self.make_directory(destination_path)
            sources = collections.deque([source_path])
            while sources:
                src = sources.popleft()
                async for path in self.path_io.list(src):
                    if write_into:
                        relative = destination_path.name / path.relative_to(source_path)
                    else:
                        relative = path.relative_to(source_path.parent)
                    if await self.path_io.is_dir(path):
                        await self.make_directory(relative)
                        sources.append(path)
                    else:
                        await self.upload(
                            path,
                            relative,
                            write_into=True,
                            block_size=block_size,
                        )

    def download_stream(
        self,
        source: _PathType,
        *,
        offset: int = 0,
    ) -> AsyncEnterableProtocol[DataConnectionThrottleStreamIO]:
        """
        :py:func:`asyncio.coroutine`

        Create stream for read data from `source` file.

        :param source: source path of file on server side
        :type source: :py:class:`str` or :py:class:`pathlib.PurePosixPath`

        :param offset: byte offset for stream start position
        :type offset: :py:class:`int`

        :rtype: :py:class:`aioftp.DataConnectionThrottleStreamIO`
        """
        return self.get_stream("RETR " + str(source), "1xx", offset=offset)

    async def download(
        self,
        source: _PathType,
        destination: _PathType = "",
        *,
        write_into: bool = False,
        block_size: int = DEFAULT_BLOCK_SIZE,
    ) -> None:
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
        source_path = pathlib.PurePosixPath(source)
        destination_path = pathlib.Path(destination)
        if not write_into:
            destination_path = destination_path / source_path.name
        if await self.is_file(source_path):
            await self.path_io.mkdir(
                destination_path.parent,
                parents=True,
                exist_ok=True,
            )
            async with self.path_io.open(destination_path, mode="wb") as file_out, self.download_stream(
                source_path,
            ) as stream:
                async for block in stream.iter_by_block(block_size):
                    await file_out.write(block)
        elif await self.is_dir(source_path):
            await self.path_io.mkdir(destination_path, parents=True, exist_ok=True)
            for name, info in await self.list(source_path):
                full = destination_path / name.relative_to(source_path)
                if info["type"] in ("file", "dir"):
                    await self.download(
                        name,
                        full,
                        write_into=True,
                        block_size=block_size,
                    )

    async def quit(self) -> None:
        """
        :py:func:`asyncio.coroutine`

        Send "QUIT" and close connection.
        """
        await self.command("QUIT", Code("2xx"))
        self.close()

    async def _do_epsv(self) -> Tuple[None, int]:
        _, info = await self.command("EPSV", Code("229"))
        ip, port = self.parse_epsv_response(info[-1])
        return ip, port

    async def _do_pasv(self) -> Tuple[str, int]:
        _, info = await self.command("PASV", Code("227"))
        ip, port = self.parse_pasv_response(info[-1])
        return ip, port

    async def get_passive_connection(
        self,
        conn_type: _ConnectionType = "I",
        commands: Optional[Sequence[str]] = None,
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        :py:func:`asyncio.coroutine`

        Getting pair of reader, writer for passive connection with server.

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :param commands: sequence of commands to try to initiate passive
            server creation. First success wins. Default is EPSV, then PASV.
            Overwrites the parameters passed when initializing the client.
        :type commands: :py:class:`list` or :py:class:`None`

        :rtype: (:py:class:`asyncio.StreamReader`,
            :py:class:`asyncio.StreamWriter`)
        """
        functions = {
            "epsv": self._do_epsv,
            "pasv": self._do_pasv,
        }
        if not commands:
            commands = self._passive_commands
        if not commands:
            raise ValueError("No passive commands provided")
        await self.command("TYPE " + conn_type, Code("200"))
        for i, name in enumerate(commands, start=1):
            name = name.lower()
            if name not in functions:
                raise ValueError(f"{name!r} not in {set(functions)!r}")
            try:
                ip, port = await functions[name]()
                break
            except errors.StatusCodeError as e:
                is_last = i == len(commands)
                if is_last or not e.received_codes[-1].matches("50x"):
                    raise
        if ip in ("0.0.0.0", None):  # type: ignore
            ip = self.server_host
        reader, writer = await self._open_connection(ip, port)  # type: ignore
        return reader, writer

    @async_enterable
    async def get_stream(
        self,
        *command_args: Any,
        conn_type: _ConnectionType = "I",
        offset: int = 0,
    ) -> DataConnectionThrottleStreamIO:
        """
        :py:func:`asyncio.coroutine`

        Create :py:class:`aioftp.DataConnectionThrottleStreamIO` for straight
        read/write io.

        :param command_args: arguments for :py:meth:`aioftp.Client.command`

        :param conn_type: connection type ("I", "A", "E", "L")
        :type conn_type: :py:class:`str`

        :param offset: byte offset for stream start position
        :type offset: :py:class:`int`

        :rtype: :py:class:`aioftp.DataConnectionThrottleStreamIO`
        """
        reader, writer = await self.get_passive_connection(conn_type)
        if offset:
            await self.command("REST " + str(offset), Code("350"))
        await self.command(*command_args)
        stream = DataConnectionThrottleStreamIO(
            self,
            reader,
            writer,
            throttles={"_": self.throttle},
            timeout=self.socket_timeout,
        )
        return stream

    async def abort(self, *, wait: bool = True) -> None:
        """
        :py:func:`asyncio.coroutine`

        Request data transfer abort.

        :param wait: wait for abort response [426]→226 if `True`
        :type wait: :py:class:`bool`
        """
        if wait:
            await self.command("ABOR", Code("226"), Code("426"))
        else:
            await self.command("ABOR")

    @classmethod
    @contextlib.asynccontextmanager
    async def context(
        cls,
        host: str,
        port: int = DEFAULT_PORT,
        user: str = DEFAULT_USER,
        password: str = DEFAULT_PASSWORD,
        account: str = DEFAULT_ACCOUNT,
        **kwargs: Any,
    ) -> AsyncIterator["Client"]:
        """
        Classmethod async context manager. This create
        :py:class:`aioftp.Client`, make async call to
        :py:meth:`aioftp.Client.connect`, :py:meth:`aioftp.Client.login`
        on enter and :py:meth:`aioftp.Client.quit` on exit.

        :param host: host name for connection
        :type host: :py:class:`str`

        :param port: port number for connection
        :type port: :py:class:`int`

        :param user: username
        :type user: :py:class:`str`

        :param password: password
        :type password: :py:class:`str`

        :param account: account (almost always blank)
        :type account: :py:class:`str`

        :param **kwargs: keyword arguments, which passed to
            :py:class:`aioftp.Client`

        ::

            >>> async with aioftp.Client.context("127.0.0.1") as client:
            ...     # do
        """
        client = cls(**kwargs)
        try:
            await client.connect(host, port)
            await client.login(user, password, account)
        except Exception:
            client.close()
            raise
        try:
            yield client
        finally:
            await client.quit()
