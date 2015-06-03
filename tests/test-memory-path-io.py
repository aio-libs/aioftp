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
    yield from client.upload_file("foo.txt", io.BytesIO(data))

    recv = bytearray()
    yield from client.download_file("foo.txt", callback=recv.extend)

    yield from client.quit()
    nose.tools.eq_(data, bytes(recv))


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
    yield from client.upload_file("bar/foo.txt", io.BytesIO(data))

    recv = bytearray()
    yield from client.download_file("bar/foo.txt", callback=recv.extend)

    yield from client.quit()
    nose.tools.eq_(data, bytes(recv))


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
    yield from client.upload_file("foo.txt", io.BytesIO(data))
    yield from client.append_file("foo.txt", io.BytesIO(data))

    recv = bytearray()
    yield from client.download_file("foo.txt", callback=recv.extend)

    yield from client.quit()
    nose.tools.eq_(data * 2, bytes(recv))


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
    yield from client.upload_file("bar/foo.txt", io.BytesIO(data))
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
    yield from client.upload_file("bar", io.BytesIO(data))
    yield from client.upload_file("bar/foo.txt", io.BytesIO(data))


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_path_raw(loop, client, server):

    mp = aioftp.MemoryPathIO()
    nose.tools.eq_(mp.get_node(pathlib.Path("/foo/bar/baz")), None)
    yield from mp.open(pathlib.Path("/foo"), "wb")
    nose.tools.eq_(mp.get_node(pathlib.Path("/foo/bar/baz")), None)


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_mkdir_on_exist(loop, client, server):

    mp = aioftp.MemoryPathIO()
    yield from mp.mkdir(pathlib.Path("/foo"))
    yield from mp.mkdir(pathlib.Path("/foo"))


@nose.tools.raises(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_mkdir_unreachable_parents(loop, client, server):

    mp = aioftp.MemoryPathIO()
    yield from mp.mkdir(pathlib.Path("/foo/bar"))


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_mkdir_cause_file(loop, client, server):

    mp = aioftp.MemoryPathIO()
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.mkdir(pathlib.Path("/foo/bar"))


@nose.tools.raises(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="/"),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
def test_memory_path_unreachable_mkdir_cause_file_with_parents(loop, client,
                                                               server):

    mp = aioftp.MemoryPathIO()
    yield from mp.open(pathlib.Path("/foo"), "wb")
    yield from mp.mkdir(pathlib.Path("/foo/bar"), parents=True)


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_memory_path_unreachable_mkdir_cause_file_with_parents()
    print("done")
