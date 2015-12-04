import time

import nose

import aioftp
from common import *  # noqa


@aioftp_setup(
    client_args=(
        [],
        {
            "read_speed_limit": 100 * 1024  # 100 Kib
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_read_throttle(loop, client, server, *, tmp_dir):

    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * (3 * 100 * 1024))  # 300 Kib

    start = time.perf_counter()
    await client.login()
    stream = await client.download_stream("tests/foo/foo.txt")
    count = 0
    while True:

        data = await stream.read()
        if not data:

            await stream.finish()
            break

        count += len(data)

    nose.tools.eq_(count, 3 * 100 * 1024)
    nose.tools.ok_(2.5 < (time.perf_counter() - start) < 3.5)
    big_file.unlink()


@aioftp_setup(
    client_args=(
        [],
        {
            "read_speed_limit": 100 * 1024  # 100 Kib
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_write_with_read_throttle(loop, client, server, *,
                                               tmp_dir):

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    await client.login()
    stream = await client.upload_stream("tests/foo/foo.txt")
    for _ in range(3 * 100):  # 300 Kib

        await stream.write(b"-" * 1024)

    await stream.finish()

    with big_file.open() as fin:

        data = fin.read()

    print(len(data), (time.perf_counter() - start))
    nose.tools.eq_(len(data), 3 * 100 * 1024)
    nose.tools.ok_((time.perf_counter() - start) < 0.5)
    big_file.unlink()


@aioftp_setup(
    client_args=(
        [],
        {
            "write_speed_limit": 100 * 1024  # 100 Kib
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_read_with_write_throttle(loop, client, server, *,
                                               tmp_dir):

    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * (3 * 100 * 1024))  # 300 Kib

    start = time.perf_counter()
    await client.login()
    stream = await client.download_stream("tests/foo/foo.txt")
    count = 0
    while True:

        data = await stream.read()
        if not data:

            await stream.finish()
            break

        count += len(data)

    nose.tools.eq_(count, 3 * 100 * 1024)
    nose.tools.ok_((time.perf_counter() - start) < 0.5)
    big_file.unlink()


@aioftp_setup(
    client_args=(
        [],
        {
            "write_speed_limit": 100 * 1024  # 100 Kib
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_write_throttle(loop, client, server, *, tmp_dir):

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    await client.login()
    stream = await client.upload_stream("tests/foo/foo.txt")
    for _ in range(3 * 100):  # 300 Kib

        await stream.write(b"-" * 1024)

    await stream.finish()

    with big_file.open() as fin:

        data = fin.read()

    nose.tools.eq_(len(data), 3 * 100 * 1024)
    nose.tools.ok_(2.5 < (time.perf_counter() - start) < 3.5)
    big_file.unlink()


@aioftp_setup(
    client_args=(
        [],
        {
            "write_speed_limit": 100 * 1024  # 100 Kib
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_write_throttle_changed_after_creation(loop, client,
                                                            server, *,
                                                            tmp_dir):

    nose.tools.eq_(client.throttle.write.limit, 100 * 1024)
    client.throttle.write.limit = 200 * 1024  # 200 Kib

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    await client.login()
    stream = await client.upload_stream("tests/foo/foo.txt")
    for _ in range(3 * 100):  # 300 Kib

        await stream.write(b"-" * 1024)

    await stream.finish()

    with big_file.open(mode="rb") as fin:

        data = fin.read()

    nose.tools.eq_(len(data), 3 * 100 * 1024)
    nose.tools.ok_(1 < (time.perf_counter() - start) < 2)
    big_file.unlink()


class SlowPathIO(aioftp.PathIO):

    @aioftp.with_timeout
    async def write(self, fout, data):

        timeout = len(data) / (100 * 1024)  # sleep as 100 Kib per second write
        await asyncio.sleep(timeout, loop=self.loop)
        await super().write(fout, data)


@aioftp_setup(
    client_args=(
        [],
        {
            "write_speed_limit": 100 * 1024,  # 100 Kib per second
            "path_io_factory": SlowPathIO,
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_write_throttle_with_slow_io(loop, client, server, *,
                                                  tmp_dir):

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    await client.login()
    await client.download(
        "tests/foo/foo.txt",
        "tests/foo/bar.txt",
        write_into=True
    )

    nose.tools.ok_(2.5 < (time.perf_counter() - start) < 3.5)
    big_file.unlink()
    received = tmp_dir / "bar.txt"
    received.unlink()


@aioftp_setup(
    client_args=(
        [],
        {
            "read_speed_limit": 200 * 1024,  # 200 Kib per second
            "path_io_factory": SlowPathIO,
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_client_read_throttle_with_too_slow_io(loop, client, server, *,
                                                     tmp_dir):

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    await client.login()
    await client.download(
        "tests/foo/foo.txt",
        "tests/foo/bar.txt",
        write_into=True
    )

    nose.tools.ok_(2.5 < (time.perf_counter() - start) < 3.5)
    big_file.unlink()
    received = tmp_dir / "bar.txt"
    received.unlink()


@aioftp_setup(
    server_args=(
        [],
        {
            "write_speed_limit": 200 * 1024,  # 200 Kib per second
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_global_write_throttle_one_user(loop, client, server, *,
                                                     tmp_dir):

    start = time.perf_counter()
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    await client.login()
    await client.download(
        "tests/foo/foo.txt",
        "tests/foo/bar.txt",
        write_into=True
    )

    nose.tools.ok_(1 < (time.perf_counter() - start) < 2)
    big_file.unlink()
    received = tmp_dir / "bar.txt"
    received.unlink()


@aioftp_setup(
    server_args=(
        [],
        {
            "write_speed_limit": 200 * 1024,  # 200 Kib per second
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_global_write_throttle_multi_users(loop, client, server,
                                                        *, tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.download(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [],
        {
            "read_speed_limit": 200 * 1024,  # 200 Kib per second
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_global_read_throttle_multi_users(loop, client, server, *,
                                                       tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.upload(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 10 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(14.5 < (time.perf_counter() - start) < 15.5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [],
        {
            "write_speed_limit_per_connection": 200 * 1024,  # 200 Kib/s
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_per_connection_write_throttle_multi_users(loop, client,
                                                                server, *,
                                                                tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.download(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 9 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [],
        {
            "read_speed_limit_per_connection": 200 * 1024,  # 200 Kib/s
        },
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_per_connection_read_throttle_multi_users(loop, client,
                                                               server, *,
                                                               tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.upload(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 9 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [[aioftp.User(write_speed_limit_per_connection=200 * 1024)]],
        {},
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_user_per_connection_write_throttle_multi_users(loop,
                                                                     client,
                                                                     server, *,
                                                                     tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.download(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 9 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [[aioftp.User(read_speed_limit_per_connection=200 * 1024)]],
        {},
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_user_per_connection_read_throttle_multi_users(loop,
                                                                    client,
                                                                    server, *,
                                                                    tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.upload(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 9 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [[aioftp.User(write_speed_limit=200 * 1024)]],
        {},
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_user_global_write_throttle_multi_users(loop, client,
                                                             server, *,
                                                             tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.download(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


@aioftp_setup(
    server_args=(
        [[aioftp.User(read_speed_limit=200 * 1024)]],
        {},
    ))
@with_connection
@with_tmp_dir("foo")
async def test_server_user_global_read_throttle_multi_users(loop, client,
                                                            server, *,
                                                            tmp_dir):

    async def worker(fname):

        client = aioftp.Client(loop=loop)
        await client.connect("127.0.0.1", PORT)
        await client.login()
        await client.upload(
            "tests/foo/foo.txt",
            str.format("tests/foo/{}", fname),
            write_into=True
        )
        await client.quit()

    fnames = ("bar.txt", "baz.txt", "hurr.txt")
    big_file = tmp_dir / "foo.txt"
    with big_file.open("wb") as fout:

        fout.write(b"-" * 3 * 100 * 1024)

    start = time.perf_counter()
    await asyncio.wait(map(worker, fnames), loop=loop)

    nose.tools.ok_(4 < (time.perf_counter() - start) < 5)

    big_file.unlink()
    for fname in fnames:

        received = tmp_dir / fname
        received.unlink()


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_client_write_throttle()
    print("done")
