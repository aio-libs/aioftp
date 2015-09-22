import logging
import collections
import time
import asyncio


__all__ = ("Throttle", "ThrottleMemory", "end_of_line", "default_block_size")


logger = logging.getLogger("aioftp")
end_of_line = "\r\n"
default_block_size = 8192


def wrap_with_container(o):

    if isinstance(o, str):

        o = (o,)

    return o


class ThrottleMemory:

    def __init__(self):

        self.end = 0

    def append(self, data, throttle):

        count = len(data)
        now = time.perf_counter()
        self.end = max(now, self.end) + count / throttle

    def timeout(self):

        return max(0, self.end - time.perf_counter())


class Throttle:

    def __init__(self, stream, *, loop, throttle=None, memory=None):

        self.stream = stream
        self.loop = loop
        self.throttle = throttle
        self.memory = memory or ThrottleMemory()

    @asyncio.coroutine
    def read(self, count=default_block_size):

        data = yield from self.stream.read(count)
        if self.throttle is not None:

            self.memory.append(data, self.throttle)
            yield from asyncio.sleep(self.memory.timeout(), loop=self.loop)

        return data

    @asyncio.coroutine
    def readline(self):

        data = yield from self.stream.readline()
        if self.throttle is not None:

            self.memory.append(data, self.throttle)
            yield from asyncio.sleep(self.memory.timeout(), loop=self.loop)

        return data

    def write(self, data):

        self.stream.write(data)
        if self.throttle is not None:

            self.memory.append(data, self.throttle)

    @asyncio.coroutine
    def drain(self):

        yield from self.stream.drain()
        if self.throttle is not None:

            yield from asyncio.sleep(self.memory.timeout(), loop=self.loop)

    def __getattr__(self, name):

        return getattr(self.stream, name)
