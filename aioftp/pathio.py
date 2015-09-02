import asyncio
import functools
import collections
import operator
import io
import time


__all__ = (
    "AbstractPathIO",
    "PathIO",
    "AsyncPathIO",
    "MemoryPathIO",
)


class AbstractPathIO:
    """
    Abstract class for path io operations.

    :param loop: loop to use
    :type loop: :py:class:`asyncio.BaseEventLoop`
    """

    def __init__(self, loop=None):

        self.loop = loop or asyncio.get_event_loop()

    @asyncio.coroutine
    def exists(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path exists

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def is_dir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is directory

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def is_file(self, path):
        """
        :py:func:`asyncio.coroutine`

        Check if path is file

        :param path: path to check
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`bool`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def mkdir(self, path, *, parents=False):
        """
        :py:func:`asyncio.coroutine`

        Make directory

        :param path: path to create
        :type path: :py:class:`pathlib.Path`

        :param parents: create parents is does not exists
        :type parents: :py:class:`bool`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def rmdir(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove directory

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def unlink(self, path):
        """
        :py:func:`asyncio.coroutine`

        Remove file

        :param path: path to remove
        :type path: :py:class:`pathlib.Path`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def list(self, path):
        """
        :py:func:`asyncio.coroutine`

        List path content. If path is file, then return empty sequence

        :param path: path to list
        :type path: :py:class:`pathlib.Path`

        :rtype: :py:class:`collections.Iterable` of :py:class:`pathlib.Path`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def stat(self, path):
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

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):
        """
        :py:func:`asyncio.coroutine`

        Open file. You should implement "mode" argument, which can be:
        "rb", "wb", "ab" (read, write, append. all binary). Return type depends
        on implementation, anyway the only place you need this file-object
        is in your implementation of read, write and close

        :param path: path to create
        :type path: :py:class:`pathlib.Path`

        :return: file-object
        """
        raise NotImplementedError

    @asyncio.coroutine
    def write(self, file, data):
        """
        :py:func:`asyncio.coroutine`

        Write some data to file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :param data: data to write
        :type data: :py:class:`bytes`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def read(self, file):
        """
        :py:func:`asyncio.coroutine`

        Read some data from file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`

        :rtype: :py:class:`bytes`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def close(self, file):
        """
        :py:func:`asyncio.coroutine`

        Close file

        :param file: file-object from :py:class:`aioftp.AbstractPathIO.open`
        """
        raise NotImplementedError

    @asyncio.coroutine
    def rename(self, source, destination):
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

    @asyncio.coroutine
    def exists(self, path):

        return path.exists()

    @asyncio.coroutine
    def is_dir(self, path):

        return path.is_dir()

    @asyncio.coroutine
    def is_file(self, path):

        return path.is_file()

    @asyncio.coroutine
    def mkdir(self, path, *, parents=False):

        return path.mkdir(parents=parents)

    @asyncio.coroutine
    def rmdir(self, path):

        return path.rmdir()

    @asyncio.coroutine
    def unlink(self, path):

        return path.unlink()

    @asyncio.coroutine
    def list(self, path):

        return tuple(path.glob("*"))

    @asyncio.coroutine
    def stat(self, path):

        return path.stat()

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):

        return path.open(*args, **kwargs)

    @asyncio.coroutine
    def write(self, file, data):

        return file.write(data)

    @asyncio.coroutine
    def read(self, file, *args, **kwargs):

        return file.read(*args, **kwargs)

    @asyncio.coroutine
    def close(self, file):

        return file.close()

    @asyncio.coroutine
    def rename(self, source, destination):

        return source.rename(destination)


class AsyncPathIO(AbstractPathIO):
    """
    Non-blocking path io. Based on
    :py:meth:`asyncio.BaseEventLoop.run_in_executor` and
    :py:class:`pathlib.Path` methods.
    """

    @asyncio.coroutine
    def exists(self, path):

        return (yield from self.loop.run_in_executor(None, path.exists))

    @asyncio.coroutine
    def is_dir(self, path):

        return (yield from self.loop.run_in_executor(None, path.is_dir))

    @asyncio.coroutine
    def is_file(self, path):

        return (yield from self.loop.run_in_executor(None, path.is_file))

    @asyncio.coroutine
    def mkdir(self, path, *, parents=False):

        f = functools.partial(path.mkdir, parents=parents)
        return (yield from self.loop.run_in_executor(None, f))

    @asyncio.coroutine
    def rmdir(self, path):

        return (yield from self.loop.run_in_executor(None, path.rmdir))

    @asyncio.coroutine
    def unlink(self, path):

        return (yield from self.loop.run_in_executor(None, path.unlink))

    @asyncio.coroutine
    def list(self, path):

        def worker(pattern):

            return tuple(path.glob(pattern))

        return (yield from self.loop.run_in_executor(None, worker, "*"))

    @asyncio.coroutine
    def stat(self, path):

        return (yield from self.loop.run_in_executor(None, path.stat))

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):

        f = functools.partial(path.open, *args, **kwargs)
        return (yield from self.loop.run_in_executor(None, f))

    @asyncio.coroutine
    def write(self, file, data):

        return (yield from self.loop.run_in_executor(None, file.write, data))

    @asyncio.coroutine
    def read(self, file, *args, **kwargs):

        f = functools.partial(file.read, *args, **kwargs)
        return (yield from self.loop.run_in_executor(None, f))

    @asyncio.coroutine
    def close(self, file):

        return (yield from self.loop.run_in_executor(None, file.close))

    @asyncio.coroutine
    def rename(self, source, destination):

        f = functools.partial(source.rename, destination)
        return (yield from self.loop.run_in_executor(None, f))


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

    def __init__(self, loop=None):

        super().__init__(loop)
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

    @asyncio.coroutine
    def exists(self, path):

        return self.get_node(path) is not None

    @asyncio.coroutine
    def is_dir(self, path):

        node = self.get_node(path)
        return not (node is None or node.type != "dir")

    @asyncio.coroutine
    def is_file(self, path):

        node = self.get_node(path)
        return not (node is None or node.type != "file")

    @asyncio.coroutine
    def mkdir(self, path, *, parents=False):

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

    @asyncio.coroutine
    def rmdir(self, path):

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

    @asyncio.coroutine
    def unlink(self, path):

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

    @asyncio.coroutine
    def list(self, path):

        node = self.get_node(path)
        if node is None or node.type != "dir":

            return ()

        else:

            names = map(operator.attrgetter("name"), node.content)
            paths = map(lambda name: path / name, names)
            return tuple(paths)

    @asyncio.coroutine
    def stat(self, path):

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

    @asyncio.coroutine
    def open(self, path, mode="rb", *args, **kwargs):

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

    @asyncio.coroutine
    def write(self, file, data):

        file.write(data)
        file.mtime = int(time.time())

    @asyncio.coroutine
    def read(self, file, count=None):

        return file.read(count)

    @asyncio.coroutine
    def close(self, file):

        pass

    @asyncio.coroutine
    def rename(self, source, destination):

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
