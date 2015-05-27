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
