import pytest


async def _auth_response(connection, rest):
    connection.response("234", ":P")
    return True


async def _ok_response(connection, rest):
    connection.response("200", ":P")
    return True


@pytest.mark.asyncio
async def test_upgrade_to_tls(mocker, pair_factory):
    ssl_context = object()
    create_default_context = mocker.patch("aioftp.client.ssl.create_default_context", return_value=ssl_context)

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = _auth_response

        start_tls = mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls()

    create_default_context.assert_called_once_with()
    start_tls.assert_called_once_with(sslcontext=ssl_context, server_hostname=pair.client.server_host)
    command_spy.assert_called_once_with("AUTH TLS", "234")


@pytest.mark.asyncio
async def test_upgrade_to_tls_custom_ssl_context(mocker, pair_factory):
    ssl_context = object()
    create_default_context = mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = _auth_response

        start_tls = mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls(sslcontext=ssl_context)

    create_default_context.assert_not_called()
    start_tls.assert_called_once_with(sslcontext=ssl_context, server_hostname=pair.client.server_host)
    command_spy.assert_called_once_with("AUTH TLS", "234")


@pytest.mark.asyncio
async def test_upgrade_to_tls_does_nothing_when_already_updated(mocker, pair_factory):
    mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.client._upgraded_to_tls = True

        start_tls = mocker.patch.object(pair.client.stream, "start_tls")
        command_spy = mocker.spy(pair.client, "command")

        await pair.client.upgrade_to_tls()

    start_tls.assert_not_called()
    command_spy.assert_not_called()


@pytest.mark.asyncio
async def test_upgrade_to_tls_when_logged_in(mocker, pair_factory):
    mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["auth"] = _auth_response
        pair.server.commands_mapping["pbsz"] = _ok_response
        pair.server.commands_mapping["prot"] = _ok_response
        pair.client._logged_in = True

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
async def test_login_should_send_tls_protection_when_upgraded(mocker, pair_factory):
    mocker.patch("aioftp.client.ssl.create_default_context")

    async with pair_factory(logged=False, do_quit=False) as pair:
        pair.server.commands_mapping["pbsz"] = _ok_response
        pair.server.commands_mapping["prot"] = _ok_response
        pair.client._upgraded_to_tls = True

        command_spy = mocker.spy(pair.client, "command")

        await pair.client.login("foo", "bar")

    command_spy.assert_has_calls(
        [
            mocker.call("PBSZ 0", "200"),
            mocker.call("PROT P", "200"),
        ],
    )
