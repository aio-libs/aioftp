import pathlib

import nose

from common import *  # noqa


@aioftp_setup()
@with_connection
async def test_current_directory_simple(loop, client, server):

    await client.login()
    cwd = await client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.PurePosixPath("/"))


@aioftp_setup(
    server_args=([(aioftp.User(home_path="/foo"),)], {}))
@with_connection
async def test_current_directory_not_default(loop, client, server):

    await client.login()
    cwd = await client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.PurePosixPath("/foo"))


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo", home_path="/"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_mlsd(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "test.txt"
    tmp_file.touch()

    await client.login()
    cwd = await client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.PurePosixPath("/"))

    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)

    nose.tools.eq_(path, pathlib.PurePosixPath("test.txt"))
    nose.tools.eq_(stat["type"], "file")

    tmp_file.unlink()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo", home_path="/"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_resolving_double_dots(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "test.txt"
    tmp_file.touch()

    await client.login()

    async def f():

        cwd = await client.get_current_directory()
        nose.tools.eq_(cwd, pathlib.PurePosixPath("/"))

        (path, stat), *_ = files = await client.list()
        nose.tools.eq_(len(files), 1)

        nose.tools.eq_(path, pathlib.PurePosixPath("test.txt"))
        nose.tools.eq_(stat["type"], "file")

    await f()
    await client.change_directory("../../../")
    await f()
    await client.change_directory("/a/../b/..")
    await f()

    tmp_file.unlink()
