import socket
import os

from common import *


if "TRAVIS" not in os.environ:
    @aioftp_setup()
    @with_connection(host="::1", family=socket.AF_INET6)
    async def test_ipv6_list(loop, client, server):
        await client.login()
        await client.list()
