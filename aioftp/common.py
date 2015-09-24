import logging
import asyncio
import functools


__all__ = (
    "ReadThrottle",
    "WriteThrottle",
    "ThrottleMemory",
    "with_timeout",
    "end_of_line",
    "default_block_size",
    "logger",
)


logger = logging.getLogger("aioftp")
end_of_line = "\r\n"
default_block_size = 8192


def wrap_with_container(o):

    if isinstance(o, str):

        o = (o,)

    return o


def with_timeout(f):

    @functools.wraps(f)
    def wrapper(cls, *args, **kwargs):

        coro = f(cls, *args, **kwargs)
        return asyncio.wait_for(coro, cls.timeout, loop=cls.loop)

    return wrapper


class ThrottleMemory:

    def __init__(self, *, loop):

        self.end = 0
        self.loop = loop

    def append(self, data, throttle):

        count = len(data)
        now = self.loop.time()
        self.end = max(now, self.end) + count / throttle

    def timeout(self):

        return max(0, self.end - self.loop.time())


class AbstractThrottle:

    def __init__(self, stream, *, loop, throttle=None, memory=None):

        self.stream = stream
        self.loop = loop
        self.throttle = throttle
        self.memory = memory or ThrottleMemory(loop=loop)
        self._lock = asyncio.Lock(loop=loop)

    def __getattr__(self, name):

        return getattr(self.stream, name)


class ReadThrottle(AbstractThrottle):

    @asyncio.coroutine
    def read(self, count=default_block_size):

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
