import functools

import nose

from common import *  # noqa


@nose.tools.nottest
def raw_memory_path_io(*args, **kwargs):

    return aioftp.MemoryPathIO(*args, **kwargs)


@nose.tools.nottest
def check_universal_exception_reason(expect):

    def decorator(f):

        @functools.wraps(f)
        def wrapper(*args, **kwargs):

            try:

                return f(*args, **kwargs)

            except aioftp.PathIOError as exc:

                type, instance, traceback = exc.reason
                if type != expect:

                    raise Exception(
                        str.format(
                            "Exception type mismatch {} != {}",
                            type,
                            expect
                        )
                    )

            except:

                raise Exception(
                    str.format(
                        "Unexpected exception {}, {}, {}",
                        type,
                        instance,
                        traceback
                    )
                )

        return wrapper

    return decorator


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
async def test_memory_path_upload_download(loop, client, server):

    await client.login()
    r = await client.list()
    nose.tools.eq_(len(r), 0)

    data = b"foobar"

    stream = await client.upload_stream("foo.txt")
    await stream.write(data)
    await stream.finish()

    stream = await client.download_stream("foo.txt")
    rdata = await stream.read()
    await stream.finish()

    await client.quit()
    nose.tools.eq_(data, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
async def test_memory_path_directory_create(loop, client, server):

    await client.login()
    r = await client.list()
    nose.tools.eq_(len(r), 0)

    await client.make_directory("bar")
    data = b"foobar"

    stream = await client.upload_stream("bar/foo.txt")
    await stream.write(data)
    await stream.finish()

    stream = await client.download_stream("bar/foo.txt")
    rdata = await stream.read()
    await stream.finish()

    nose.tools.eq_(data, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
async def test_memory_path_append(loop, client, server):

    await client.login()
    r = await client.list()
    nose.tools.eq_(len(r), 0)

    data = b"foobar"

    stream = await client.upload_stream("foo.txt")
    await stream.write(data)
    await stream.finish()

    stream = await client.append_stream("foo.txt")
    await stream.write(data)
    await stream.finish()

    stream = await client.download_stream("foo.txt")
    rdata = await stream.read()
    await stream.finish()

    await client.quit()
    nose.tools.eq_(data * 2, rdata)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
async def test_memory_path_remove(loop, client, server):

    await client.login()
    r = await client.list()
    nose.tools.eq_(len(r), 0)

    await client.make_directory("bar")
    data = b"foobar"

    stream = await client.upload_stream("bar/foo.txt")
    await stream.write(data)
    await stream.finish()

    await client.remove("bar")
    r = await client.list()
    nose.tools.eq_(len(r), 0)

    await client.quit()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
@expect_codes_in_exception("550")
async def test_memory_path_unreachable_path_upload(loop, client, server):

    await client.login()
    data = b"foobar"

    stream = await client.upload_stream("bar")
    await stream.write(data)
    await stream.finish()

    stream = await client.upload_stream("bar/foo.txt")
    await stream.write(data)
    await stream.finish()


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_unreachable_path_raw(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    nose.tools.eq_(mp.get_node(pathlib.PurePosixPath("/foo/bar/baz")), None)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    nose.tools.eq_(mp.get_node(pathlib.PurePosixPath("/foo/bar/baz")), None)


@check_universal_exception_reason(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_mkdir_on_exist(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo"))
    await mp.mkdir(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_mkdir_unreachable_parents(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo/bar"))


@check_universal_exception_reason(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_unreachable_mkdir_cause_file(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    await mp.mkdir(pathlib.PurePosixPath("/foo/bar"))


@check_universal_exception_reason(FileExistsError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_unreachable_mkdir_cause_file_with_parents(loop,
                                                                     client,
                                                                     server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    await mp.mkdir(pathlib.PurePosixPath("/foo/bar"), parents=True)


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_remove_directory_not_exists(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.rmdir(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(NotADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_remove_directory_is_file(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    await mp.rmdir(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(OSError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_remove_directory_not_empty(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo"))
    await mp.open(pathlib.PurePosixPath("/foo/bar"), "wb")
    await mp.rmdir(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_unlink_not_exists(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.unlink(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_unlink_not_file(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo"))
    await mp.unlink(pathlib.PurePosixPath("/foo"))


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_list_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    r = await mp.list(pathlib.PurePosixPath("/foo"))
    nose.tools.eq_(r, [])


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_stat_not_exists(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.stat(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_read_not_exists(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"))


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_write_parent_file(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    await mp.open(pathlib.PurePosixPath("/foo/bar"), "wb")


@check_universal_exception_reason(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_write_dir(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo"))
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_write_over(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")
    await mp.open(pathlib.PurePosixPath("/foo"), "wb")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_append_new(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "ab")


@check_universal_exception_reason(IsADirectoryError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_append_over_dir(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.mkdir(pathlib.PurePosixPath("/foo"))
    await mp.open(pathlib.PurePosixPath("/foo"), "ab")


@check_universal_exception_reason(ValueError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_open_bad_mode(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.open(pathlib.PurePosixPath("/foo"), "foobar")


@check_universal_exception_reason(FileNotFoundError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_rename_not_exists(loop, client, server):

    mp = raw_memory_path_io(loop=loop)
    await mp.rename(
        pathlib.PurePosixPath("/foo"),
        pathlib.PurePosixPath("/bar")
    )


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_rename_to_not_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    s, d = pathlib.PurePosixPath("/foo"), pathlib.PurePosixPath("/bar")
    await mp.open(s, "wb")
    await mp.rename(s, d)
    nose.tools.eq_(await mp.exists(d), True)
    nose.tools.eq_(await mp.exists(s), False)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_rename_to_exists(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    s, d = pathlib.PurePosixPath("/foo"), pathlib.PurePosixPath("/bar")
    await mp.open(s, "wb")
    await mp.open(d, "wb")
    await mp.rename(s, d)
    nose.tools.eq_(await mp.exists(d), True)
    nose.tools.eq_(await mp.exists(s), False)


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_seek_read(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    tmp_file = pathlib.PurePosixPath("/foo.txt")

    f = await mp.open(tmp_file, "wb")
    await f.write(b"foobar")
    await f.close()

    f = await mp.open(tmp_file, "r+b")
    await f.seek(3)
    r = await f.read()
    nose.tools.eq_(r, b"bar")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_seek_write(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    tmp_file = pathlib.PurePosixPath("/foo.txt")

    f = await mp.open(tmp_file, "wb")
    await f.write(b"foobar")
    await f.close()

    f = await mp.open(tmp_file, "r+b")
    await f.seek(3)
    await f.write(b"foo")

    f = await mp.open(tmp_file, "rb")
    r = await f.read()
    await f.close()

    nose.tools.eq_(r, b"foofoo")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
async def test_memory_path_seek_write_over_end(loop, client, server):

    mp = aioftp.MemoryPathIO(loop=loop)
    tmp_file = pathlib.PurePosixPath("/foo.txt")

    f = await mp.open(tmp_file, "wb")
    await f.write(b"foobar")
    await f.close()

    f = await mp.open(tmp_file, "r+b")
    await f.seek(10)
    await f.write(b"foo")

    f = await mp.open(tmp_file, "rb")
    r = await f.read()
    await f.close()

    nose.tools.eq_(r, b"foobar" + b"\x00" * 4 + b"foo")


@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path=pathlib.PurePosixPath("/")),)],
        {"path_io_factory": aioftp.MemoryPathIO}))
@with_connection
async def test_memory_path_save_state_on_reconnection(loop, client, server):
    data = b"test"
    await client.login()
    async with client.upload_stream("foo.txt") as stream:
        await stream.write(data)
    async with client.download_stream("foo.txt") as stream:
        assert (await stream.read()) == data
    await client.quit()
    await client.connect("127.0.0.1", PORT)
    await client.login()
    assert (await client.exists("foo.txt"))
    async with client.download_stream("foo.txt") as stream:
        assert (await stream.read()) == data


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_memory_path_rename_to_not_exists()
    print("done")
