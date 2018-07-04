import asyncio
import functools
import locale
import threading
from contextlib import contextmanager


__all__ = (
    "with_timeout",
    "END_OF_LINE",
    "DEFAULT_BLOCK_SIZE",
    "wrap_with_container",
    "AsyncStreamIterator",
    "AbstractAsyncLister",
    "AsyncListerMixin",
    "async_enterable",
    "DEFAULT_PORT",
    "DEFAULT_USER",
    "DEFAULT_PASSWORD",
    "DEFAULT_ACCOUNT",
    "setlocale",
)


END_OF_LINE = "\r\n"
DEFAULT_BLOCK_SIZE = 8192

DEFAULT_PORT = 21
DEFAULT_USER = "anonymous"
DEFAULT_PASSWORD = "anon@"
DEFAULT_ACCOUNT = ""


def with_timeout(f=None, *, name="timeout"):
    """
    Method decorator, wraps method with :py:func:`asyncio.wait_for`. `timeout`
    argument takes from `name` decorator argument or "timeout".

    :param name: name of timeout attribute
    :type name: :py:class:`str`

    :raises asyncio.TimeoutError: if coroutine does not finished in timeout

    Wait for `self.timeout`
    ::

        >>> def __init__(self, ...):
        ...     self.timeout = 1
        ...
        ... @with_timeout
        ... async def foo(self, ...):
        ...     pass

    Wait for custom timeout
    ::

        >>> def __init__(self, ...):
        ...     self.foo_timeout = 1
        ...
        ... @with_timeout(name="foo_timeout")
        ... async def foo(self, ...):
        ...     pass

    """
    def decorator(f):

        @functools.wraps(f)
        async def wrapper(cls, *args, **kwargs):
            coro = f(cls, *args, **kwargs)
            timeout = getattr(cls, name)
            return await asyncio.wait_for(coro, timeout, loop=cls.loop)

        return wrapper

    if f:
        return decorator(f)
    else:
        return decorator


class AsyncStreamIterator:

    def __init__(self, read_coro):
        self.read_coro = read_coro

    def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self.read_coro()
        if data:
            return data
        else:
            raise StopAsyncIteration


class AsyncListerMixin:
    """
    Add ability to `async for` context to collect data to list via await.

    ::

        >>> class Context(AsyncListerMixin):
        ...     ...
        >>> results = await Context(...)
    """
    async def _to_list(self):
        items = []
        async for item in self:
            items.append(item)
        return items

    def __await__(self):
        return self._to_list().__await__()


class AbstractAsyncLister(AsyncListerMixin):
    """
    Abstract context with ability to collect all iterables into
    :py:class:`list` via `await` with optional timeout (via
    :py:func:`aioftp.with_timeout`)

    :param timeout: timeout for __anext__ operation
    :type timeout: :py:class:`None`, :py:class:`int` or :py:class:`float`

    :param loop: loop to use for timeouts
    :type loop: :py:class:`asyncio.BaseEventLoop`

    ::

        >>> class Lister(AbstractAsyncLister):
        ...
        ...     @with_timeout
        ...     async def __anext__(self):
        ...         ...

    ::

        >>> async for block in Lister(...):
        ...     ...

    ::

        >>> result = await Lister(...)
        >>> result
        [block, block, block, ...]
    """
    def __init__(self, *, timeout=None, loop=None):
        self.timeout = timeout
        self.loop = loop or asyncio.get_event_loop()

    def __aiter__(self):
        return self

    @with_timeout
    async def __anext__(self):
        raise NotImplementedError


def async_enterable(f):
    """
    Decorator. Bring coroutine result up, so it can be used as async context

    ::

        >>> async def foo():
        ...     ...
        ...     return AsyncContextInstance(...)
        ...
        ... ctx = await foo()
        ... async with ctx as smth:
        ...     # do

    ::

        >>> @async_enterable
        ... async def foo():
        ...     ...
        ...     return AsyncContextInstance(...)
        ...
        ... async with foo() as smth:
        ...     # do
        ...
        ... ctx = await foo()
        ... async with ctx:
        ...     # do

    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):

        class AsyncEnterableInstance:

            async def __aenter__(self):
                self.context = await f(*args, **kwargs)
                return await self.context.__aenter__()

            async def __aexit__(self, *args, **kwargs):
                await self.context.__aexit__(*args, **kwargs)

            def __await__(self):
                return f(*args, **kwargs).__await__()

        return AsyncEnterableInstance()

    return wrapper


def wrap_with_container(o):
    if isinstance(o, str):
        o = (o,)
    return o


LOCALE_LOCK = threading.Lock()


@contextmanager
def setlocale(name):
    """
    Context manager with threading lock for set locale on enter, and set it
    back to original state on exit.

    ::

        >>> with setlocale("C"):
        ...     ...
    """
    with LOCALE_LOCK:
        old_locale = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, old_locale)
