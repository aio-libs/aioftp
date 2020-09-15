import abc
import asyncio
import collections
import functools
import io
import operator
import pathlib
import stat
import sys
import time

from . import errors
from .common import (
    DEFAULT_BLOCK_SIZE,
    AbstractAsyncLister,
    AsyncStreamIterator,
    with_timeout,
)

__all__ = (
    "AbstractPathIO",
    "PathIO",
    "AsyncPathIO",
    "MemoryPathIO",
    "PathIONursery",
)


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
    def __init__(self, pathio, args, kwargs):
        self.close = None
        self.pathio = pathio
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        self.file = await self.pathio._open(*self.args, **self.kwargs)
        self.seek = functools.partial(self.pathio.seek, self.file)
        self.write = functools.partial(self.pathio.write, self.file)
        self.read = functools.partial(self.pathio.read, self.file)
        self.close = functools.partial(self.pathio.close, self.file)
        return self

    async def __aexit__(self, *args):
        if self.close is not None:
            await self.close()

    def __await__(self):
        return self.__aenter__().__await__()

    def iter_by_block(self, count=DEFAULT_BLOCK_SIZE):
        return AsyncStreamIterator(lambda: self.read(count))


def universal_exception(coro):
    """
    Decorator. Reraising any exception (except `CancelledError` and
    `NotImplementedError`) with universal exception
    :py:class:`aioftp.PathIOError`
    """
    @functools.wraps(coro)
    async def wrapper(*args, **kwargs):
        try:
            return await coro(*args, **kwargs)
        except (asyncio.CancelledError, NotImplementedError,
                StopAsyncIteration):
            raise
        except Exception as exc:
            raise errors.PathIOError(reason=sys.exc_info()) from exc

    return wrapper


class PathIONursery:

    def __init__(self, factory):
        self.factory = factory
        self.state = None

    def __call__(self, *args, **kwargs):
        instance = self.factory(*args, state=self.state, **kwargs)
        if self.state is None:
            self.state = instance.state
        return instance


