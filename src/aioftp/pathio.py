import abc
import asyncio
import functools
import io
import operator
import os
import pathlib
import stat
import sys
import time
import typing
from concurrent import futures
from typing import (
    Any,
    Awaitable,
    BinaryIO,
    Callable,
    Coroutine,
    Dict,
    Generator,
    List,
    Literal,
    NamedTuple,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import ParamSpec, Protocol, Self, TypeAlias, override

from . import errors
from .common import (
    DEFAULT_BLOCK_SIZE,
    AbstractAsyncLister,
    AsyncStreamIterator,
    with_timeout,
)
from .types import OpenMode, StatsProtocol
from .utils import get_param

if typing.TYPE_CHECKING:
    from .server import Connection

__all__ = (
    "AbstractPathIO",
    "PathIO",
    "AsyncPathIO",
    "MemoryPathIO",
    "PathIONursery",
)

_Ps = ParamSpec("_Ps")
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)


class _DirNodeProtocol(Protocol):
    type: Literal["dir"]
    name: str
    ctime: int
    mtime: int
    content: List[Union["_FileNodeProtocol", "_DirNodeProtocol"]]


class _FileNodeProtocol(Protocol):
    type: Literal["file"]
    name: str
    ctime: int
    mtime: int
    content: io.BytesIO


_NodeProtocol: TypeAlias = Union[_DirNodeProtocol, _FileNodeProtocol]
_NodeType: TypeAlias = Literal["file", "dir"]


class SupportsNext(Protocol[_T_co]):
    @abc.abstractmethod
    def __next__(self) -> _T_co:
        raise NotImplementedError


class AsyncPathIOContext:
    """
    Async pathio context.

    Usage:
    ::

        >>> async with pathio.open(filename) as file_in:
        ...     async for block in file_in.iter_by_block(size):
        ...         # do

    or borring:
    ::

        >>> file = await pathio.open(filename)
        ... data = await file.read(size)
        ... await file.write(data)
        ... await file.close()

    """

    seek: "functools.partial[Awaitable[int]]"
    write: "functools.partial[Awaitable[int]]"
    read: "functools.partial[Awaitable[bytes]]"
    close: Optional["functools.partial[Awaitable[None]]"]
    pathio: "AbstractPathIO"
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]

    def __init__(self, pathio: "AbstractPathIO", args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
        self.close = None
        self.pathio = pathio
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self) -> Self:
        self.file = await self.pathio._open(*self.args, **self.kwargs)  # pyright: ignore[reportPrivateUsage]
        self.seek = functools.partial(self.pathio.seek, self.file)
        self.write = functools.partial(self.pathio.write, self.file)
        self.read = functools.partial(self.pathio.read, self.file)
        self.close = functools.partial(self.pathio.close, self.file)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self.close is not None:
            await self.close()

    def __await__(self) -> Generator[None, None, "AsyncPathIOContext"]:
        return self.__aenter__().__await__()

    def iter_by_block(self, count: int = DEFAULT_BLOCK_SIZE) -> AsyncStreamIterator[bytes]:
        return AsyncStreamIterator(lambda: self.read(count))


def universal_exception(coro: Callable[_Ps, Coroutine[None, None, _T]]) -> Callable[_Ps, Coroutine[None, None, _T]]:
    """
    Decorator. Reraising any exception (except `CancelledError` and
    `NotImplementedError`) with universal exception
    :py:class:`aioftp.PathIOError`
    """

    @functools.wraps(coro)
    async def wrapper(*args: _Ps.args, **kwargs: _Ps.kwargs) -> _T:
        try:
            return await coro(*args, **kwargs)
        except (
            asyncio.CancelledError,
            NotImplementedError,
            StopAsyncIteration,
        ):
            raise
        except Exception as exc:
            raise errors.PathIOError(reason=sys.exc_info()) from exc

    return wrapper


class PathIONursery:
    state: Optional[Union[List[_NodeProtocol], io.BytesIO]]
    factory: Type["AbstractPathIO"]

    def __init__(self, factory: Type["AbstractPathIO"]):
        self.factory = factory
        self.state = None

    def __call__(self, *args: Any, **kwargs: Any) -> "AbstractPathIO":
        instance = self.factory(*args, state=self.state, **kwargs)  # type: ignore
        if self.state is None:
            self.state = instance.state
        return instance


