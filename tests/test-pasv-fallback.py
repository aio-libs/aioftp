from common import *


async def not_implemented(connection, rest):
    connection.response("502", ":P")
    return True


@aioftp_setup()
@with_connection
async def test_client_fallback_to_pasv_at_list(loop, client, server):
    server.epsv = not_implemented
    await client.login()
    await client.list()
