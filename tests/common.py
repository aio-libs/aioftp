import asyncio
import functools
import sys
import pathlib
import os

import nose

sys.path.insert(0, str(pathlib.Path("..").absolute()))
import aioftp


PORT = 8888


@nose.tools.nottest
def aioftp_setup(*, server_args=([], {}), client_args=([], {})):

    def decorator(f):

        @functools.wraps(f)
        def wrapper():

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(None)

            args, kwargs = server_args
            el = os.environ["AIOFTP_TESTS"]
            factory = getattr(aioftp, el)
            if "path_io_factory" not in kwargs:

                kwargs["path_io_factory"] = factory

            server = aioftp.Server(*args, loop=loop, **kwargs)

            args, kwargs = client_args
            client = aioftp.Client(*args, loop=loop, **kwargs)

            coro = asyncio.coroutine(f)
            try:

                loop.run_until_complete(coro(loop, client, server))

            finally:

                loop.close()

        return wrapper

    return decorator


@nose.tools.nottest
def with_connection(f):

    @functools.wraps(f)
    def wrapper(loop, client, server):

        try:

            yield from server.start(None, PORT)
            yield from client.connect("127.0.0.1", PORT)
            yield from asyncio.coroutine(f)(loop, client, server)

        finally:

            server.close()
            client.close()
            yield from server.wait_closed()

    return wrapper


@nose.tools.nottest
def expect_codes_in_exception(*codes):

    def decorator(f):

        @functools.wraps(f)
        def wrapper(*args):

            try:

                yield from f(*args)

            except aioftp.StatusCodeError as exc:

                nose.tools.eq_(exc.received_codes, codes)

            else:

                raise Exception("There was no exception")

        return wrapper

    return decorator


@nose.tools.nottest
def with_tmp_dir(name):

    def decorator(f):

        @functools.wraps(f)
        def wrapper(*args):

            tmp_dir = pathlib.Path("tests") / name
            tmp_dir.mkdir(parents=True)
            try:

                yield from f(*args, tmp_dir=tmp_dir)

            finally:

                tmp_dir.rmdir()

        return wrapper

    return decorator
