import pathlib

import nose

from common import *  # noqa


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_create_and_remove_directory(loop, client, server, *, tmp_dir):

    await client.login()
    await client.make_directory("bar")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

    await client.remove_directory("bar")
    files = await client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_create_and_remove_directory_long(loop, client, server, *,
                                                tmp_dir):

    await client.login()
    await client.make_directory("bar/baz")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = await client.list("bar")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar/baz"))
    nose.tools.eq_(stat["type"], "dir")

    await client.remove_directory("bar/baz")
    await client.remove_directory("bar")
    files = await client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_create_directory_long_no_parents(loop, client, server, *,
                                                tmp_dir):

    await client.login()
    await client.make_directory("bar/baz", parents=False)
    await client.remove_directory("bar/baz")
    await client.remove_directory("bar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_change_directory(loop, client, server, *, tmp_dir):

    await client.login()
    await client.make_directory("bar")
    await client.change_directory("bar")
    cwd = await client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.PurePosixPath("/bar"))

    await client.change_directory()
    cwd = await client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.PurePosixPath("/"))

    await client.remove_directory("bar")
    files = await client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@expect_codes_in_exception("550")
@with_tmp_dir("foo")
async def test_change_directory_not_exist(loop, client, server, *, tmp_dir):

    await client.login()
    await client.change_directory("bar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_rename_empty_directory(loop, client, server, *, tmp_dir):

    await client.login()
    await client.make_directory("bar")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

    await client.rename("bar", "baz")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("baz"))
    nose.tools.eq_(stat["type"], "dir")

    await client.remove_directory("baz")
    files = await client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_rename_non_empty_directory(loop, client, server, *, tmp_dir):

    await client.login()
    await client.make_directory("bar")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

    tmp_file = tmp_dir / "bar" / "foo.txt"
    tmp_file.touch()

    await client.make_directory("hurr")
    await client.rename("bar", "hurr/baz")
    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("hurr"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = await client.list("hurr")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("hurr/baz"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = await client.list("/hurr/baz")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("/hurr/baz/foo.txt"))
    nose.tools.eq_(stat["type"], "file")

    tmp_file = tmp_dir / "hurr" / "baz" / "foo.txt"
    tmp_file.unlink()
    await client.remove_directory("hurr/baz")
    await client.remove_directory("hurr")
    files = await client.list()
    nose.tools.eq_(len(files), 0)


class FakeErrorPathIO(aioftp.PathIO):

    def list(self, path):

        class Lister(aioftp.AbstractAsyncLister):
            iter = None

            @aioftp.pathio.universal_exception
            @aioftp.with_timeout
            async def __anext__(self):
                if self.iter is None:
                    self.iter = path.glob("*")
                try:
                    raise Exception("KERNEL PANIC")
                except StopIteration:
                    raise StopAsyncIteration

        return Lister(timeout=self.timeout, loop=self.loop)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests"),)],
                 {"path_io_factory": FakeErrorPathIO}))
@expect_codes_in_exception("451")
@with_connection
async def test_exception_in_list(loop, client, server):

    await client.login()
    await client.list()
