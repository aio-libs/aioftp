from common import *  # noqa


@nose.tools.raises(OSError)
@aioftp_setup()
async def test_client_without_server(loop, client, server):

    await client.connect("127.0.0.1", PORT)


@aioftp_setup()
@with_connection
async def test_connection(loop, client, server):

    pass


@aioftp_setup()
@with_connection
async def test_quit(loop, client, server):

    await client.quit()


@aioftp_setup()
@with_connection
async def test_dirty_quit(loop, client, server):

    await asyncio.sleep(0.5, loop=loop)
    client.close()
    await asyncio.sleep(0.5, loop=loop)


@aioftp_setup()
@with_connection
@expect_codes_in_exception("502")
async def test_not_implemented(loop, client, server):

    await client.command("FOOBAR", "2xx", "1xx")


@aioftp_setup()
@with_connection
@expect_codes_in_exception("502")
async def test_type_not_implemented(loop, client, server):

    await client.login()
    await client.get_passive_connection("A")


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError)
@aioftp_setup()
@with_connection
async def test_extra_pasv_connection(loop, client, server):

    await client.login()
    r, w = await client.get_passive_connection()
    er, ew = await client.get_passive_connection()
    while True:

        ew.write(b"-" * 8192)
        await asyncio.sleep(0.1, loop=loop)
        await ew.drain()

    await client.quit()


@nose.tools.timed(2)
@nose.tools.raises(ConnectionError)
@aioftp_setup()
@with_connection
async def test_closing_pasv_connection(loop, client, server):

    await client.login()
    r, w = await client.get_passive_connection()
    host, port = w.transport.get_extra_info("peername")
    nr, nw = await asyncio.open_connection(host, port, loop=loop)
    while True:

        nw.write(b"-" * 100)
        await asyncio.sleep(0.1, loop=loop)
        await nw.drain()

    await client.quit()


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError)
@aioftp_setup()
@with_connection
async def test_server_shutdown(loop, client, server):

    async def close_server():

        await asyncio.sleep(1, loop=loop)
        server.close()
        await server.wait_closed()

    await client.login()
    loop.create_task(close_server())
    while True:

        await client.list()
        await asyncio.sleep(0.5, loop=loop)


@aioftp_setup()
async def test_client_zeros_passiv_ip(loop, client, server):

    await server.start(None, PORT)
    await client.connect("127.0.0.1", PORT)

    await client.login()
    r, w = await client.get_passive_connection()
    w.close()

    client.close()
    server.close()
    await server.wait_closed()

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
