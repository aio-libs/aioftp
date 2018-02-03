import asyncio
import functools
import pathlib
import logging
import shutil
import socket

import nose

import aioftp


PORT = 8888


@nose.tools.nottest
def aioftp_setup(*, server_args=([], {}), client_args=([], {})):

    def decorator(f):

        @functools.wraps(f)
        def wrapper():
            s_args, s_kwargs = server_args
            c_args, c_kwargs = client_args

            def run_in_loop(s_args, s_kwargs, c_args, c_kwargs):
                logging.basicConfig(
                    level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(message)s",
                    datefmt="[%H:%M:%S]:",
                )
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(None)
                server = aioftp.Server(*s_args, loop=loop, **s_kwargs)
                client = aioftp.Client(*c_args, loop=loop, **c_kwargs)
                try:
                    loop.run_until_complete(f(loop, client, server))
                finally:
                    if hasattr(server, "server"):
                        loop.run_until_complete(server.close())
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
def with_connection(f=None, *, host="127.0.0.1", port=PORT,
                    family=socket.AF_INET):

    def decorator(f):

        @functools.wraps(f)
        async def wrapper(loop, client, server):
            try:
                await server.start(host, port, family=family)
                await client.connect(host, port)
                await f(loop, client, server)
            finally:
                client.close()
                await server.close()

        return wrapper
    if f is None:
        return decorator
    else:
        return decorator(f)


@nose.tools.nottest
def expect_codes_in_exception(*codes):

    def decorator(f):

        @functools.wraps(f)
        async def wrapper(*args):
            try:
                await f(*args)
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
        async def wrapper(*args):
            tmp_dir = pathlib.Path("tests") / name
            tmp_dir.mkdir(parents=True)
            try:
                await f(*args, tmp_dir=tmp_dir)
            finally:
                shutil.rmtree(str(tmp_dir))

        return wrapper
    return decorator
