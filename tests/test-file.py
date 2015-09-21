import pathlib
import io
import contextlib

import nose

from common import *


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_remove_single_file(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    nose.tools.ok_(tmp_file.exists() == False)
    tmp_file.touch()
    nose.tools.ok_(tmp_file.exists())

    yield from client.login()
    yield from client.remove_file("foo.txt")
    yield from client.quit()

    nose.tools.ok_(tmp_file.exists() == False)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_recursive_remove(loop, client, server, *, tmp_dir):

    d = tmp_dir / "foo"
    d.mkdir()
    (d / "bar.txt").touch()
    (d / "baz.foo").touch()
    dd = d / "bar_dir"
    dd.mkdir()
    (dd / "foo.baz").touch()

    yield from client.login()
    yield from client.remove("foo")
    r = yield from client.list()
    yield from client.quit()

    nose.tools.eq_(len(r), 0)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_file_download(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo"
    with f.open("w") as fout:

        fout.write("foobar")

    yield from client.login()
    stream = yield from client.download_stream("foo")
    data = yield from stream.read()
    yield from stream.finish()
    yield from client.quit()

    f.unlink()

    nose.tools.eq_(data, b"foobar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_file_upload(loop, client, server, *, tmp_dir):

    def callback(data):

        nose.tools.eq_(data, b)

    f = tmp_dir / "foo"
    b = b"foobar"

    yield from client.login()

    stream = yield from client.upload_stream("foo")
    yield from stream.write(b)
    yield from stream.finish()
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b, rb)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_file_append(loop, client, server, *, tmp_dir):

    f = tmp_dir / "foo"
    with f.open("w") as fout:

        fout.write("foobar")

    ab = b"foobar"
    file_like = io.BytesIO(ab)
    yield from client.login()
    stream = yield from client.append_stream("foo")
    yield from stream.write(ab)
    yield from stream.finish()
    yield from client.quit()

    with f.open("rb") as fin:

        rb = fin.read()

    f.unlink()

    nose.tools.eq_(b"foobar" + ab, rb)


@contextlib.contextmanager
def make_some_files(path):

    for i in range(4):

        f = path / str.format("file{}", i)
        with f.open("w") as fout:

            fout.write("foobar")

    yield
    for i in range(4):

        f = path / str.format("file{}", i)
        f.unlink()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_upload_folder(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    ecdir = cdir / "extra"
    ecdir.mkdir()

    with make_some_files(cdir), make_some_files(ecdir):

        spaths = set(
            map(
                lambda p: p.relative_to(cdir),
                cdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.upload(cdir)
        rpaths = set(
            map(
                lambda p: p.relative_to(sdir / "client"),
                (sdir / "client").rglob("*"),
            )
        )
        yield from client.remove("/")
        yield from client.quit()

    ecdir.rmdir()
    cdir.rmdir()
    nose.tools.eq_(spaths, rpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_upload_folder_into(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    ecdir = cdir / "extra"
    ecdir.mkdir()

    with make_some_files(cdir), make_some_files(ecdir):

        spaths = set(
            map(
                lambda p: p.relative_to(cdir),
                cdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.upload(cdir, write_into=True)
        rpaths = set(
            map(
                lambda p: p.relative_to(sdir),
                (sdir).rglob("*"),
            )
        )
        yield from client.remove("/")
        yield from client.quit()

    ecdir.rmdir()
    cdir.rmdir()
    nose.tools.eq_(spaths, rpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_upload_folder_into_another(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    esdir = sdir / "foo"
    esdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    ecdir = cdir / "extra"
    ecdir.mkdir()

    with make_some_files(cdir), make_some_files(ecdir):

        spaths = set(
            map(
                lambda p: p.relative_to(cdir),
                cdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.upload(cdir, "foo", write_into=True)
        rpaths = set(
            map(
                lambda p: p.relative_to(esdir),
                (esdir).rglob("*"),
            )
        )
        yield from client.remove("/")
        yield from client.quit()

    ecdir.rmdir()
    cdir.rmdir()
    nose.tools.eq_(spaths, rpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_download_folder(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    esdir = sdir / "extra"
    esdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    with make_some_files(sdir), make_some_files(esdir):

        spaths = set(
            map(
                lambda p: p.relative_to(sdir),
                sdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.download("/server", cdir)
        cpaths = set(
            map(
                lambda p: p.relative_to(cdir / "server"),
                (cdir / "server").rglob("*"),
            )
        )
        yield from client.remove("/client")
        yield from client.quit()

    esdir.rmdir()
    sdir.rmdir()
    nose.tools.eq_(spaths, cpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_download_folder_into(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    esdir = sdir / "extra"
    esdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    with make_some_files(sdir), make_some_files(esdir):

        spaths = set(
            map(
                lambda p: p.relative_to(sdir),
                sdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.download("/server", cdir, write_into=True)
        cpaths = set(
            map(
                lambda p: p.relative_to(cdir),
                (cdir).rglob("*"),
            )
        )
        yield from client.remove("/client")
        yield from client.quit()

    esdir.rmdir()
    sdir.rmdir()
    nose.tools.eq_(spaths, cpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_download_folder_into_another(loop, client, server, *, tmp_dir):

    sdir = tmp_dir / "server"
    sdir.mkdir()

    esdir = sdir / "extra"
    esdir.mkdir()

    cdir = tmp_dir / "client"
    cdir.mkdir()

    with make_some_files(sdir), make_some_files(esdir):

        spaths = set(
            map(
                lambda p: p.relative_to(sdir),
                sdir.rglob("*")
            )
        )
        yield from client.login()
        yield from client.download("/server", cdir / "foo", write_into=True)
        cpaths = set(
            map(
                lambda p: p.relative_to(cdir / "foo"),
                (cdir / "foo").rglob("*"),
            )
        )
        yield from client.remove("/client")
        yield from client.quit()

    esdir.rmdir()
    sdir.rmdir()
    nose.tools.eq_(spaths, cpaths)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_upload_file_into_another(loop, client, server, *, tmp_dir):

    cfile = tmp_dir / "client_file.txt"
    sfile = tmp_dir / "server_file.txt"
    with cfile.open("w") as fout:

        fout.write("foobar")

    yield from client.login()
    yield from client.upload(cfile, sfile.name, write_into=True)

    with sfile.open() as fin:

        data = fin.read()

    cfile.unlink()
    sfile.unlink()
    nose.tools.eq_("foobar", data)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_download_file(loop, client, server, *, tmp_dir):

    cfile = tmp_dir / "bar" / "server_file.txt"
    sfile = tmp_dir / "server_file.txt"

    with sfile.open("w") as fout:

        fout.write("foobar")

    yield from client.login()
    yield from client.download(sfile.name, tmp_dir / "bar")

    with cfile.open() as fin:

        data = fin.read()

    cfile.unlink()
    cfile.parent.rmdir()
    sfile.unlink()
    nose.tools.eq_("foobar", data)


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_download_file_write_into(loop, client, server, *, tmp_dir):

    cfile = tmp_dir / "client_file.txt"
    sfile = tmp_dir / "server_file.txt"

    with sfile.open("w") as fout:

        fout.write("foobar")

    yield from client.login()
    yield from client.download(sfile.name, cfile, write_into=True)

    with cfile.open() as fin:

        data = fin.read()

    cfile.unlink()
    sfile.unlink()
    nose.tools.eq_("foobar", data)


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )
    # test_remove_single_file()
    # test_recursive_remove()
    # test_file_download()
    # test_file_upload()
    # test_file_append()
    test_upload_folder()
    test_upload_folder_into()
    test_upload_folder_into_another()
    test_download_folder()
    test_download_folder_into()
    test_download_folder_into_another()
    test_upload_file_into_another()
    test_download_file()
    test_download_file_write_into()
    print("done")
