from common import *  # noqa


@aioftp_setup(
    server_args=([(aioftp.User(
        base_path="tests/foo",
        home_path="/",
        permissions=[aioftp.Permission(writable=False)],
    ),)], {}))
@with_connection
@expect_codes_in_exception("550")
async def test_permission_denied(loop, client, server):

    await client.login()
    await client.make_directory("bar")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User(
        base_path="tests/foo",
        home_path="/",
        permissions=[
            aioftp.Permission("/", writable=False),
            aioftp.Permission("/bar"),
            aioftp.Permission("/foo"),
        ],
    ),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_permission_overriden(loop, client, server, *, tmp_dir):

    await client.login()
    await client.make_directory("bar")
    await client.remove_directory("bar")
    await client.quit()