def defend_file_methods(
    coro: Callable[_Ps, Coroutine[None, None, _T]],
) -> Callable[_Ps, Coroutine[None, None, _T]]:
    """
    Decorator. Raises exception when file methods called with wrapped by
    :py:class:`aioftp.AsyncPathIOContext` file object.
    """

    @functools.wraps(coro)
    async def wrapper(
        *args: _Ps.args,
        **kwargs: _Ps.kwargs,
    ) -> _T:
        file = get_param((1, "file"), args, kwargs)
        if isinstance(file, AsyncPathIOContext):
            raise ValueError(
                "Native path io file methods can not be used with wrapped file object",
            )
        return await coro(*args, **kwargs)

    return wrapper


class AbstractPathIO(abc.ABC):
    """
    Abstract class for path io operations.

    :param timeout: timeout used by `with_timeout` decorator
    :type timeout: :py:class:`float`, :py:class:`int` or `None`

    :param connection: server connection that is accessing this PathIO
    :type connection: :py:class:`aioftp.Connection`

    :param state: shared pathio state per server
    """

    timeout: Optional[Union[float, int]]
    connection: Optional["Connection"]

    def __init__(
        self,
        timeout: Optional[Union[float, int]] = None,
        connection: Optional["Connection"] = None,
        state: Optional[List[_NodeProtocol]] = None,
    ):
        self.timeout = timeout
        self.connection = connection

    @property
    def state(self) -> Optional[Union[List[_NodeProtocol], io.BytesIO]]:
        """
        Shared pathio state per server
        """
        return None

    @universal_exception
    @abc.abstractmethod
    async def exists(self, path: pathlib.Path) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Check if path exists

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def is_dir(self, path: pathlib.Path) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Check if path is directory

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def is_file(self, path: pathlib.Path) -> bool:
        """
        :py:func:`asyncio.coroutine`

        Check if path is file

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def mkdir(self, path: pathlib.Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        """
        :py:func:`asyncio.coroutine`

        Make directory

        :param path: path to create
        :type path: :py:class:`pathlib.Path`

        :param parents: create parents is does not exists
        :type parents: :py:class:`bool`

        :param exist_ok: do not raise exception if directory already exists
        :type exist_ok: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def rmdir(self, path: pathlib.Path) -> None:
        """
        :py:func:`asyncio.coroutine`

        Remove directory

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """

    @universal_exception
    @abc.abstractmethod
    async def unlink(self, path: pathlib.Path) -> None:
        """
        :py:func:`asyncio.coroutine`

        Remove file

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """

    @abc.abstractmethod
    def list(self, path: pathlib.Path) -> AbstractAsyncLister[Any]:
        """
        Create instance of subclass of :py:class:`aioftp.AbstractAsyncLister`.
        You should subclass and implement `__anext__` method
        for :py:class:`aioftp.AbstractAsyncLister` and return new instance.

        :param path: path to list
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`aioftp.AbstractAsyncLister`

        Usage:
        ::

            >>> async for p in pathio.list(path):
            ...     # do

        or borring instance of :py:class:`list`:
        ::

            >>> paths = await pathio.list(path)
            >>> paths
            [path, path, path, ...]

        """

    @universal_exception
    @abc.abstractmethod
    async def stat(self, path: pathlib.Path) -> StatsProtocol:
        """
        :py:func:`asyncio.coroutine`

        Get path stats

        :param path: path, which stats need
        :type path: :py:class:`pathlib.Path`

        :return: path stats. For proper work you need only this stats:
          st_size, st_mtime, st_ctime, st_nlink, st_mode
        :rtype: same as :py:class:`os.stat_result`
        """

    @universal_exception
    @abc.abstractmethod
    async def _open(self, path: pathlib.Path, mode: OpenMode) -> BinaryIO:
        """
        :py:func:`asyncio.coroutine`

        Open file. You should implement "mode" argument, which can be:
        "rb", "wb", "ab" (read, write, append. all binary). Return type depends
        on implementation, anyway the only place you need this file-object
        is in your implementation of read, write and close

        :param path: path to create
        :type path: :py:class:`pathlib.Path`

        :param mode: specifies the mode in which the file is opened ("rb",
            "wb", "ab", "r+b" (read, write, append, read/write, all binary))
        :type mode: :py:class:`str`

        :return: file-object
        """

    def open(self, *args: Any, **kwargs: Any) -> AsyncPathIOContext:
        """
        Create instance of :py:class:`aioftp.pathio.AsyncPathIOContext`,
        parameters passed to :py:meth:`aioftp.AbstractPathIO._open`

        :rtype: :py:class:`aioftp.pathio.AsyncPathIOContext`
        """
        return AsyncPathIOContext(self, args, kwargs)

    @universal_exception
    @defend_file_methods
    @abc.abstractmethod
    async def seek(self, file: BinaryIO, offset: int, whence: int = io.SEEK_SET) -> int:
        """
        :py:func:`asyncio.coroutine`

        Change the stream position to the given byte `offset`. Same behaviour
        as :py:meth:`io.IOBase.seek`

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param offset: relative byte offset
        :type offset: :py:class:`int`

        :param whence: base position for offset
        :type whence: :py:class:`int`
        """

    @universal_exception
    @defend_file_methods
    @abc.abstractmethod
    async def write(self, file: BinaryIO, data: bytes) -> int:
        """
        :py:func:`asyncio.coroutine`

        Write some data to file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param data: data to write
        :type data: :py:class:`bytes`
        """

    @universal_exception
    @defend_file_methods
    @abc.abstractmethod
    async def read(self, file: BinaryIO, block_size: int) -> bytes:
        """
        :py:func:`asyncio.coroutine`

        Read some data from file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param block_size: bytes count to read
        :type block_size: :py:class:`int`

        :rtype: :py:class:`bytes`
        """

    @universal_exception
    @defend_file_methods
    @abc.abstractmethod
    async def close(self, file: BinaryIO) -> None:
        """
        :py:func:`asyncio.coroutine`

        Close file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`
        """

    @universal_exception
    @abc.abstractmethod
    async def rename(self, source: pathlib.Path, destination: pathlib.Path) -> Optional[pathlib.Path]:
        """
        :py:func:`asyncio.coroutine`

        Rename path

        :param source: rename from
        :type source: :py:class:`pathlib.Path`

        :param destination: rename to
        :type destination: :py:class:`pathlib.Path`
        """


