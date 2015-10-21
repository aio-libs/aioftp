import logging
import asyncio
import functools
import collections


__all__ = (
    "with_timeout",
    "StreamIO",
    "Throttle",
    "StreamThrottle",
    "ThrottleStreamIO",
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
    :type timeout: :py:class:`int`, :py:class:`float` or :py:class:`None`

    :param read_timeout: socket timeout for read operations, overrides
        `timeout`
    :type read_timeout: :py:class:`int`, :py:class:`float` or :py:class:`None`

    :param write_timeout: socket timeout for write operations, overrides
        `timeout`
    :type write_timeout: :py:class:`int`, :py:class:`float` or :py:class:`None`

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

    :param limit: speed limit in bytes or :py:class:`None` for unlimited
    :type limit: :py:class:`int` or :py:class:`None`

    :param reset_rate: time in seconds for «round» throttle memory (to deal
        with float precision when divide)
    :type reset_rate: :py:class:`int` or :py:class:`float`
    """

    def __init__(self, *, loop=None, limit=None, reset_rate=10):

        self.loop = loop or asyncio.get_event_loop()
        self._limit = limit
        self.reset_rate = reset_rate
        self._start = None
        self._sum = 0

    @asyncio.coroutine
    def wait(self):
        """
        :py:func:`asyncio.coroutine`

        Wait until can do IO
        """
        if self._limit is not None and self._limit > 0 and \
           self._start is not None:

            now = self.loop.time()
            end = self._start + self._sum / self._limit
            yield from asyncio.sleep(max(0, end - now), loop=self.loop)

    def append(self, data, start):
        """
        Count `data` for throttle

        :param data: bytes of data for count
        :type data: :py:class:`bytes`

        :param start: start of read/write time from
            :py:meth:`asyncio.BaseEventLoop.time`
        :type start: :py:class:`float`
        """
        if self._limit is not None and self._limit > 0:

            if self._start is None:

                self._start = start

            if start - self._start > self.reset_rate:

                self._sum -= round((start - self._start) * self._limit)
                self._start = start

            self._sum += len(data)

    @property
    def limit(self):
        """
        Throttle limit
        """
        return self._limit

    @limit.setter
    def limit(self, value):
        """
        Set throttle limit

        :param value: bytes per second
        :type value: :py:class:`int` or :py:class:`None`
        """
        self._limit = value
        self._start = None
        self._sum = 0

    def clone(self):
        """
        Clone throttle without memory
        """
        return Throttle(
            loop=self.loop,
            limit=self._limit,
            reset_rate=self.reset_rate
        )

    def __repr__(self):

        return str.format(
            "{}(loop={!r}, limit={!r}, reset_rate={!r})",
            self.__class__.__name__,
            self.loop,
            self._limit,
            self.reset_rate
        )


class StreamThrottle(collections.namedtuple("StreamThrottle", "read write")):
    """
    Stream throttle with `read` and `write` :py:class:`aioftp.Throttle`

    :param read: stream read throttle
    :type read: :py:class:`aioftp.Throttle`

    :param write: stream write throttle
    :type write: :py:class:`aioftp.Throttle`
    """

    def clone(self):
        """
        Clone throttles without memory
        """
        return StreamThrottle(
            read=self.read.clone(),
            write=self.write.clone()
        )

    @classmethod
    def from_limits(cls, read_speed_limit=None, write_speed_limit=None, *,
                    loop=None):
        """
        Simple wrapper for creation :py:class:`aioftp.StreamThrottle`

        :param read_speed_limit: stream read speed limit in bytes or
            :py:class:`None` for unlimited
        :type read_speed_limit: :py:class:`int` or :py:class:`None`

        :param write_speed_limit: stream write speed limit in bytes or
            :py:class:`None` for unlimited
        :type write_speed_limit: :py:class:`int` or :py:class:`None`

        :param loop: loop to use
        :type loop: :py:class:`asyncio.BaseEventLoop`
        """
        loop = loop or asyncio.get_event_loop()
        return cls(
            read=Throttle(
                loop=loop,
                limit=read_speed_limit
            ),
            write=Throttle(
                loop=loop,
                limit=write_speed_limit
            ),
        )


class ThrottleStreamIO(StreamIO):
    """
    Throttled :py:class:`aioftp.StreamIO`. `ThrottleStreamIO` is subclass of
    :py:class:`aioftp.StreamIO`. `throttles` attribute is dictionary of `name`:
    :py:class:`aioftp.StreamThrottle` pairs

    :param *args: positional arguments for :py:class:`aioftp.StreamIO`
    :param **kwargs: keyword arguments for :py:class:`aioftp.StreamIO`

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

        super().__init__(*args, **kwargs)
        self.throttles = throttles

    @asyncio.coroutine
    def wait(self, name):
        """
        :py:func:`asyncio.coroutine`

        Wait for all throttles

        :param name: name of throttle to acquire ("read" or "write")
        :type name: :py:class:`str`
        """
        waiters = []
        for throttle in self.throttles.values():

            waiters.append(getattr(throttle, name).wait())

        yield from asyncio.wait(waiters, loop=self.loop)

    def append(self, name, data, start):
        """
        Update timeout for all throttles

        :param name: name of throttle to append to ("read" or "write")
        :type name: :py:class:`str`

        :param data: bytes of data for count
        :type data: :py:class:`bytes`

        :param start: start of read/write time from
            :py:meth:`asyncio.BaseEventLoop.time`
        :type start: :py:class:`float`
        """
        for throttle in self.throttles.values():

            getattr(throttle, name).append(data, start)

    @asyncio.coroutine
    def read(self, count=DEFAULT_BLOCK_SIZE):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.read` proxy
        """
        yield from self.wait("read")
        start = self.loop.time()
        data = yield from super().read(count)
        self.append("read", data, start)
        return data

    @asyncio.coroutine
    def readline(self):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.readline` proxy
        """
        yield from self.wait("read")
        start = self.loop.time()
        data = yield from super().readline()
        self.append("read", data, start)
        return data

    @asyncio.coroutine
    def write(self, data):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.write` proxy
        """
        yield from self.wait("write")
        start = self.loop.time()
        yield from super().write(data)
        self.append("write", data, start)
