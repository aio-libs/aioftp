import asyncio
import functools
import collections
import operator


class AbstractPathIO:

    def __init__(self, loop=None):

        self.loop = loop or asyncio.get_event_loop()

    @asyncio.coroutine
    def exists(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def is_dir(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def is_file(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def mkdir(self, path, *, parents=False):

        raise NotImplementedError

    @asyncio.coroutine
    def rmdir(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def unlink(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def list(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def stat(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):

        raise NotImplementedError

    @asyncio.coroutine
    def write(self, file, data):

        raise NotImplementedError

    @asyncio.coroutine
    def read(self, file):

        raise NotImplementedError

    @asyncio.coroutine
    def close(self, file):

        raise NotImplementedError

    @asyncio.coroutine
    def rename(self, source, destination):

        raise NotImplementedError


class PathIO(AbstractPathIO):

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


class MemoryPathIO(AbstractPathIO):

    Node = collections.namedtuple("Node", "type name content")

    def __init__(self, loop=None):

        self.fs = [MemoryPathIO.Node("dir", "/", [])]

    def __repr__(self):

        return repr(self.fs)

    def get_node(self, path):

        nodes = self.fs
        for part in path.parts:

            if isinstance(nodes, list):

                for node in nodes:

                    if node.name == part:

                        nodes = node.content
                        break

                else:

                    return

            else:

                return

        return node

    @asyncio.coroutine
    def exists(self, path):

        print("exists", path, self.get_node(path))
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

            node = MemoryPathIO.Node("dir", part, [])
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

                        node = MemoryPathIO.Node("dir", part, [])
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

            return tuple(map(operator.attrgetter("name"), node.content))

    @asyncio.coroutine
    def stat(self, path):

        raise NotImplementedError

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):

        raise NotImplementedError

    @asyncio.coroutine
    def write(self, file, data):

        raise NotImplementedError

    @asyncio.coroutine
    def read(self, file):

        raise NotImplementedError

    @asyncio.coroutine
    def close(self, file):

        raise NotImplementedError

    @asyncio.coroutine
    def rename(self, source, destination):

        if source == destination:

            return

        snode = self.get_node(source)
        sparent = self.get_node(source.parent)
        dparent = self.get_node(destination.parent)
        if snode is None:

            raise FileNotFoundError

        for i, node in enumerate(dparent.content):

            if node.name == destination.name:

                dparent.content[i] = snode._replace(name=destination.name)
                break

        else:

            dparent.content.append(snode._replace(name=destination.name))

        for i, node in enumerate(sparent.content):

            if node.name == source.name:

                sparent.content.pop(i)


if __name__ == "__main__":

    import pathlib

    @asyncio.coroutine
    def test():

        mp = MemoryPathIO()
        print(mp)

        print((yield from mp.exists(pathlib.Path("/foo"))))
        print((yield from mp.is_dir(pathlib.Path("/foo"))))
        print((yield from mp.is_file(pathlib.Path("/foo"))))

        yield from mp.mkdir(pathlib.Path("/foo/bar/baz"), parents=True)

        print((yield from mp.exists(pathlib.Path("/foo"))))
        print((yield from mp.is_dir(pathlib.Path("/foo"))))
        print((yield from mp.is_file(pathlib.Path("/foo"))))

        print(mp)
        print((yield from mp.list(pathlib.Path("/foo"))))
        print((yield from mp.list(pathlib.Path("foo"))))
        print((yield from mp.list(pathlib.Path("/foo/bar"))))

        yield from mp.rmdir(pathlib.Path("/foo/bar/baz"))
        print(mp)

        yield from mp.rename(pathlib.Path("/foo/bar"), pathlib.Path("/foo/b"))
        print(mp)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
    loop.close()
    print("done")
