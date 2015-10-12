import nose
import contextlib

import aioftp.client
import aioftp
from common import *  # noqa
from aioftp.server import MemoryUserManager


@nose.tools.raises(ConnectionResetError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {"idle_timeout": 1}))
@with_connection
def test_idle_timeout(loop, client, server):

    yield from asyncio.sleep(2, loop=loop)
    yield from client.login()


class SlowMemoryPathIO(aioftp.MemoryPathIO):

    @aioftp.with_timeout
    @asyncio.coroutine
    def mkdir(self, path, parents=False):

        yield from asyncio.sleep(10, loop=self.loop)

    @aioftp.with_timeout
    @asyncio.coroutine
    def open(self, path, mode):

        yield from asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(ConnectionResetError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {
            "path_timeout": 1,
            "path_io_factory": SlowMemoryPathIO,
        }))
@with_connection
def test_server_path_timeout(loop, client, server):

    yield from client.login()
    yield from client.make_directory("foo")


@nose.tools.raises(asyncio.TimeoutError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}),
    client_args=(
        [],
        {
            "path_timeout": 1,
            "path_io_factory": SlowMemoryPathIO,
        }))
@with_connection
@with_tmp_dir("foo")
def test_client_path_timeout(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    with f.open("wb") as fout:

        fout.write(b"-" * 1024)

    yield from client.login()
    try:

        yield from client.download("foo.txt", "/foo.txt", write_into=True)

    finally:

        f.unlink()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}))
@with_connection
@expect_codes_in_exception("503")
@with_tmp_dir("foo")
def test_wait_pasv_timeout_fail_short(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    yield from client.login()
    yield from client.command("STOR " + f.name)
    yield from asyncio.sleep(0.5, loop=loop)
    reader, writer = yield from client.get_passive_connection("I")

    with contextlib.closing(writer) as writer:

        writer.write(b)
        yield from writer.drain()

    yield from client.command(None, "2xx", "1xx")
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}))
@with_connection
@expect_codes_in_exception("503")
@with_tmp_dir("foo")
def test_wait_pasv_timeout_fail_long(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    yield from client.login()
    yield from client.command("STOR " + f.name)
    yield from asyncio.sleep(2, loop=loop)
    reader, writer = yield from client.get_passive_connection("I")

    with contextlib.closing(writer) as writer:

        writer.write(b)
        yield from writer.drain()

    yield from client.command(None, "2xx", "1xx")
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}))
@with_connection
@with_tmp_dir("foo")
def test_wait_pasv_timeout_ok(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    yield from client.login()
    yield from client.command("TYPE I", "200")
    code, info = yield from client.command("PASV", "227")
    ip, port = client.parse_address_response(info[-1])

    yield from client.command("STOR " + f.name)
    yield from asyncio.sleep(0.5, loop=loop)
    reader, writer = yield from aioftp.client.open_connection(
        ip,
        port,
        loop,
        client.create_connection,
    )

    with contextlib.closing(writer) as writer:

        writer.write(b)
        yield from writer.drain()

    yield from client.command(None, "2xx", "1xx")
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}))
@with_connection
@expect_codes_in_exception("425")
@with_tmp_dir("foo")
def test_wait_pasv_timeout_ok_but_too_long(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    yield from client.login()
    yield from client.command("TYPE I", "200")
    code, info = yield from client.command("PASV", "227")
    ip, port = client.parse_address_response(info[-1])

    yield from client.command("STOR " + f.name)
    yield from asyncio.sleep(2, loop=loop)

    reader, writer = yield from aioftp.client.open_connection(
        ip,
        port,
        loop,
        client.create_connection,
    )

    with contextlib.closing(writer) as writer:

        writer.write(b)
        yield from writer.drain()

    yield from client.command(None, "2xx", "1xx")
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


class SlowServer(aioftp.Server):

    @asyncio.coroutine
    def dispatcher(self, reader, writer):

        yield from asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(asyncio.TimeoutError)
def test_client_socket_timeout():

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    server = SlowServer(loop=loop)
    client = aioftp.Client(loop=loop, socket_timeout=1)

    @asyncio.coroutine
    def coro():

        try:

            yield from server.start(None, 8888)
            yield from client.connect("127.0.0.1", 8888)
            yield from asyncio.sleep(10, loop=loop)

        finally:

            server.close()
            yield from server.wait_closed()

    loop.run_until_complete(coro())


class SlowUserManager(MemoryUserManager):

    @aioftp.with_timeout
    @asyncio.coroutine
    def get_user(self, login):

        yield from asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(ConnectionResetError)
def test_user_manager_timeout():

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    server = aioftp.Server(
        SlowUserManager(None, timeout=1, loop=loop),
        loop=loop)
    client = aioftp.Client(loop=loop)

    @asyncio.coroutine
    def coro():

        try:

            yield from server.start(None, 8888)
            yield from client.connect("127.0.0.1", 8888)
            yield from client.login()

        finally:

            server.close()
            yield from server.wait_closed()

    loop.run_until_complete(coro())


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_wait_pasv_timeout_ok()
    test_wait_pasv_timeout_ok_but_too_long()
    print("done")
