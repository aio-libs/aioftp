from common import *  # noqa


@aioftp_setup()
@with_connection
@expect_codes_in_exception("503")
async def test_not_logged_in(loop, client, server):

    await client.get_current_directory()


@aioftp_setup()
@with_connection
async def test_anonymous_login(loop, client, server):

    await client.login()
    await client.quit()


@aioftp_setup()
@with_connection
async def test_login_with_login_data(loop, client, server):

    await client.login("foo", "bar")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo"),)], {}))
@with_connection
async def test_login_with_login_and_no_password(loop, client, server):

    await client.login("foo")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
async def test_login_with_login_and_password(loop, client, server):

    await client.login("foo", "bar")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
@expect_codes_in_exception("530")
async def test_login_with_login_and_password_no_such_user(loop, client,
                                                          server):

    await client.login("fo", "bar")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
@expect_codes_in_exception("530")
async def test_login_with_login_and_password_bad_password(loop, client,
                                                          server):

    await client.login("foo", "baz")
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
@expect_codes_in_exception("503")
async def test_pasv_after_login(loop, client, server):

    await client.login("foo", "bar")
    await client.command("PASS baz", ("230", "33x"))
    await client.quit()


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_login_with_login_and_no_password()
    print("done")
