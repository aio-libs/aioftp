import asyncio
import functools
import sys
import pathlib
import os
import aioftp

import nose


PORT = 8888


@nose.tools.nottest
def aioftp_setup(*, server_args=([], {}), client_args=([], {})):

    def decorator(f):

        @functools.wraps(f)
        def wrapper():

            s_args, s_kwargs = server_args
            c_args, c_kwargs = client_args

            def run_in_loop(s_args, s_kwargs, c_args, c_kwargs):

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(None)

                server = aioftp.Server(*s_args, loop=loop, **s_kwargs)
                client = aioftp.Client(*c_args, loop=loop, **c_kwargs)

                coro = asyncio.coroutine(f)
                try:

                    loop.run_until_complete(coro(loop, client, server))

                finally:

                    if hasattr(server, "server"):

                        server.close()
                        loop.run_until_complete(server.wait_closed())

                    if hasattr(client, "writer"):

                        client.close()

                    loop.close()

            if "path_io_factory" not in s_kwargs:
                for factory in (aioftp.PathIO, aioftp.AsyncPathIO):
                    s_kwargs["path_io_factory"] = factory
                    run_in_loop(s_args, s_kwargs, c_args, c_kwargs)
            else:
                run_in_loop(s_args, s_kwargs, c_args, c_kwargs)

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

            client.close()
            server.close()
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
