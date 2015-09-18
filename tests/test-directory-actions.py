import pathlib

import nose

from common import *


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_create_and_remove_directory(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("bar"))
    nose.tools.eq_(stat["type"], "dir")

    yield from client.remove_directory("bar")
    files = yield from client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_create_and_remove_directory_long(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar/baz")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("bar"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = yield from client.list("bar")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("bar/baz"))
    nose.tools.eq_(stat["type"], "dir")

    yield from client.remove_directory("bar/baz")
    yield from client.remove_directory("bar")
    files = yield from client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_create_directory_long_no_parents(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar/baz", parents=False)
    yield from client.remove_directory("bar/baz")
    yield from client.remove_directory("bar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_change_directory(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    yield from client.change_directory("bar")
    cwd = yield from client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.Path("/bar"))

    yield from client.change_directory()
    cwd = yield from client.get_current_directory()
    nose.tools.eq_(cwd, pathlib.Path("/"))

    yield from client.remove_directory("bar")
    files = yield from client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@expect_codes_in_exception("550")
@with_tmp_dir("foo")
def test_change_directory_not_exist(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.change_directory("bar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_rename_empty_directory(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("bar"))
    nose.tools.eq_(stat["type"], "dir")

    yield from client.rename("bar", "baz")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("baz"))
    nose.tools.eq_(stat["type"], "dir")

    yield from client.remove_directory("baz")
    files = yield from client.list()
    nose.tools.eq_(len(files), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_rename_non_empty_directory(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("bar"))
    nose.tools.eq_(stat["type"], "dir")

    tmp_file = tmp_dir / "bar" / "foo.txt"
    tmp_file.touch()

    yield from client.make_directory("hurr")
    yield from client.rename("bar", "hurr/baz")
    (path, stat), *_ = files = yield from client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("hurr"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = yield from client.list("hurr")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("hurr/baz"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = yield from client.list("/hurr/baz")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.Path("/hurr/baz/foo.txt"))
    nose.tools.eq_(stat["type"], "file")

    tmp_file = tmp_dir / "hurr" / "baz" / "foo.txt"
    tmp_file.unlink()
    yield from client.remove_directory("hurr/baz")
    yield from client.remove_directory("hurr")
    files = yield from client.list()
    nose.tools.eq_(len(files), 0)
