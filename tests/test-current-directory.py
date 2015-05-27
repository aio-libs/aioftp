import pathlib

import nose

from common import *


@aioftp_setup()
@with_connection
def test_current_directory_simple(loop, client, server):

    yield from client.login()
    cwd = yield from client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.Path("/"))


@aioftp_setup(
    server_args=([(aioftp.User(home_path="/foo"),)], {}))
@with_connection
def test_current_directory_not_default(loop, client, server):

    yield from client.login()
    cwd = yield from client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.Path("/foo"))
