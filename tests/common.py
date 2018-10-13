import asyncio
import functools
import logging
import pathlib
import shutil
import socket
import ssl

import nose
import trustme

import aioftp


ca = trustme.CA()
server_cert = ca.issue_server_cert("127.0.0.1", "::1")

ssl_server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
server_cert.configure_cert(ssl_server)

ssl_client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ca.configure_trust(ssl_client)

PORT = 8888


@nose.tools.nottest
def aioftp_setup(*, server_args=([], {}), client_args=([], {})):

    def decorator(f):

        @functools.wraps(f)
        def wrapper():
            s_args, s_kwargs = server_args
            c_args, c_kwargs = client_args

            def run_in_loop(s_args, s_kwargs, c_args, c_kwargs, s_ssl=None, c_ssl=None):
                logging.basicConfig(
                    level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(message)s",
                    datefmt="[%H:%M:%S]:",
                )
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(None)
                server = aioftp.Server(*s_args, loop=loop, ssl=s_ssl, **s_kwargs)
                client = aioftp.Client(*c_args, loop=loop, ssl=c_ssl, **c_kwargs)
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
                    run_in_loop(s_args, s_kwargs, c_args, c_kwargs, ssl_server, ssl_client)
            else:
                run_in_loop(s_args, s_kwargs, c_args, c_kwargs)
                run_in_loop(s_args, s_kwargs, c_args, c_kwargs, ssl_server, ssl_client)

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
