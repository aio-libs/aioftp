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


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_native_list(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    tmp_file.touch()

    lines = []
    yield from client.login()
    stream = yield from client.get_stream(str.strip("LIST"), "1xx")
    while True:

        raw = yield from stream.readline()
        if not raw:

            break

        lines.append(raw)

    con = next(iter(server.connections.values()))
    yield from client.quit()
    ans = yield from server.build_list_string(con, tmp_file)
    tmp_file.unlink()

    nose.tools.eq_(len(lines), 1)
    line, *_ = lines
    line = str.strip(bytes.decode(line, "utf-8"))
    nose.tools.eq_(line, ans)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_recursive_list(loop, client, server, *, tmp_dir):

    d = tmp_dir / "foo"
    (tmp_dir / "bar.txt").touch()
    d.mkdir()
    (d / "baz.foo").touch()

    yield from client.login()
    paths = set()
    for path, stats in (yield from client.list(recursive=True)):

        paths.add(path)

    (d / "baz.foo").unlink()
    (tmp_dir / "bar.txt").unlink()
    d.rmdir()
    names = "bar.txt", "foo", "foo/baz.foo"
    nose.tools.ok_(paths == set(map(pathlib.Path, names)))

    yield from client.quit()


@nose.tools.raises(aioftp.PathIsNotFileOrDir)
@aioftp_setup()
def test_not_a_file_or_dir(loop, client, server):

    class NotFileOrDirPathIO(aioftp.AbstractPathIO):

        @asyncio.coroutine
        def is_file(self, path):

            return False

        @asyncio.coroutine
        def is_dir(self, path):

            return False

    yield from server.build_mlsx_string(
        aioftp.Connection(
            path_io=NotFileOrDirPathIO(loop),
            path_timeout=None,
            loop=loop,
        ),
        pathlib.Path("/foo")
    )


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_exists()
    test_is_dir()
    test_is_file()
    test_stats()
    test_native_list()
    test_recursive_list()
    test_not_a_file_or_dir()
    print("done")
