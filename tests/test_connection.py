import asyncio

import pytest

import aioftp


@pytest.mark.asyncio
async def test_client_without_server(pair_factory, unused_tcp_port_factory):
    f = pair_factory(connected=False, logged=False, do_quit=False)
    async with f as pair:
        pass
    with pytest.raises(OSError):
        await pair.client.connect("127.0.0.1", unused_tcp_port_factory())


@pytest.mark.asyncio
async def test_connection(pair_factory):
    async with pair_factory(connected=True, logged=False, do_quit=False):
        pass


@pytest.mark.asyncio
async def test_quit(pair_factory):
    async with pair_factory(connected=True, logged=False, do_quit=True):
        pass


@pytest.mark.asyncio
async def test_not_implemented(pair_factory, expect_codes_in_exception):
    async with pair_factory() as pair:
        with expect_codes_in_exception("502"):
            await pair.client.command("FOOBAR", "2xx", "1xx")


@pytest.mark.asyncio
async def test_type_success(pair_factory, expect_codes_in_exception):
    async with pair_factory() as pair:
        await pair.client.get_passive_connection("A")


@pytest.mark.asyncio
async def test_extra_pasv_connection(pair_factory):
    async with pair_factory() as pair:
        r, w = await pair.client.get_passive_connection()
        er, ew = await pair.client.get_passive_connection()
        with pytest.raises((ConnectionResetError, BrokenPipeError)):
            while True:
                w.write(b"-" * aioftp.DEFAULT_BLOCK_SIZE)
                await w.drain()


@pytest.mark.asyncio
async def test_closing_pasv_connection(pair_factory):
    async with pair_factory() as pair:
        r, w = await pair.client.get_passive_connection()
        host, port, *_ = w.transport.get_extra_info("peername")
        nr, nw = await asyncio.open_connection(host, port)
        with pytest.raises((ConnectionResetError, BrokenPipeError)):
            while True:
                nw.write(b"-" * aioftp.DEFAULT_BLOCK_SIZE)
                await nw.drain()


@pytest.mark.asyncio
async def test_pasv_connection_ports_not_added(pair_factory):
    async with pair_factory() as pair:
        r, w = await pair.client.get_passive_connection()
        assert pair.server.available_data_ports is None


@pytest.mark.asyncio
async def test_pasv_connection_ports(pair_factory, Server,
                                     unused_tcp_port_factory):
    ports = [unused_tcp_port_factory(), unused_tcp_port_factory()]
    async with pair_factory(None, Server(data_ports=ports)) as pair:
        r, w = await pair.client.get_passive_connection()
        host, port, *_ = w.transport.get_extra_info("peername")
        assert port in ports
        assert pair.server.available_data_ports.qsize() == 1


@pytest.mark.asyncio
async def test_data_ports_remains_empty(pair_factory, Server):
    async with pair_factory(None, Server(data_ports=[])) as pair:
        assert pair.server.available_data_ports.qsize() == 0


@pytest.mark.asyncio
async def test_pasv_connection_port_reused(pair_factory, Server,
                                           unused_tcp_port):
    s = Server(data_ports=[unused_tcp_port])
    async with pair_factory(None, s) as pair:
        r, w = await pair.client.get_passive_connection()
        host, port, *_ = w.transport.get_extra_info("peername")
        assert port == unused_tcp_port
        assert pair.server.available_data_ports.qsize() == 0
        w.close()
        await pair.client.quit()
        pair.client.close()
        assert pair.server.available_data_ports.qsize() == 1
        await pair.client.connect(pair.server.server_host,
                                  pair.server.server_port)
        await pair.client.login()
        r, w = await pair.client.get_passive_connection()
        host, port, *_ = w.transport.get_extra_info("peername")
        assert port == unused_tcp_port
        assert pair.server.available_data_ports.qsize() == 0


@pytest.mark.asyncio
async def test_pasv_connection_no_free_port(pair_factory, Server,
                                            expect_codes_in_exception):
    s = Server(data_ports=[])
    async with pair_factory(None, s, do_quit=False) as pair:
        assert pair.server.available_data_ports.qsize() == 0
        with expect_codes_in_exception("421"):
            await pair.client.get_passive_connection()


@pytest.mark.asyncio
async def test_pasv_connection_busy_port(pair_factory, Server,
                                         unused_tcp_port_factory):
    ports = [unused_tcp_port_factory(), unused_tcp_port_factory()]
    async with pair_factory(None, Server(data_ports=ports)) as pair:
        conflicting_server = await asyncio.start_server(
            lambda r, w: w.close(),
            host=pair.server.server_host,
            port=ports[0],
        )
        r, w = await pair.client.get_passive_connection()
        host, port, *_ = w.transport.get_extra_info("peername")
        assert port == ports[1]
        assert pair.server.available_data_ports.qsize() == 1
    conflicting_server.close()
    await conflicting_server.wait_closed()


@pytest.mark.asyncio
async def test_pasv_connection_busy_port2(pair_factory, Server,
                                          unused_tcp_port_factory,
                                          expect_codes_in_exception):
    ports = [unused_tcp_port_factory()]
    s = Server(data_ports=ports)
    async with pair_factory(None, s, do_quit=False) as pair:
        conflicting_server = await asyncio.start_server(
            lambda r, w: w.close(),
            host=pair.server.server_host,
            port=ports[0],
        )
        with expect_codes_in_exception("421"):
            await pair.client.get_passive_connection()
    conflicting_server.close()
    await conflicting_server.wait_closed()


@pytest.mark.asyncio
async def test_server_shutdown(pair_factory):
    async with pair_factory(do_quit=False) as pair:
        await pair.client.list()
        await pair.server.close()
        with pytest.raises(ConnectionResetError):
            await pair.client.list()


@pytest.mark.asyncio
async def test_client_session_context_manager(pair_factory):
    async with pair_factory(connected=False) as pair:
        async with aioftp.ClientSession(*pair.server.address) as client:
            await client.list()
