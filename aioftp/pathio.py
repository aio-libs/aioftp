import asyncio


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

        return path.glob("*")

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

        f = functools.partial(mkdir, parents=parents)
        return (yield from self.loop.run_in_executor(None, f))

    @asyncio.coroutine
    def rmdir(self, path):

        return (yield from self.loop.run_in_executor(None, path.rmdir))

    @asyncio.coroutine
    def unlink(self, path):

        return (yield from self.loop.run_in_executor(None, path.unlink))

    @asyncio.coroutine
    def list(self, path):

        return (yield from self.loop.run_in_executor(None, path.glob, "*"))

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
