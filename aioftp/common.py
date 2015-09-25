import logging
import asyncio
import functools
import collections


__all__ = (
    "StreamIO",
    "ThrottleStreamIO",
    "StreamThrottle",
    "Throttle",
    "with_timeout",
    "END_OF_LINE",
    "DEFAULT_BLOCK_SIZE",
    "wrap_with_container",
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
    """
    Method decorator, wraps method with :py:func:`asyncio.wait_for`. `timeout`
        argument takes from `name` decorator argument or "timeout".

    :param name: name of timeout attribute
    :type name: :py:class:`str`

    :raises asyncio.TimeoutError: if coroutine does not finished in timeout

    Wait for `self.timeout`
    ::

        def __init__(self, ...):

            self.timeout = 1

        @with_timeout
        @asyncio.coroutine
        def foo(self, ...):

            pass

    Wait for custom timeout
    ::

        def __init__(self, ...):

            self.foo_timeout = 1

        @with_timeout("foo_timeout")
        @asyncio.coroutine
        def foo(self, ...):

            pass

    """

    if isinstance(name, str):

        return _with_timeout(name)

    else:

        return _with_timeout("timeout")(name)


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


class Throttle:
    """
    Throttle for streams.

    :param loop: loop to use
    :type loop: :py:class:`asyncio.BaseEventLoop`

    :param limit: speed limit in bytes or `None` for unlimited
    :type limit: :py:class:`int` or `None`
    """

    def __init__(self, *, loop=None, limit=None):

        self.loop = loop or asyncio.get_event_loop()
        self._limit = limit
        self._lock = asyncio.Lock(loop=self.loop)
        self.end = 0

    @asyncio.coroutine
    def acquire(self):
        """
        :py:func:`asyncio.coroutine`

        Acquire internal lock
        """
        if self.limit is not None and self.limit > 0:

            yield from self._lock

    def append(self, data):
        """
        Count `data` for throttle
        """
        if self.limit is not None and self.limit > 0:

            self.end = max(self.loop.time(), self.end) + len(data) / self.limit

    def release_later(self):
        """
        Release internal lock after timeout
        """
        if self._lock.locked():

            self.loop.call_later(self.timeout, self._lock.release)

    @property
    def timeout(self):

        return max(0, self.end - self.loop.time())

    @property
    def limit(self):

        return self._limit

    @limit.setter
    def limit(self, value):

        self._limit = value
        self.end = 0


StreamThrottle = collections.namedtuple("StreamThrottle", "read write")


class ThrottleStreamIO(StreamIO, dict):
    """
    Throttled :py:class:`aioftp.StreamIO`. `ThrottleStreamIO` is mix of
    :py:class:`aioftp.StreamIO` and :py:class:`dict`. Dictionary values are
    :py:class:`aioftp.StreamThrottle` objects: `read` and `write`
    :py:class:`aioftp.Throttle`

    :param *args: positional arguments for StreamIO
    :param **kwargs: keyword arguments for StreamIO

    :param throttles: dictionary of throttles
    :type throttles: :py:class:`dict` with :py:class:`aioftp.Throttle` values

    ::

        self.stream = ThrottleStreamIO(
            reader,
            writer,
            throttles={
                "main": StreamThrottle(
                    read=Throttle(...),
                    write=Throttle(...)
                )
            },
            timeout=timeout,
            loop=loop
        )
    """

    def __init__(self, *args, throttles={}, **kwargs):

        StreamIO.__init__(self, *args, **kwargs)
        dict.__init__(self, throttles)

    @asyncio.coroutine
    def acquire(self, name):
        """
        Acquire all throttles
        """
        for throttle in self.values():

            yield from getattr(throttle, name).acquire()

    def append(self, name, data):
        """
        Update timeout for all throttles
        """
        for throttle in self.values():

            getattr(throttle, name).append(data)

    def release_later(self, name):
        """
        Trigger :py:meth:`aioftp.Throttle.release_later` for all throttles
        """
        for throttle in self.values():

            getattr(throttle, name).release_later()

    @asyncio.coroutine
    def read(self, count=DEFAULT_BLOCK_SIZE):
        """
        :py:meth:`aioftp.StreamIO.read` proxy
        """
        yield from self.acquire("read")
        try:

            data = yield from super().read(count)
            self.append("read", data)

        finally:

            self.release_later("read")

        return data

    @asyncio.coroutine
    def readline(self):
        """
        :py:meth:`aioftp.StreamIO.readline` proxy
        """
        yield from self.acquire("read")
        try:

            data = yield from super().readline()
            self.append("read", data)

        finally:

            self.release_later("read")

        return data

    @asyncio.coroutine
    def write(self, data):
        """
        :py:meth:`aioftp.StreamIO.write` proxy
        """
        yield from self.acquire("write")
        try:

            yield from super().write(data)
            self.append("write", data)

        finally:

            self.release_later("write")
