import asyncio
import functools
import collections
import operator
import io
import time
import sys

from .common import (with_timeout, AsyncStreamIterator, DEFAULT_BLOCK_SIZE,
                     AbstractAsyncLister)
from . import errors


__all__ = (
    "AbstractPathIO",
    "PathIO",
    "AsyncPathIO",
    "MemoryPathIO",
)


class AsyncPathIOContext:
    """
    Async pathio context.

    Usage:
    ::

        >>> async with pathio.open(filename) as file_in:
        ...
        ...     async for block in file_in.iter_by_block(size):
        ...
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

        except asyncio.CancelledError:

            raise

        except NotImplementedError:

            raise

        except StopAsyncIteration:

            raise

        except:

            raise errors.PathIOError(reason=sys.exc_info())

    return wrapper


class AbstractPathIO:
    """
    Abstract class for path io operations.

    :param timeout: timeout used by `with_timeout` decorator
    :type timeout: :py:class:`float`, :py:class:`int` or `None`

    :param loop: loop to use
    :type loop: :py:class:`asyncio.BaseEventLoop`
    """

    def __init__(self, timeout=None, loop=None):

        self.timeout = timeout
        self.loop = loop or asyncio.get_event_loop()

    @universal_exception
    async def exists(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path exists

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @universal_exception
    async def is_dir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is directory

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @universal_exception
    async def is_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is file

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @universal_exception
    async def mkdir(self, path, *, parents=False):
        """
        :py:func:`asyncio.coroutine`

        Make directory

        :param path: path to create
        :type path: :py:class:`pathlib.Path`

        :param parents: create parents is does not exists
        :type parents: :py:class:`bool`
        """
        raise NotImplementedError

    @universal_exception
    async def rmdir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove directory

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """
        raise NotImplementedError

    @universal_exception
    async def unlink(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove file

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """
        raise NotImplementedError

    def list(self, path):
        """
        Create instance of subclass of :py:class:`aioftp.AbstractAsyncLister`.
        You should subclass and implement `__aiter__` and `__anext__` methods
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
        raise NotImplementedError

    @universal_exception
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
        raise NotImplementedError

    @universal_exception
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
            "wb", "ab" (read, write, append, all binary))
        :type mode: :py:class:`str`

        :return: file-object
        """
        raise NotImplementedError

    def open(self, *args, **kwargs):
        """
        Create instance of :py:class:`aioftp.pathio.AsyncPathIOContext`,
        parameters passed to :py:meth:`aioftp.AbstractPathIO._open`

        :rtype: :py:class:`aioftp.pathio.AsyncPathIOContext`
        """
        return AsyncPathIOContext(self, args, kwargs)

    @universal_exception
    async def write(self, file, data):
        """
        :py:func:`asyncio.coroutine`

        Write some data to file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param data: data to write
        :type data: :py:class:`bytes`
        """
        raise NotImplementedError

    @universal_exception
    async def read(self, file, block_size):
        """
        :py:func:`asyncio.coroutine`

        Read some data from file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param block_size: bytes count to read
        :type block_size: :py:class:`int`

        :rtype: :py:class:`bytes`
        """
        raise NotImplementedError

    @universal_exception
    async def close(self, file):
        """
        :py:func:`asyncio.coroutine`

        Close file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`
        """
        raise NotImplementedError

    @universal_exception
    async def rename(self, source, destination):
        """
        :py:func:`asyncio.coroutine`

        Rename path

        :param source: rename from
        :type source: :py:class:`pathlib.Path`

        :param destination: rename to
        :type destination: :py:class:`pathlib.Path`
        """
        raise NotImplementedError


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
    async def mkdir(self, path, *, parents=False):

        return path.mkdir(parents=parents)

    @universal_exception
    async def rmdir(self, path):

        return path.rmdir()

    @universal_exception
    async def unlink(self, path):

        return path.unlink()

    def list(self, path):

        class Lister(AbstractAsyncLister):

            @universal_exception
            async def __aiter__(self):

                self.iter = path.glob("*")
                return self

            @universal_exception
            async def __anext__(self):

                try:

                    return next(self.iter)

                except StopIteration:

                    raise StopAsyncIteration

        return Lister(timeout=self.timeout, loop=self.loop)

    @universal_exception
    async def stat(self, path):

        return path.stat()

    @universal_exception
    async def _open(self, path, *args, **kwargs):

        return path.open(*args, **kwargs)

    @universal_exception
    async def write(self, file, *args, **kwargs):

        return file.write(*args, **kwargs)

    @universal_exception
    async def read(self, file, *args, **kwargs):

        return file.read(*args, **kwargs)

    @universal_exception
    async def close(self, file):

        return file.close()

    @universal_exception
    async def rename(self, source, destination):

        return source.rename(destination)


class AsyncPathIO(AbstractPathIO):
    """
    Non-blocking path io. Based on
    :py:meth:`asyncio.BaseEventLoop.run_in_executor` and
    :py:class:`pathlib.Path` methods.
    """

    @universal_exception
    @with_timeout
    async def exists(self, path):

        return await self.loop.run_in_executor(None, path.exists)

    @universal_exception
    @with_timeout
    async def is_dir(self, path):

        return await self.loop.run_in_executor(None, path.is_dir)

    @universal_exception
    @with_timeout
    async def is_file(self, path):

        return await self.loop.run_in_executor(None, path.is_file)

    @universal_exception
    @with_timeout
    async def mkdir(self, path, *, parents=False):

        f = functools.partial(path.mkdir, parents=parents)
        return await self.loop.run_in_executor(None, f)

    @universal_exception
    @with_timeout
    async def rmdir(self, path):

        return await self.loop.run_in_executor(None, path.rmdir)

    @universal_exception
    @with_timeout
    async def unlink(self, path):

        return await self.loop.run_in_executor(None, path.unlink)

    def list(self, path):

        class Lister(AbstractAsyncLister):

            def worker(self):

                try:

                    return next(self.iter)

                except StopIteration:

                    raise StopAsyncIteration

            @universal_exception
            @with_timeout
            async def __aiter__(self):

                f = lambda: path.glob("*")
                self.iter = await self.loop.run_in_executor(None, f)
                return self

            @universal_exception
            @with_timeout
            async def __anext__(self):

                return await self.loop.run_in_executor(None, self.worker)

        return Lister(timeout=self.timeout, loop=self.loop)

    @universal_exception
    @with_timeout
    async def stat(self, path):

        return await self.loop.run_in_executor(None, path.stat)

    @universal_exception
    @with_timeout
    async def _open(self, path, *args, **kwargs):

        f = functools.partial(path.open, *args, **kwargs)
        return await self.loop.run_in_executor(None, f)

    @universal_exception
    @with_timeout
    async def write(self, file, *args, **kwargs):

        f = functools.partial(file.write, *args, **kwargs)
        return await self.loop.run_in_executor(None, f)

    @universal_exception
    @with_timeout
    async def read(self, file, *args, **kwargs):

        f = functools.partial(file.read, *args, **kwargs)
        return await self.loop.run_in_executor(None, f)

    @universal_exception
    @with_timeout
    async def close(self, file):

        return await self.loop.run_in_executor(None, file.close)

    @universal_exception
    @with_timeout
    async def rename(self, source, destination):

        f = functools.partial(source.rename, destination)
        return await self.loop.run_in_executor(None, f)


class Node:

    def __init__(self, type, name, ctime=None, mtime=None, *, content):

        self.type = type
        self.name = name
        self.ctime = ctime or int(time.time())
        self.mtime = mtime or int(time.time())
        self.content = content

    def __repr__(self):

        return str.format(
            "{}(type={!r}, name={!r}, ctime={!r}, mtime={!r}, content={!r})",
            self.__class__.__name__,
            self.type,
            self.name,
            self.ctime,
            self.mtime,
            self.content,
        )


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

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.fs = [Node("dir", "/", content=[])]

    def __repr__(self):

        return repr(self.fs)

    def get_node(self, path):

        nodes = self.fs
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
    async def mkdir(self, path, *, parents=False):

        if self.get_node(path):

            raise FileExistsError

        elif not parents:

            parent = self.get_node(path.parent)
            if parent is None:

                raise FileNotFoundError

            elif parent.type != "dir":

                raise FileExistsError

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

                    raise FileExistsError

    @universal_exception
    async def rmdir(self, path):

        node = self.get_node(path)
        if node is None:

            raise FileNotFoundError

        elif node.type != "dir":

            raise NotADirectoryError

        elif node.content:

            raise OSError("Directory not empty")

        else:

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

        elif node.type != "file":

            raise IsADirectoryError

        else:

            parent = self.get_node(path.parent)
            for i, node in enumerate(parent.content):

                if node.name == path.name:

                    break

            parent.content.pop(i)

    def list(self, path):

        class Lister(AbstractAsyncLister):

            @universal_exception
            async def __aiter__(cls):

                node = self.get_node(path)
                if node is None or node.type != "dir":

                    cls.iter = iter(())

                else:

                    names = map(operator.attrgetter("name"), node.content)
                    paths = map(lambda name: path / name, names)
                    cls.iter = iter(paths)

                return cls

            @universal_exception
            async def __anext__(cls):

                try:

                    return next(cls.iter)

                except StopIteration:

                    raise StopAsyncIteration

        return Lister(timeout=self.timeout, loop=self.loop)

    @universal_exception
    async def stat(self, path):

        node = self.get_node(path)
        if node is None:

            raise FileNotFoundError

        else:

            if node.type == "file":

                size = len(node.content.getbuffer())

            else:

                size = 0

            return MemoryPathIO.Stats(
                size,
                node.ctime,
                node.mtime,
                1,
                0o100777,
            )

    @universal_exception
    async def _open(self, path, mode="rb", *args, **kwargs):

        if mode == "rb":

            node = self.get_node(path)
            if node is None:

                raise FileNotFoundError

            file_like = node.content
            file_like.seek(0, io.SEEK_SET)

        elif mode in ("wb", "ab"):

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

                else:

                    file_like = node.content
                    file_like.seek(0, io.SEEK_END)

        else:

            raise ValueError(str.format("invalid mode: {}", mode))

        return file_like

    @universal_exception
    async def write(self, file, data):

        file.write(data)
        file.mtime = int(time.time())

    @universal_exception
    async def read(self, file, count=None):

        return file.read(count)

    @universal_exception
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
