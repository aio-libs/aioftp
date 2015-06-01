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
def test_quit(loop, client, server):

    yield from asyncio.sleep(0.5, loop=loop)
    client.close()
    yield from asyncio.sleep(0.5, loop=loop)


@aioftp_setup()
@with_connection
@expect_codes_in_exception("502")
def test_not_implemented(loop, client, server):

    yield from client.command("FOOBAR", "2xx", "1xx")
