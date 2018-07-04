import asyncio
import collections
import enum

from . import errors
from .common import (
    with_timeout,
    AsyncStreamIterator,
    DEFAULT_BLOCK_SIZE,
    async_enterable,
)


__all__ = (
    "Throttle",
    "StreamThrottle",
    "StreamIO",
    "ThrottleStreamIO",
    "StreamDirection",
    "DirectedThrottleStreamIO",
)


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

    @with_timeout(name="read_timeout")
    async def readline(self):
        """
        :py:func:`asyncio.coroutine`

        Proxy for :py:meth:`asyncio.StreamReader.readline`.
        """
        return await self.reader.readline()

    @with_timeout(name="read_timeout")
    async def read(self, count=-1):
        """
        :py:func:`asyncio.coroutine`

        Proxy for :py:meth:`asyncio.StreamReader.read`.

        :param count: block size for read operation
        :type count: :py:class:`int`
        """
        return await self.reader.read(count)

    @with_timeout(name="write_timeout")
    async def write(self, data):
        """
        :py:func:`asyncio.coroutine`

        Combination of :py:meth:`asyncio.StreamWriter.write` and
        :py:meth:`asyncio.StreamWriter.drain`.

        :param data: data to write
        :type data: :py:class:`bytes`
        """
        self.writer.write(data)
        await self.writer.drain()

    async def close(self):
        """
        :py:func:`asyncio.coroutine`

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

    async def wait(self):
        """
        :py:func:`asyncio.coroutine`

        Wait until can do IO
        """
        if self._limit is None or self._limit <= 0 or self._start is None:
            return
        now = self.loop.time()
        end = self._start + self._sum / self._limit
        await asyncio.sleep(max(0, end - now), loop=self.loop)

    def append(self, data, start):
        """
        Count `data` for throttle

        :param data: bytes of data for count
        :type data: :py:class:`bytes`

        :param start: start of read/write time from
            :py:meth:`asyncio.BaseEventLoop.time`
        :type start: :py:class:`float`
        """
        if self._limit is None or self._limit <= 0:
            return
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
        return "{}(loop={!r}, limit={!r}, reset_rate={!r})".format(
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

        >>> self.stream = ThrottleStreamIO(
        ...     reader,
        ...     writer,
        ...     throttles={
        ...         "main": StreamThrottle(
        ...             read=Throttle(...),
        ...             write=Throttle(...)
        ...         )
        ...     },
        ...     timeout=timeout,
        ...     loop=loop
        ... )
    """

    def __init__(self, *args, throttles={}, **kwargs):
        super().__init__(*args, **kwargs)
        self.throttles = throttles

    async def wait(self, name):
        """
        :py:func:`asyncio.coroutine`

        Wait for all throttles

        :param name: name of throttle to acquire ("read" or "write")
        :type name: :py:class:`str`
        """
        waiters = []
        for throttle in self.throttles.values():
            curr_throttle = getattr(throttle, name)
            if curr_throttle.limit:
                waiters.append(curr_throttle.wait())
        if waiters:
            await asyncio.wait(waiters, loop=self.loop)

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

    async def read(self, count=-1):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.read` proxy
        """
        await self.wait("read")
        start = self.loop.time()
        data = await super().read(count)
        self.append("read", data, start)
        return data

    async def readline(self):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.readline` proxy
        """
        await self.wait("read")
        start = self.loop.time()
        data = await super().readline()
        self.append("read", data, start)
        return data

    async def write(self, data):
        """
        :py:func:`asyncio.coroutine`

        :py:meth:`aioftp.StreamIO.write` proxy
        """
        await self.wait("write")
        start = self.loop.time()
        await super().write(data)
        self.append("write", data, start)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def iter_by_line(self):
        """
        Read/iterate stream by line.

        :rtype: :py:class:`aioftp.AsyncStreamIterator`

        ::

            >>> async for line in stream.iter_by_line():
            ...     ...
        """
        return AsyncStreamIterator(self.readline)

    def iter_by_block(self, count=DEFAULT_BLOCK_SIZE):
        """
        Read/iterate stream by block.

        :rtype: :py:class:`aioftp.AsyncStreamIterator`

        ::

            >>> async for block in stream.iter_by_block(block_size):
            ...     ...
        """
        return AsyncStreamIterator(lambda: self.read(count))


StreamDirection = enum.Enum("StreamDirection", "incoming outgoing")


class DirectedThrottleStreamIO(ThrottleStreamIO):
    """
    Directed reusable throttled stream.

    This is very high level «one client» stream. «One client» means that stream
    object can have only one connection at any time.

    :param *args: positional arguments for :py:class:`aioftp.ThrottleStreamIO`
    :param **kwargs: keyword arguments for :py:class:`aioftp.ThrottleStreamIO`

    :param start_server_factory: server factory
    :type start_server_factory: :py:func:`callable` with only arguments
        host and port

    :param create_connection_factory: client factory
    :type start_server_factory: :py:func:`callable` with only arguments
        host and port

    :param available_ports: list of available ports for server to bind to
    :type available_ports: :py:class:`list` or :py:class:`None`

    :param wait_connection_timeout: maximum time between `connect` call and
        actual connection establishment
    :type wait_connection_timeout: :py:class:`float` or :py:class:`None`
    """
    def __init__(self, *args, start_server_factory,
                 create_connection_factory, available_ports=None,
                 wait_connection_timeout=None, **kwargs):
        super().__init__(None, None, *args, **kwargs)
        self.host = None
        self.port = None
        self.start_server_factory = start_server_factory
        self.create_connection_factory = create_connection_factory
        self.available_ports = available_ports
        self.wait_connection_timeout = wait_connection_timeout
        self._server = None
        self._direction = None

    async def set_direction(self, direction):
        if self._direction == direction:
            return
        if direction == StreamDirection.outgoing:
            await self._stop_incoming_server()
        elif direction == StreamDirection.incoming:
            await self._start_incoming_server()
        else:
            raise ValueError("Unknown direction type {!r}".format(direction))
        self._direction = direction

    @async_enterable
    async def connect(self, host=None, port=None, *, direction=None):
        """
        :py:func:`asyncio.coroutine`

        Connect to host:port or wait for incoming connection. Can be used
        as context manager («async enterable»).

        :param host: host to connect to
        :type host: :py:class:`str` or :py:class:`None`

        :param port: port to connect to
        :type port: :py:class:`int` or :py:class:`None`

        :param direction: connection direction
        :type direction: :py:class:`aioftp.StreamDirection` or :py:class:`None`

        ::
            >>> # this will auto-disconnect on context finalization
            >>> async with stream.connect(...):
            ...     await stream.readline()

            >>> # this requires manual `disconnect` call
            >>> await stream.connect(...)
            ... await stream.readline()
            ... await stream disconnect()
        """
        await self.disconnect()
        if direction is not None:
            await self.set_direction(direction)
        if self._direction == StreamDirection.outgoing:
            if host is None or port is None:
                raise ValueError("Outgoing connection need host and port, "
                                 "but got {!r} {!r}".format(host, port))
            self.host = host
            self.port = port
            self.reader, self.writer = await asyncio.wait_for(
                self.create_connection_factory(self.host, self.port),
                self.wait_connection_timeout,
                loop=self._loop,
            )
        elif self._direction == StreamDirection.incoming:
            if host is not None or port is not None:
                raise ValueError("Incoming connection need no host and port, "
                                 "but got {!r} {!r}".format(host, port))
            self.reader, self.writer = await asyncio.wait_for(
                self._incomming_connection,
                self.wait_connection_timeout,
                loop=self._loop
            )
        else:
            raise ValueError("Unknown direction {!r}".format(self._direction))

    async def disconnect(self):
        """
        :py:func:`asyncio.coroutine`

        Close connection/stop waiting for incomming.
        """
        if self.writer is not None:
            await self.close()
        self.reader = self.writer = None
        self._incomming_connection.cancel()
        self._incomming_connection = asyncio.Future(loop=self._loop)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc_info):
        await self.disconnect()

    async def stop(self):
        """
        :py:func:`asyncio.coroutine`

        Disconnect and stop incoming server. You should not call any method
        after calling this.
        """
        await self.disconnect()
        await self._stop_incoming_server()

    async def _incoming_handler(self, reader, writer):
        if self.reader and self.writer:
            writer.close()
        else:
            self._incomming_connection.set_result((reader, writer))

    async def _start_incoming_server(self):
        if self._server is not None:
            return
        if self.available_ports is not None:
            if not self.available_ports:
                raise errors.NoAvailablePort
            port = self.available_ports.pop()
        else:
            port = None
        self._server = await self._start_server_factory(self._incoming_handler,
                                                        port=port)
        self.host, self.port, *_ = self._server.sockets[0].getsockname()

    async def _stop_incoming_server(self):
        if self._server is None:
            return
        self.available_ports.add(self.port)
        try:
            self._server.close()
            await self._server.wait_closed()
        finally:
            self.host = self.port = self._server = None
