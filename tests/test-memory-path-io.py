import io

import nose

from common import *


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
def test_memory_path_upload_download(loop, client, server):

    yield from client.login()
    r = yield from client.list()
    nose.tools.eq_(len(r), 0)

    data = b"foobar"

    stream = yield from client.upload_stream("foo.txt")
    yield from stream.write(data)
    yield from stream.finish()

    stream = yield from client.download_stream("foo.txt")
    rdata = yield from stream.read()
    yield from stream.finish()


    yield from client.quit()
    nose.tools.eq_(data, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
def test_memory_path_directory_create(loop, client, server):

    yield from client.login()
    r = yield from client.list()
    nose.tools.eq_(len(r), 0)

    yield from client.make_directory("bar")
    data = b"foobar"

    stream = yield from client.upload_stream("bar/foo.txt")
    yield from stream.write(data)
    yield from stream.finish()

    stream = yield from client.download_stream("bar/foo.txt")
    rdata = yield from stream.read()
    yield from stream.finish()

    nose.tools.eq_(data, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
def test_memory_path_append(loop, client, server):

    yield from client.login()
    r = yield from client.list()
    nose.tools.eq_(len(r), 0)

    data = b"foobar"

    stream = yield from client.upload_stream("foo.txt")
    yield from stream.write(data)
    yield from stream.finish()

    stream = yield from client.append_stream("foo.txt")
    yield from stream.write(data)
    yield from stream.finish()

    stream = yield from client.download_stream("foo.txt")
    rdata = yield from stream.read()
    yield from stream.finish()

    yield from client.quit()
    nose.tools.eq_(data * 2, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
def test_memory_path_remove(loop, client, server):

    yield from client.login()
    r = yield from client.list()
    nose.tools.eq_(len(r), 0)

    yield from client.make_directory("bar")
    data = b"foobar"

    stream = yield from client.upload_stream("bar/foo.txt")
    yield from stream.write(data)
    yield from stream.finish()

    yield from client.remove("bar")
    r = yield from client.list()
    nose.tools.eq_(len(r), 0)

    yield from client.quit()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
@expect_codes_in_exception("550")
def test_memory_path_unreachable_path_upload(loop, client, server):

    yield from client.login()
    data = b"foobar"

    stream = yield from client.upload_stream("bar")
    yield from stream.write(data)
    yield from stream.finish()

    stream = yield from client.upload_stream("bar/foo.txt")
    yield from stream.write(data)
    yield from stream.finish()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_path_raw(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    nose.tools.eq_(mp.get_node(pathlib.Path("/foo/bar/baz")), None)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    nose.tools.eq_(mp.get_node(pathlib.Path("/foo/bar/baz")), None)


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_mkdir_on_exist(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.mkdir(pathlib.Path("/foo"))


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_mkdir_unreachable_parents(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo/bar"))


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_mkdir_cause_file(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.mkdir(pathlib.Path("/foo/bar"))


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_mkdir_cause_file_with_parents(loop, client,
                                                               server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.mkdir(pathlib.Path("/foo/bar"), parents=True)


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_remove_directory_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.rmdir(pathlib.Path("/foo"))


@nose.tools.raises(NotADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_remove_directory_is_file(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.rmdir(pathlib.Path("/foo"))


@nose.tools.raises(OSError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_remove_directory_not_empty(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.open(pathlib.Path("/foo/bar"), "wb")
    yield from mp.rmdir(pathlib.Path("/foo"))


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unlink_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.unlink(pathlib.Path("/foo"))


@nose.tools.raises(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unlink_not_file(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.unlink(pathlib.Path("/foo"))


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_list_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    r = yield from mp.list(pathlib.Path("/foo"))
    nose.tools.eq_(r, tuple())


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_stat_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    r = yield from mp.stat(pathlib.Path("/foo"))


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_read_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"))


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_write_parent_file(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.open(pathlib.Path("/foo/bar"), "wb")


@nose.tools.raises(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_write_dir(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.open(pathlib.Path("/foo"), "wb")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_write_over(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.open(pathlib.Path("/foo"), "wb")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_append_new(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "ab")


@nose.tools.raises(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_append_over_dir(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.open(pathlib.Path("/foo"), "ab")


@nose.tools.raises(ValueError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_open_bad_mode(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.open(pathlib.Path("/foo"), "foobar")


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_rename_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    yield from mp.rename(pathlib.Path("/foo"), pathlib.Path("/bar"))


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_rename_to_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    s, d = pathlib.Path("/foo"), pathlib.Path("/bar")
    yield from mp.open(s, "wb")
    yield from mp.rename(s, d)
    nose.tools.eq_((yield from mp.exists(d)), True)
    nose.tools.eq_((yield from mp.exists(s)), False)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_rename_to_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop)
    s, d = pathlib.Path("/foo"), pathlib.Path("/bar")
    yield from mp.open(s, "wb")
    yield from mp.open(d, "wb")
    yield from mp.rename(s, d)
    nose.tools.eq_((yield from mp.exists(d)), True)
    nose.tools.eq_((yield from mp.exists(s)), False)


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_memory_path_rename_to_not_exists()
    print("done")
