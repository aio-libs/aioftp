from common import *


@aioftp_setup()
@with_connection
@expect_codes_in_exception("503")
def test_not_logged_in(loop, client, server):

    cwd = yield from client.get_current_directory()


@aioftp_setup()
@with_connection
def test_anonymous_login(loop, client, server):

    yield from client.login()
    yield from client.quit()


@aioftp_setup()
@with_connection
def test_login_with_login_data(loop, client, server):

    yield from client.login("foo", "bar")
    yield from client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo"),)], {}))
@with_connection
def test_login_with_login_and_no_password(loop, client, server):

    yield from client.login("foo")
    yield from client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
def test_login_with_login_and_password(loop, client, server):

    yield from client.login("foo", "bar")
    yield from client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
@expect_codes_in_exception("530")
def test_login_with_login_and_password_no_such_user(loop, client, server):

    yield from client.login("fo", "bar")
    yield from client.quit()


@aioftp_setup(
    server_args=([(aioftp.User("foo", "bar"),)], {}))
@with_connection
@expect_codes_in_exception("530")
def test_login_with_login_and_password_bad_password(loop, client, server):

    yield from client.login("foo", "baz")
    yield from client.quit()


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_login_with_login_and_no_password()
    print("done")
