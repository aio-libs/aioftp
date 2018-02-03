import socket

from common import *


@aioftp_setup()
@with_connection(host="::1", family=socket.AF_INET6)
async def test_ipv6_pasv_rejected(loop, client, server):
    await client.login()
    await client.list()
