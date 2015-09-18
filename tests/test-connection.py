from common import *


@nose.tools.raises(OSError)
@aioftp_setup()
def test_client_without_server(loop, client, server):

    yield from client.connect("127.0.0.1", PORT)


@aioftp_setup()
@with_connection
def test_connection(loop, client, server):

    pass


@aioftp_setup()
@with_connection
def test_quit(loop, client, server):

    yield from client.quit()


@aioftp_setup()
@with_connection
def test_dirty_quit(loop, client, server):

    yield from asyncio.sleep(0.5, loop=loop)
    client.close()
    yield from asyncio.sleep(0.5, loop=loop)


@aioftp_setup()
@with_connection
@expect_codes_in_exception("502")
def test_not_implemented(loop, client, server):

    yield from client.command("FOOBAR", "2xx", "1xx")


@aioftp_setup()
@with_connection
@expect_codes_in_exception("502")
def test_type_not_implemented(loop, client, server):

    yield from client.login()
    yield from client.get_passive_connection("A")


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError)
@aioftp_setup()
@with_connection
def test_extra_pasv_connection(loop, client, server):

    yield from client.login()
    r, w = yield from client.get_passive_connection()
    er, ew = yield from client.get_passive_connection()
    while True:

        ew.write(b"-" * 8192)
        yield from asyncio.sleep(0.1, loop=loop)
        yield from ew.drain()

    yield from client.quit()


@nose.tools.timed(2)
@nose.tools.raises(ConnectionRefusedError)
@aioftp_setup()
@with_connection
def test_closing_pasv_connection(loop, client, server):

    yield from client.login()
    r, w = yield from client.get_passive_connection()
    host, port = w.transport.get_extra_info("peername")
    yield from client.quit()
    yield from asyncio.open_connection(host, port, loop=loop)


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError)
@aioftp_setup()
@with_connection
def test_server_shutdown(loop, client, server):

    @asyncio.coroutine
    def close_server():

        yield from asyncio.sleep(1, loop=loop)
        server.close()
        yield from server.wait_closed()

    yield from client.login()
    asyncio.async(close_server(), loop=loop)
    while True:

        yield from client.list()
        yield from asyncio.sleep(0.5, loop=loop)


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    os.environ["PYTHONASYNCIODEBUG"] = "1"
    logging.basicConfig(
        level=logging.INFO
    )

    test_server_shutdown()
    print("done")
