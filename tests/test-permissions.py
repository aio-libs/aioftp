from common import *


@aioftp_setup(
    server_args=([(aioftp.User(
        base_path="tests/foo",
        home_path="/",
        permissions=[aioftp.Permission(writable=False)],
    ),)], {}))
@with_connection
@expect_codes_in_exception("550")
def test_permission_denied(loop, client, server):

    yield from client.login()
    yield from client.make_directory("bar")
    yield from client.quit()


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
def test_permission_overriden(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    yield from client.remove_directory("bar")
    yield from client.quit()


def test_permission_representation():

    p = aioftp.Permission(writable=False)
    nose.tools.eq_(
        repr(p),
        "Permission(PurePosixPath('/'), readable=True, writable=False)"
    )
