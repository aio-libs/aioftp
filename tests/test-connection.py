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
async def test_type_success(loop, client, server):
    await client.login()
    await client.get_passive_connection("A")


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError, BrokenPipeError)
@aioftp_setup()
@with_connection
async def test_extra_pasv_connection(loop, client, server):

    await client.login()
    r, w = await client.get_passive_connection()
    er, ew = await client.get_passive_connection()
    while True:

        w.write(b"-" * 8192)
        await asyncio.sleep(0.1, loop=loop)
        await w.drain()

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


@aioftp_setup()
@with_connection
async def test_pasv_connection_ports_not_added(loop, client, server):

    await client.login()
    await client.get_passive_connection()
    await client.quit()

    nose.tools.eq_(server.available_data_ports, None)


@aioftp_setup(server_args=([], {"data_ports": [30000, 30001]}))
@with_connection
async def test_pasv_connection_ports(loop, client, server):

    clients = [aioftp.Client(loop=loop) for _ in range(2)]
    expected_data_ports = [30000, 30001]

    for i, client in enumerate(clients):

        await client.connect("127.0.0.1", PORT)
        await client.login()
        r, w = await client.get_passive_connection()
        host, port = w.transport.get_extra_info("peername")
        nose.tools.eq_(port, expected_data_ports[i])

    for client in clients:

        await client.quit()


@aioftp_setup(server_args=([], {"data_ports": []}))
@with_connection
async def test_data_ports_remains_empty(loop, client, server):

    await client.login()
    await client.quit()

    nose.tools.eq_(server.available_data_ports.qsize(), 0)


@aioftp_setup(server_args=([], {"data_ports": [30000]}))
@with_connection
async def test_pasv_connection_port_reused(loop, client, server):

    clients = [aioftp.Client(loop=loop) for _ in range(2)]

    for client in clients:

        await client.connect("127.0.0.1", PORT)
        await client.login()
        r, w = await client.get_passive_connection()
        host, port = w.transport.get_extra_info("peername")
        nose.tools.eq_(port, 30000)
        await client.quit()


@aioftp_setup(server_args=([], {"data_ports": []}))
@expect_codes_in_exception("421")
@with_connection
async def test_pasv_connection_no_free_port(loop, client, server):

    await client.login()
    await client.get_passive_connection()


@aioftp_setup(server_args=([], {"data_ports": [30000, 30001]}))
@with_connection
async def test_pasv_connection_busy_port(loop, client, server):

    async def handle(reader, writer):
        writer.close()

    conflicting_server = await asyncio.start_server(
        handle,
        host=server.server_host,
        port=30000,
        loop=loop
    )

    await client.login()
    r, w = await client.get_passive_connection()
    host, port = w.transport.get_extra_info("peername")
    nose.tools.eq_(port, 30001)
    await client.quit()

    conflicting_server.close()
    await conflicting_server.wait_closed()


@aioftp_setup(server_args=([], {"data_ports": [30000]}))
@expect_codes_in_exception("421")
@with_connection
async def test_pasv_connection_busy_port2(loop, client, server):

    async def handle(reader, writer):
        writer.close()

    conflicting_server = await asyncio.start_server(
        handle,
        host=server.server_host,
        port=30000,
        loop=loop
    )

    await client.login()
    try:
        await client.get_passive_connection()
    finally:
        conflicting_server.close()
        await conflicting_server.wait_closed()


@aioftp_setup(server_args=([], {"data_ports": [30000, 30001]}))
@expect_codes_in_exception("421")
@with_connection
async def test_pasv_connection_busy_port3(loop, client, server):

    async def handle(reader, writer):
        writer.close()

    conflicting_server1 = await asyncio.start_server(
        handle,
        host=server.server_host,
        port=30000,
        loop=loop
    )

    conflicting_server2 = await asyncio.start_server(
        handle,
        host=server.server_host,
        port=30001,
        loop=loop
    )

    await client.login()
    try:
        await client.get_passive_connection()
    finally:
        conflicting_server1.close()
        conflicting_server2.close()
        await conflicting_server1.wait_closed()
        await conflicting_server2.wait_closed()


@nose.tools.timed(2)
@nose.tools.raises(ConnectionResetError)
@aioftp_setup()
@with_connection
async def test_server_shutdown(loop, client, server):

    async def close_server():

        await asyncio.sleep(1, loop=loop)
        await server.close()

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
    await server.close()


def test_client_session_context_manager():

    async def test():
        server = aioftp.Server(loop=loop)
        await server.start(None, PORT)
        kw = dict(host="127.0.0.1", port=PORT, loop=loop)
        async with aioftp.ClientSession(**kw) as client:
            async for path in client.list():
                pass
        await server.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)
    loop.run_until_complete(test())


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
