import logging
import asyncio
import functools


__all__ = (
    "StreamIO",
    "ReadThrottle",
    "WriteThrottle",
    "ThrottleMemory",
    "with_timeout",
    "END_OF_LINE",
    "DEFAULT_BLOCK_SIZE",
    "logger",
    "wrap_with_container"
)


logger = logging.getLogger("aioftp")
END_OF_LINE = "\r\n"
DEFAULT_BLOCK_SIZE = 8192


def wrap_with_container(o):

    if isinstance(o, str):

        o = (o,)

    return o


def _with_timeout(name):

    def decorator(f):

        @functools.wraps(f)
        def wrapper(cls, *args, **kwargs):

            coro = f(cls, *args, **kwargs)
            timeout = getattr(cls, name)
            return asyncio.wait_for(coro, timeout, loop=cls.loop)

        return wrapper

    return decorator


def with_timeout(name):

    if isinstance(name, str):

        return _with_timeout(name)

    else:

        return _with_timeout("timeout")(name)


class ThrottleMemory:

    def __init__(self, *, loop=None):

        self.end = 0
        self.loop = loop or asyncio.get_event_loop()

    def append(self, data, throttle):

        count = len(data)
        now = self.loop.time()
        self.end = max(now, self.end) + count / throttle

    def timeout(self):

        return max(0, self.end - self.loop.time())


class AbstractThrottle:

    def __init__(self, stream, *, loop=None, throttle=None, memory=None):

        self.stream = stream
        self.loop = loop or asyncio.get_event_loop()
        self.throttle = throttle
        self.memory = memory or ThrottleMemory(loop=loop)
        self._lock = asyncio.Lock(loop=loop)

    def __getattr__(self, name):

        return getattr(self.stream, name)


class ReadThrottle(AbstractThrottle):

    @asyncio.coroutine
    def read(self, count=DEFAULT_BLOCK_SIZE):

        if self.throttle is not None:

            yield from self._lock

        try:

            data = yield from self.stream.read(count)

        finally:

            if self.throttle is not None:

                self.memory.append(data, self.throttle)
                self.loop.call_later(self.memory.timeout(), self._lock.release)

        return data

    @asyncio.coroutine
    def readline(self):

        if self.throttle is not None:

            yield from self._lock

        try:

            data = yield from self.stream.readline()

        finally:

            if self.throttle is not None:

                self.memory.append(data, self.throttle)
                self.loop.call_later(self.memory.timeout(), self._lock.release)

        return data


class WriteThrottle(AbstractThrottle):

    def write(self, data):

        self.stream.write(data)
        if self.throttle is not None:

            self.memory.append(data, self.throttle)

    @asyncio.coroutine
    def drain(self):

        if self.throttle is not None:

            yield from self._lock

        try:

            yield from self.stream.drain()

        finally:

            if self.throttle is not None:

                self.loop.call_later(self.memory.timeout(), self._lock.release)


class StreamIO:
    """
    Stream input/output wrapper with timeout.

    :param reader: stream reader
    :type reader: :py:class:`asyncio.StreamReader`

    :param writer: stream writer
    :type writer: :py:class:`asyncio.StreamWriter`

    :param timeout: socket timeout for read/write operations
    :type timeout: :py:class:`int`, :py:class:`float` or `None`

    :param read_timeout: socket timeout for read operations, overrides
        `timeout`
    :type read_timeout: :py:class:`int`, :py:class:`float` or `None`

    :param write_timeout: socket timeout for write operations, overrides
        `timeout`
    :type write_timeout: :py:class:`int`, :py:class:`float` or `None`

    :param loop: loop to use for creating connection and binding with streams
    :type loop: :py:class:`asyncio.BaseEventLoop`
    """

    def __init__(self, reader, writer, *, timeout=None, read_timeout=None,
                 write_timeout=None, loop=None):

        self.reader = reader
        self.writer = writer
        self.read_timeout = read_timeout or timeout
        self.write_timeout = write_timeout or timeout
        self.loop = loop or asyncio.get_event_loop()

    @with_timeout("read_timeout")
    @asyncio.coroutine
    def readline(self):
        """
        :py:func:`asyncio.coroutine`

        Proxy for :py:meth:`asyncio.StreamReader.readline`.
        """
        return (yield from self.reader.readline())

    @with_timeout("read_timeout")
    @asyncio.coroutine
    def read(self, count=DEFAULT_BLOCK_SIZE):
        """
        :py:func:`asyncio.coroutine`

        Proxy for :py:meth:`asyncio.StreamReader.read`.

        :param count: block size for read operation
        :type count: :py:class:`int`
        """
        return (yield from self.reader.read(count))

    @with_timeout("write_timeout")
    @asyncio.coroutine
    def write(self, data):
        """
        :py:func:`asyncio.coroutine`

        Combination of :py:meth:`asyncio.StreamWriter.write` and
        :py:meth:`asyncio.StreamWriter.drain`.

        :param data: data to write
        :type data: :py:class:`bytes`
        """
        self.writer.write(data)
        yield from self.writer.drain()

    def close(self):
        """
        Close connection.
        """
        self.writer.close()
