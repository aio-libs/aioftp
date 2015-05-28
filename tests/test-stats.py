import pathlib

import nose

from common import *


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_exists(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    exists = yield from client.exists("bar")
    nose.tools.eq_(exists, True)

    yield from client.remove_directory("bar")
    exists = yield from client.exists("bar")
    nose.tools.eq_(exists, False)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_is_dir(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    is_dir = yield from client.is_dir("bar")
    nose.tools.eq_(is_dir, True)

    tmp_file = tmp_dir / "foo.txt"
    tmp_file.touch()

    is_dir = yield from client.is_dir("foo.txt")
    nose.tools.eq_(is_dir, False)

    yield from client.remove_directory("bar")

    tmp_file.unlink()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_is_file(loop, client, server, *, tmp_dir):

    yield from client.login()
    yield from client.make_directory("bar")
    is_file = yield from client.is_file("bar")
    nose.tools.eq_(is_file, False)

    tmp_file = tmp_dir / "foo.txt"
    tmp_file.touch()

    is_file = yield from client.is_file("foo.txt")
    nose.tools.eq_(is_file, True)

    yield from client.remove_directory("bar")

    tmp_file.unlink()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_stats(loop, client, server, *, tmp_dir):

    s = "i'm a text"
    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write(s)

    yield from client.login()
    stats = yield from client.stat("foo.txt")
    nose.tools.eq_(stats["type"], "file")
    nose.tools.eq_(stats["size"], str(len(s)))

    tmp_file.unlink()
