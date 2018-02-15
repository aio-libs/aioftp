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
async def test_idle_timeout(loop, client, server):

    await asyncio.sleep(2, loop=loop)
    await client.login()


class SlowMemoryPathIO(aioftp.MemoryPathIO):

    @aioftp.pathio.universal_exception
    @aioftp.with_timeout
    async def mkdir(self, path, parents=False, exist_ok=False):

        await asyncio.sleep(10, loop=self.loop)

    @aioftp.pathio.universal_exception
    @aioftp.with_timeout
    async def _open(self, path, mode):

        await asyncio.sleep(10, loop=self.loop)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {
            "path_timeout": 1,
            "path_io_factory": SlowMemoryPathIO,
        }))
@expect_codes_in_exception("451")
@with_connection
async def test_server_path_timeout(loop, client, server):

    await client.login()
    await client.make_directory("foo")


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
async def test_client_path_timeout(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    with f.open("wb") as fout:

        fout.write(b"-" * 1024)

    await client.login()
    try:

        await client.download("foo.txt", "/foo.txt", write_into=True)

    except aioftp.PathIOError as e:

        _, value, _ = e.reason
        raise value

    finally:

        f.unlink()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {}))
@with_connection
@expect_codes_in_exception("503")
@with_tmp_dir("foo")
async def test_wait_pasv_timeout_fail_short(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    await client.login()
    await client.command("STOR " + f.name)
    await asyncio.sleep(0.5, loop=loop)
    reader, writer = await client.get_passive_connection("I")

    with contextlib.closing(writer) as writer:

        writer.write(b)
        await writer.drain()

    await client.command(None, "2xx", "1xx")
    await client.quit()

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
async def test_wait_pasv_timeout_fail_long(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    await client.login()
    await client.command("STOR " + f.name)
    await asyncio.sleep(2, loop=loop)
    reader, writer = await client.get_passive_connection("I")

    with contextlib.closing(writer) as writer:

        writer.write(b)
        await writer.drain()

    await client.command(None, "2xx", "1xx")
    await client.quit()

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
async def test_wait_pasv_timeout_ok(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    await client.login()
    await client.command("TYPE I", "200")
    code, info = await client.command("PASV", "227")
    ip, port = client.parse_pasv_response(info[-1])

    await client.command("STOR " + f.name)
    await asyncio.sleep(0.5, loop=loop)
    reader, writer = await aioftp.client.open_connection(
        ip,
        port,
        loop,
        client.create_connection,
    )

    with contextlib.closing(writer) as writer:

        writer.write(b)
        await writer.drain()

    await client.command(None, "2xx", "1xx")
    await client.quit()

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
async def test_wait_pasv_timeout_ok_but_too_long(loop, client, server, *,
                                                 tmp_dir):

    f = tmp_dir / "foo.txt"
    b = b"foobar"

    await client.login()
    await client.command("TYPE I", "200")
    code, info = await client.command("PASV", "227")
    ip, port = client.parse_pasv_response(info[-1])

    await client.command("STOR " + f.name)
    await asyncio.sleep(2, loop=loop)

    reader, writer = await aioftp.client.open_connection(
        ip,
        port,
        loop,
        client.create_connection,
    )

    with contextlib.closing(writer) as writer:

        writer.write(b)
        await writer.drain()

    await client.command(None, "2xx", "1xx")
    await client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


class SlowServer(aioftp.Server):

    async def dispatcher(self, reader, writer):

        await asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(asyncio.TimeoutError)
def test_client_socket_timeout():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)
    server = SlowServer(loop=loop)
    client = aioftp.Client(loop=loop, socket_timeout=1)

    async def coro():
        try:
            await server.start(None, 8888)
            await client.connect("127.0.0.1", 8888)
            await asyncio.sleep(10, loop=loop)
        finally:
            await server.close()

    loop.run_until_complete(coro())


class SlowUserManager(MemoryUserManager):

    @aioftp.with_timeout
    async def get_user(self, login):

        await asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(ConnectionResetError)
def test_user_manager_timeout():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)
    server = aioftp.Server(SlowUserManager(None, timeout=1, loop=loop),
                           loop=loop)
    client = aioftp.Client(loop=loop)

    async def coro():
        try:
            await server.start(None, 8888)
            await client.connect("127.0.0.1", 8888)
            await client.login()
        finally:
            await server.close()

    loop.run_until_complete(coro())


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_server_path_timeout()
    # test_wait_pasv_timeout_ok_but_too_long()
    print("done")
