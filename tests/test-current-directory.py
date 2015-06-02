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


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo", home_path="/"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_mlsd(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "test.txt"
    tmp_file.touch()

    yield from client.login()
    cwd = yield from client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.Path("/"))

    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)

    nose.tools.eq_(path, pathlib.Path("test.txt"))
    nose.tools.eq_(stat["type"], "file")

    tmp_file.unlink()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo", home_path="/"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_resolving_double_dots(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "test.txt"
    tmp_file.touch()

    yield from client.login()

    @asyncio.coroutine
    def f():

        cwd = yield from client.get_current_directory()
        nose.tools.eq_(cwd, pathlib.Path("/"))

        (path, stat), *_ = files = yield from client.list()
        nose.tools.eq_(len(files), 1)

        nose.tools.eq_(path, pathlib.Path("test.txt"))
        nose.tools.eq_(stat["type"], "file")

    yield from f()
    yield from client.change_directory("../../../")
    yield from f()
    yield from client.change_directory("/a/../b/..")
    yield from f()

    tmp_file.unlink()