class PathIO(AbstractPathIO):
    """
    Blocking path io. Directly based on :py:class:`pathlib.Path` methods.
    """

    @override
    @universal_exception
    async def exists(self, path: pathlib.Path) -> bool:
        return path.exists()

    @override
    @universal_exception
    async def is_dir(self, path: pathlib.Path) -> bool:
        return path.is_dir()

    @override
    @universal_exception
    async def is_file(self, path: pathlib.Path) -> bool:
        return path.is_file()

    @override
    @universal_exception
    async def mkdir(self, path: pathlib.Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        return path.mkdir(parents=parents, exist_ok=exist_ok)

    @override
    @universal_exception
    async def rmdir(self, path: pathlib.Path) -> None:
        return path.rmdir()

    @override
    @universal_exception
    async def unlink(self, path: pathlib.Path) -> None:
        return path.unlink()

    @override
    def list(self, path: pathlib.Path) -> AbstractAsyncLister[pathlib.Path]:
        class Lister(AbstractAsyncLister[pathlib.Path]):
            iter: Optional[Generator[pathlib.Path, None, None]] = None

            @override
            @universal_exception
            async def __anext__(self) -> pathlib.Path:
                if self.iter is None:
                    self.iter = path.glob("*")
                try:
                    return next(self.iter)
                except StopIteration:
                    raise StopAsyncIteration

        return Lister(timeout=self.timeout)

    @override
    @universal_exception
    async def stat(self, path: pathlib.Path) -> os.stat_result:
        return path.stat()

    @override
    @universal_exception
    async def _open(self, path: pathlib.Path, mode: OpenMode) -> BinaryIO:
        return path.open(mode)

    @override
    @universal_exception
    @defend_file_methods
    async def seek(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        return file.seek(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    async def write(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        return file.write(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    async def read(self, file: BinaryIO, *args: Any, **kwargs: Any) -> bytes:
        return file.read(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    async def close(self, file: BinaryIO) -> None:
        return file.close()

    @override
    @universal_exception
    async def rename(self, source: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
        return source.rename(destination)


def _blocking_io(
    f: Callable[_Ps, _T],
) -> Callable[_Ps, Coroutine[None, None, _T]]:
    @functools.wraps(f)
    async def wrapper(
        *args: _Ps.args,
        **kwargs: _Ps.kwargs,
    ) -> _T:
        self: "AsyncPathIO" = get_param((0, "self"), args, kwargs)
        return await asyncio.get_running_loop().run_in_executor(
            self.executor,
            functools.partial(f, *args, **kwargs),
        )

    return wrapper


class AsyncPathIO(AbstractPathIO):
    """
    Non-blocking path io. Based on
    :py:meth:`asyncio.BaseEventLoop.run_in_executor` and
    :py:class:`pathlib.Path` methods. It's really slow, so it's better to avoid
    usage of this path io layer.

    :param executor: executor for running blocking tasks
    :type executor: :py:class:`concurrent.futures.Executor`
    """

    executor: Optional[futures.Executor]

    def __init__(
        self,
        *args: Any,
        executor: Optional[futures.Executor] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.executor = executor

    @override
    # @universal_exception
    # @with_timeout
    @_blocking_io
    def exists(self, path: pathlib.Path) -> bool:
        return path.exists()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def is_dir(self, path: pathlib.Path) -> bool:
        return path.is_dir()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def is_file(self, path: pathlib.Path) -> bool:
        return path.is_file()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def mkdir(
        self,
        path: pathlib.Path,
        *,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        return path.mkdir(parents=parents, exist_ok=exist_ok)

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def rmdir(self, path: pathlib.Path) -> None:
        return path.rmdir()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def unlink(self, path: pathlib.Path) -> None:
        return path.unlink()

    @override
    def list(self, path: pathlib.Path) -> AbstractAsyncLister[pathlib.Path]:
        class Lister(AbstractAsyncLister[pathlib.Path]):
            iter: Optional[SupportsNext[pathlib.Path]] = None

            def __init__(self, *args: Any, executor: Optional[futures.Executor] = None, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.executor = executor

            def worker(self) -> pathlib.Path:
                try:
                    return next(self.iter)  # type: ignore
                except StopIteration:
                    raise StopAsyncIteration

            @override
            @universal_exception
            @with_timeout
            @_blocking_io
            def __anext__(self) -> pathlib.Path:
                if self.iter is None:
                    self.iter = path.glob("*")
                return self.worker()

        return Lister(timeout=self.timeout, executor=self.executor)

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def stat(self, path: pathlib.Path) -> os.stat_result:
        return path.stat()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def _open(self, path: pathlib.Path, *args: Any, **kwargs: Any) -> BinaryIO:
        return cast(BinaryIO, path.open(*args, **kwargs))

    @override
    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def seek(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        return file.seek(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def write(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        return file.write(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def read(self, file: BinaryIO, *args: Any, **kwargs: Any) -> bytes:
        return file.read(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def close(self, file: BinaryIO) -> None:
        return file.close()

    @override
    @universal_exception
    @with_timeout
    @_blocking_io
    def rename(self, source: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
        return source.rename(destination)


class Node:
    type: _NodeType
    name: str
    ctime: int
    mtime: int
    content: Union[List["Node"], io.BytesIO]

    @overload
    def __init__(
        self,
        type: Literal["file"],
        name: str,
        ctime: Optional[int] = None,
        mtime: Optional[int] = None,
        *,
        content: io.BytesIO,
    ) -> None: ...

    @overload
    def __init__(
        self,
        type: Literal["dir"],
        name: str,
        ctime: Optional[int] = None,
        mtime: Optional[int] = None,
        *,
        content: List["Node"],
    ) -> None: ...

    def __init__(
        self,
        type: _NodeType,
        name: str,
        ctime: Optional[int] = None,
        mtime: Optional[int] = None,
        *,
        content: Union[List["Node"], io.BytesIO],
    ) -> None:
        self.type = type
        self.name = name
        self.ctime = ctime or int(time.time())
        self.mtime = mtime or int(time.time())
        self.content = content

    @override
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(type={self.type!r}, "
            f"name={self.name!r}, ctime={self.ctime!r}, "
            f"mtime={self.mtime!r}, content={self.content!r})"
        )


class MemoryPathIO(AbstractPathIO):
    """
    Non-blocking path io. Based on in-memory tree. It is just proof of concept
    and probably not so fast as it can be.
    """

    class Stats(NamedTuple):
        st_size: int
        st_ctime: int
        st_mtime: int
        st_nlink: int
        st_mode: int

    fs: Union[List[_NodeProtocol], io.BytesIO]
    cwd: pathlib.PurePosixPath

    def __init__(
        self,
        *args: Any,
        state: Optional[Union[List[_NodeProtocol], io.BytesIO]] = None,
        cwd: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cwd = pathlib.PurePosixPath(cwd or "/")
        if state is None:
            self.fs = [cast(_DirNodeProtocol, Node("dir", "/", content=[]))]
        else:
            self.fs = state

    @property
    @override
    def state(self) -> Union[List[_NodeProtocol], io.BytesIO]:
        return self.fs

    @override
    def __repr__(self) -> str:
        return repr(self.fs)

    def _absolute(self, path: pathlib.PurePath) -> pathlib.PurePath:
        if not path.is_absolute():
            path = self.cwd / path
        return path

    def get_node(self, path: pathlib.PurePath) -> Optional[_NodeProtocol]:
        nodes: Union[List[_NodeProtocol], io.BytesIO] = self.fs
        node = None
        path_ = self._absolute(path)
        for part in path_.parts:
            if not isinstance(nodes, list):
                return None
            for node in nodes:
                if node.name == part:
                    nodes = node.content
                    break
            else:
                return None
        return node

    @override
    @universal_exception
    async def exists(self, path: pathlib.Path) -> bool:
        return self.get_node(path) is not None

    @override
    @universal_exception
    async def is_dir(self, path: pathlib.Path) -> bool:
        node = self.get_node(path)
        return not (node is None or node.type != "dir")

    @override
    @universal_exception
    async def is_file(self, path: pathlib.Path) -> bool:
        node = self.get_node(path)
        return not (node is None or node.type != "file")

    @override
    @universal_exception
    async def mkdir(
        self,
        path: pathlib.Path,
        *,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        path_ = self._absolute(path)
        node = self.get_node(path_)
        if node:
            if node.type != "dir" or not exist_ok:
                raise FileExistsError
        elif not parents:
            parent = self.get_node(path_.parent)
            if parent is None:
                raise FileNotFoundError
            if parent.type != "dir":
                raise NotADirectoryError
            node = cast(_DirNodeProtocol, Node("dir", path.name, content=[]))
            parent.content.append(node)
        else:
            nodes: Union[List[_NodeProtocol], io.BytesIO] = self.fs
            for part in path_.parts:
                if isinstance(nodes, list):
                    for node in nodes:
                        if node.name == part:
                            nodes = node.content
                            break
                    else:
                        node = cast(_DirNodeProtocol, Node("dir", part, content=[]))
                        nodes.append(node)
                        nodes = node.content
                else:
                    raise NotADirectoryError

    @override
    @universal_exception
    async def rmdir(self, path: pathlib.Path) -> None:
        node = self.get_node(path)
        if node is None:
            raise FileNotFoundError
        if node.type != "dir":
            raise NotADirectoryError

        if node.content:
            raise OSError("Directory not empty")

        parent = cast(_DirNodeProtocol, self.get_node(path.parent))
        for i, node in enumerate(parent.content):
            if node.name == path.name:
                break
        parent.content.pop(i)  # pyright: ignore[reportPossiblyUnboundVariable]

    @override
    @universal_exception
    async def unlink(self, path: pathlib.Path) -> None:
        node = self.get_node(path)
        if node is None:
            raise FileNotFoundError
        if node.type != "file":
            raise IsADirectoryError

        parent = cast(_DirNodeProtocol, self.get_node(path.parent))
        for i, node in enumerate(parent.content):
            if node.name == path.name:
                break
        parent.content.pop(i)  # pyright: ignore[reportPossiblyUnboundVariable]

    @override
    def list(self, path: pathlib.Path) -> "AbstractAsyncLister[pathlib.Path]":
        class Lister(AbstractAsyncLister[pathlib.Path]):
            iter: Optional[SupportsNext[pathlib.Path]] = None

            @override
            @universal_exception
            async def __anext__(cls) -> pathlib.Path:
                if cls.iter is None:
                    node = self.get_node(path)
                    if node is None or node.type != "dir":
                        cls.iter = iter(())
                    else:
                        names = map(operator.attrgetter("name"), node.content)
                        paths = map(lambda name: path / name, names)
                        cls.iter = iter(paths)
                try:
                    return next(cls.iter)
                except StopIteration:
                    raise StopAsyncIteration

        return Lister(timeout=self.timeout)

    @override
    @universal_exception
    async def stat(self, path: pathlib.Path) -> "MemoryPathIO.Stats":
        node = self.get_node(path)
        if node is None:
            raise FileNotFoundError

        if node.type == "file":
            size = len(node.content.getbuffer())
            mode = stat.S_IFREG | 0o666
        else:
            size = 0
            mode = stat.S_IFDIR | 0o777
        return MemoryPathIO.Stats(
            size,
            node.ctime,
            node.mtime,
            1,
            mode,
        )

    @override
    @universal_exception
    async def _open(self, path: pathlib.Path, mode: OpenMode = "rb", *args: Any, **kwargs: Any) -> io.BytesIO:
        if mode == "rb":
            node = cast(Optional[_FileNodeProtocol], self.get_node(path))
            if node is None:
                raise FileNotFoundError
            file_like = node.content
            file_like.seek(0, io.SEEK_SET)
        elif mode in ("wb", "ab", "r+b"):
            node = cast(Optional[_FileNodeProtocol], self.get_node(path))
            if node is None:
                parent = self.get_node(path.parent)
                if parent is None or parent.type != "dir":
                    raise FileNotFoundError
                new_node = cast(_FileNodeProtocol, Node("file", path.name, content=io.BytesIO()))
                parent.content.append(new_node)
                file_like = new_node.content
            elif node.type != "file":
                raise IsADirectoryError
            else:
                if mode == "wb":
                    file_like = node.content = io.BytesIO()
                elif mode == "ab":
                    file_like = node.content
                    file_like.seek(0, io.SEEK_END)
                elif mode == "r+b":
                    file_like = node.content
                    file_like.seek(0, io.SEEK_SET)
        else:
            raise ValueError(f"invalid mode: {mode}")
        return file_like  # type: ignore

    @override
    @universal_exception
    @defend_file_methods
    async def seek(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        return file.seek(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    async def write(self, file: BinaryIO, *args: Any, **kwargs: Any) -> int:
        result = file.write(*args, **kwargs)
        file.mtime = int(time.time())  # type: ignore
        return result

    @override
    @universal_exception
    @defend_file_methods
    async def read(self, file: BinaryIO, *args: Any, **kwargs: Any) -> bytes:
        return file.read(*args, **kwargs)

    @override
    @universal_exception
    @defend_file_methods
    async def close(self, file: BinaryIO) -> None:
        pass

    @override
    @universal_exception
    async def rename(self, source: pathlib.Path, destination: pathlib.Path) -> Optional[pathlib.Path]:
        if source != destination:
            sparent = cast(_DirNodeProtocol, self.get_node(source.parent))
            dparent = cast(Optional[_DirNodeProtocol], self.get_node(destination.parent))
            snode = self.get_node(source)
            if snode is None or dparent is None:
                raise FileNotFoundError
            for i, node in enumerate(sparent.content):
                if node.name == source.name:
                    sparent.content.pop(i)
            snode.name = destination.name
            for i, node in enumerate(dparent.content):
                if node.name == destination.name:
                    dparent.content[i] = snode
                    break
            else:
                dparent.content.append(snode)
        return None
