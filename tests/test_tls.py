import ssl
import sys

import pytest

if sys.version_info < (3, 11):
    pytest.skip(reason="required python 3.11+", allow_module_level=True)


def _is_tls_connection(conn):
    return isinstance(conn.get_extra_info("ssl_object"), (ssl.SSLObject, ssl.SSLSocket))


def simple_response(code, message):
    async def command(connection, rest):
        connection.response(code, message)
        return True

    return command


AUTH_RESPONSE = simple_response("234", ":P")
PBSZ_RESPONSE = simple_response("200", ":P")
PROT_RESPONSE = simple_response("200", ":P")
OK_RESPONSE = simple_response("200", ":P")


@pytest.mark.asyncio
async def test_upgrade_to_tls(mocker, pair_factory):
    ssl_context = object()
    create_default_context = mocker.patch("aioftp.client.ssl.create_default_context", return_value=ssl_context)

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = AUTH_RESPONSE
        pair.server.commands_mapping["pbsz"] = PBSZ_RESPONSE
        pair.server.commands_mapping["prot"] = PROT_RESPONSE

        start_tls = mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls()

    create_default_context.assert_called_once_with()
    start_tls.assert_called_once_with(sslcontext=ssl_context, server_hostname=pair.client.server_host)
    assert command_spy.call_count == 3
    command_spy.assert_has_calls(
        [
            mocker.call("AUTH TLS", "234"),
            mocker.call("PBSZ 0", "200"),
            mocker.call("PROT P", "200"),
        ],
    )


@pytest.mark.asyncio
async def test_upgrade_to_tls_custom_ssl_context(mocker, pair_factory):
    ssl_context = object()
    create_default_context = mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = AUTH_RESPONSE
        pair.server.commands_mapping["pbsz"] = PBSZ_RESPONSE
        pair.server.commands_mapping["prot"] = PROT_RESPONSE

        start_tls = mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls(sslcontext=ssl_context)

    create_default_context.assert_not_called()
    start_tls.assert_called_once_with(sslcontext=ssl_context, server_hostname=pair.client.server_host)
    assert command_spy.call_count == 3
    command_spy.assert_has_calls(
        [
            mocker.call("AUTH TLS", "234"),
            mocker.call("PBSZ 0", "200"),
            mocker.call("PROT P", "200"),
        ],
    )


@pytest.mark.asyncio
async def test_upgrade_to_tls_when_logged_in(mocker, pair_factory):
    mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = AUTH_RESPONSE
        pair.server.commands_mapping["pbsz"] = OK_RESPONSE
        pair.server.commands_mapping["prot"] = OK_RESPONSE

        mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls()

    command_spy.assert_has_calls(
        [
            mocker.call("AUTH TLS", "234"),
            mocker.call("PBSZ 0", "200"),
            mocker.call("PROT P", "200"),
        ],
    )


@pytest.mark.asyncio
async def test_ftps_connection(pair_factory, Server, Client, server_ssl, client_ssl):
    async with pair_factory(server=Server(ssl=server_ssl), client=Client(ssl=client_ssl)) as pair:
        assert pair.client._stream.writer.get_extra_info("ssl_object") is not None


@pytest.mark.asyncio
async def test_ftps_passive_connection(pair_factory, Server, Client, server_ssl, client_ssl):
    async with pair_factory(server=Server(ssl=server_ssl), client=Client(ssl=client_ssl)) as pair:
        reader, writer = await pair.client.get_passive_connection("A")
        assert _is_tls_connection(writer)


@pytest.mark.asyncio
async def test_ftpes_connection(pair_factory, Server, server_ssl, client_ssl, expect_codes_in_exception):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=False) as pair:
        assert not _is_tls_connection(pair.client._stream.writer)
        await pair.client.upgrade_to_tls(client_ssl)
        assert _is_tls_connection(pair.client._stream.writer)
        with expect_codes_in_exception("503"):
            await pair.client.upgrade_to_tls(client_ssl)


@pytest.mark.asyncio
async def test_ftpes_passive_connection(pair_factory, Server, server_ssl, client_ssl):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=False) as pair:
        await pair.client.upgrade_to_tls(client_ssl)
        await pair.client.login()
        reader, writer = await pair.client.get_passive_connection("A")
        assert _is_tls_connection(writer)


@pytest.mark.asyncio
async def test_authtls_fail_after_login(pair_factory, Server, server_ssl, client_ssl, expect_codes_in_exception):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=True) as pair:
        with expect_codes_in_exception("503"):
            await pair.client.upgrade_to_tls(client_ssl)


@pytest.mark.asyncio
async def test_authtls_not_supported(pair_factory, client_ssl, expect_codes_in_exception):
    async with pair_factory(logged=False) as pair:
        with expect_codes_in_exception("502"):
            await pair.client.upgrade_to_tls(client_ssl)


@pytest.mark.asyncio
async def test_authtls_type_not_supported(pair_factory, Server, server_ssl, expect_codes_in_exception):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=False) as pair:
        with expect_codes_in_exception("504"):
            await pair.client.command("AUTH foo", "234")


@pytest.mark.asyncio
async def test_ssl_parameter(pair_factory, Server):
    with pytest.raises(ValueError):
        async with pair_factory(server=Server(ssl=None, ssl_explicit=True)):
            pass


@pytest.mark.asyncio
async def test_pbsz(pair_factory, Server, server_ssl, client_ssl, expect_codes_in_exception):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=False) as pair:
        with expect_codes_in_exception("503"):
            await pair.client.command("pbsz 0", "200")
        await pair.client.upgrade_to_tls(client_ssl)
        await pair.client.command("pbsz 0", "200")


@pytest.mark.asyncio
async def test_prot(pair_factory, Server, server_ssl, client_ssl, expect_codes_in_exception):
    async with pair_factory(server=Server(ssl=server_ssl, ssl_explicit=True), logged=False) as pair:
        with expect_codes_in_exception("503"):
            await pair.client.command("prot P", "200")
        await pair.client.upgrade_to_tls(client_ssl)
        await pair.client.command("prot P", "200")
        with expect_codes_in_exception("502"):
            await pair.client.command("prot foo", "200")