def defend_file_methods(coro):
    """
    Decorator. Raises exception when file methods called with wrapped by
    :py:class:`aioftp.AsyncPathIOContext` file object.
    """
    @functools.wraps(coro)
    async def wrapper(self, file, *args, **kwargs):
        if isinstance(file, AsyncPathIOContext):
            raise ValueError("Native path io file methods can not be used "
                             "with wrapped file object")
        return await coro(self, file, *args, **kwargs)
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
    def __init__(self, timeout=None, connection=None, state=None):
        self.timeout = timeout
        self.connection = connection

    @property
    def state(self):
        """
        Shared pathio state per server
        """

    @universal_exception
    @abc.abstractmethod
    async def exists(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path exists

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def is_dir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is directory

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def is_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is file

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """

    @universal_exception
    @abc.abstractmethod
    async def mkdir(self, path, *, parents=False, exist_ok=False):
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
    async def rmdir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove directory

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """

    @universal_exception
    @abc.abstractmethod
    async def unlink(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove file

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """

    @abc.abstractmethod
    def list(self, path):
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
    async def stat(self, path):
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
    async def _open(self, path, mode):
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

    def open(self, *args, **kwargs):
        """
        Create instance of :py:class:`aioftp.pathio.AsyncPathIOContext`,
        parameters passed to :py:meth:`aioftp.AbstractPathIO._open`

        :rtype: :py:class:`aioftp.pathio.AsyncPathIOContext`
        """
        return AsyncPathIOContext(self, args, kwargs)

    @universal_exception
    @defend_file_methods
    @abc.abstractmethod
    async def seek(self, file, offset, whence=io.SEEK_SET):
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
    async def write(self, file, data):
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
    async def read(self, file, block_size):
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
    async def close(self, file):
        """
        :py:func:`asyncio.coroutine`

        Close file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`
        """

    @universal_exception
    @abc.abstractmethod
    async def rename(self, source, destination):
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

    @universal_exception
    async def exists(self, path):
        return path.exists()

    @universal_exception
    async def is_dir(self, path):
        return path.is_dir()

    @universal_exception
    async def is_file(self, path):
        return path.is_file()

    @universal_exception
    async def mkdir(self, path, *, parents=False, exist_ok=False):
        return path.mkdir(parents=parents, exist_ok=exist_ok)

    @universal_exception
    async def rmdir(self, path):
        return path.rmdir()

    @universal_exception
    async def unlink(self, path):
        return path.unlink()

    def list(self, path):

        class Lister(AbstractAsyncLister):
            iter = None

            @universal_exception
            async def __anext__(self):
                if self.iter is None:
                    self.iter = path.glob("*")
                try:
                    return next(self.iter)
                except StopIteration:
                    raise StopAsyncIteration

        return Lister(timeout=self.timeout)

    @universal_exception
    async def stat(self, path):
        return path.stat()

    @universal_exception
    async def _open(self, path, *args, **kwargs):
        return path.open(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def seek(self, file, *args, **kwargs):
        return file.seek(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def write(self, file, *args, **kwargs):
        return file.write(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def read(self, file, *args, **kwargs):
        return file.read(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def close(self, file):
        return file.close()

    @universal_exception
    async def rename(self, source, destination):
        return source.rename(destination)


def _blocking_io(f):
    @functools.wraps(f)
    async def wrapper(self, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(
            self.executor,
            functools.partial(f, self, *args, **kwargs),
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
    def __init__(self, *args, executor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = executor

    @universal_exception
    @with_timeout
    @_blocking_io
    def exists(self, path):
        return path.exists()

    @universal_exception
    @with_timeout
    @_blocking_io
    def is_dir(self, path):
        return path.is_dir()

    @universal_exception
    @with_timeout
    @_blocking_io
    def is_file(self, path):
        return path.is_file()

    @universal_exception
    @with_timeout
    @_blocking_io
    def mkdir(self, path, *, parents=False, exist_ok=False):
        return path.mkdir(parents=parents, exist_ok=exist_ok)

    @universal_exception
    @with_timeout
    @_blocking_io
    def rmdir(self, path):
        return path.rmdir()

    @universal_exception
    @with_timeout
    @_blocking_io
    def unlink(self, path):
        return path.unlink()

    def list(self, path):

        class Lister(AbstractAsyncLister):
            iter = None

            def __init__(self, *args, executor=None, **kwargs):
                super().__init__(*args, **kwargs)
                self.executor = executor

            def worker(self):
                try:
                    return next(self.iter)
                except StopIteration:
                    raise StopAsyncIteration

            @universal_exception
            @with_timeout
            @_blocking_io
            def __anext__(self):
                if self.iter is None:
                    self.iter = path.glob("*")
                return self.worker()

        return Lister(timeout=self.timeout, executor=self.executor)

    @universal_exception
    @with_timeout
    @_blocking_io
    def stat(self, path):
        return path.stat()

    @universal_exception
    @with_timeout
    @_blocking_io
    def _open(self, path, *args, **kwargs):
        return path.open(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def seek(self, file, *args, **kwargs):
        return file.seek(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def write(self, file, *args, **kwargs):
        return file.write(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def read(self, file, *args, **kwargs):
        return file.read(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    @with_timeout
    @_blocking_io
    def close(self, file):
        return file.close()

    @universal_exception
    @with_timeout
    @_blocking_io
    def rename(self, source, destination):
        return source.rename(destination)


class Node:

    def __init__(self, type, name, ctime=None, mtime=None, *, content):
        self.type = type
        self.name = name
        self.ctime = ctime or int(time.time())
        self.mtime = mtime or int(time.time())
        self.content = content

    def __repr__(self):
        return f"{self.__class__.__name__}(type={self.type!r}, " \
               f"name={self.name!r}, ctime={self.ctime!r}, " \
               f"mtime={self.mtime!r}, content={self.content!r})"


class MemoryPathIO(AbstractPathIO):
    """
    Non-blocking path io. Based on in-memory tree. It is just proof of concept
    and probably not so fast as it can be.
    """

    Stats = collections.namedtuple(
        "Stats",
        (
            "st_size",
            "st_ctime",
            "st_mtime",
            "st_nlink",
            "st_mode",
        )
    )

    def __init__(self, *args, state=None, cwd=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwd = pathlib.PurePosixPath(cwd or "/")
        if state is None:
            self.fs = [Node("dir", "/", content=[])]
        else:
            self.fs = state

    @property
    def state(self):
        return self.fs

    def __repr__(self):
        return repr(self.fs)

    def _absolute(self, path):
        if not path.is_absolute():
            path = self.cwd / path
        return path

    def get_node(self, path):
        nodes = self.fs
        node = None
        path = self._absolute(path)
        for part in path.parts:
            if not isinstance(nodes, list):
                return
            for node in nodes:
                if node.name == part:
                    nodes = node.content
                    break
            else:
                return
        return node

    @universal_exception
    async def exists(self, path):
        return self.get_node(path) is not None

    @universal_exception
    async def is_dir(self, path):
        node = self.get_node(path)
        return not (node is None or node.type != "dir")

    @universal_exception
    async def is_file(self, path):
        node = self.get_node(path)
        return not (node is None or node.type != "file")

    @universal_exception
    async def mkdir(self, path, *, parents=False, exist_ok=False):
        path = self._absolute(path)
        node = self.get_node(path)
        if node:
            if node.type != "dir" or not exist_ok:
                raise FileExistsError
        elif not parents:
            parent = self.get_node(path.parent)
            if parent is None:
                raise FileNotFoundError
            if parent.type != "dir":
                raise NotADirectoryError
            node = Node("dir", path.name, content=[])
            parent.content.append(node)
        else:
            nodes = self.fs
            for part in path.parts:
                if isinstance(nodes, list):
                    for node in nodes:
                        if node.name == part:
                            nodes = node.content
                            break
                    else:
                        node = Node("dir", part, content=[])
                        nodes.append(node)
                        nodes = node.content
                else:
                    raise NotADirectoryError

    @universal_exception
    async def rmdir(self, path):
        node = self.get_node(path)
        if node is None:
            raise FileNotFoundError
        if node.type != "dir":
            raise NotADirectoryError
        if node.content:
            raise OSError("Directory not empty")

        parent = self.get_node(path.parent)
        for i, node in enumerate(parent.content):
            if node.name == path.name:
                break
        parent.content.pop(i)

    @universal_exception
    async def unlink(self, path):
        node = self.get_node(path)
        if node is None:
            raise FileNotFoundError
        if node.type != "file":
            raise IsADirectoryError

        parent = self.get_node(path.parent)
        for i, node in enumerate(parent.content):
            if node.name == path.name:
                break
        parent.content.pop(i)

    def list(self, path):

        class Lister(AbstractAsyncLister):
            iter = None

            @universal_exception
            async def __anext__(cls):
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

    @universal_exception
    async def stat(self, path):
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

    @universal_exception
    async def _open(self, path, mode="rb", *args, **kwargs):
        if mode == "rb":
            node = self.get_node(path)
            if node is None:
                raise FileNotFoundError
            file_like = node.content
            file_like.seek(0, io.SEEK_SET)
        elif mode in ("wb", "ab", "r+b"):
            node = self.get_node(path)
            if node is None:
                parent = self.get_node(path.parent)
                if parent is None or parent.type != "dir":
                    raise FileNotFoundError
                new_node = Node("file", path.name, content=io.BytesIO())
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
        return file_like

    @universal_exception
    @defend_file_methods
    async def seek(self, file, *args, **kwargs):
        return file.seek(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def write(self, file, *args, **kwargs):
        file.write(*args, **kwargs)
        file.mtime = int(time.time())

    @universal_exception
    @defend_file_methods
    async def read(self, file, *args, **kwargs):
        return file.read(*args, **kwargs)

    @universal_exception
    @defend_file_methods
    async def close(self, file):
        pass

    @universal_exception
    async def rename(self, source, destination):
        if source != destination:
            sparent = self.get_node(source.parent)
            dparent = self.get_node(destination.parent)
            snode = self.get_node(source)
            if None in (snode, dparent):
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
