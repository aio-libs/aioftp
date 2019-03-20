import pytest


async def not_implemented(connection, rest):
    connection.response("502", ":P")
    return True


@pytest.mark.asyncio
async def test_client_fallback_to_pasv_at_list(pair_factory):
    async with pair_factory(host="127.0.0.1") as pair:
        pair.server.epsv = not_implemented
        await pair.client.list()
