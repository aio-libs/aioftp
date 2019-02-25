import nose

from common import *  # noqa
import aioftp


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_retr_0(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.download_stream("foo.txt", offset=0) as stream:

        r = await stream.read()

    await client.quit()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foobar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_retr_3(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.download_stream("foo.txt", offset=3) as stream:

        r = await stream.read()

    await client.quit()

    tmp_file.unlink()
    nose.tools.eq_(r, b"bar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_retr_100(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.download_stream("foo.txt", offset=100) as stream:

        r = await stream.read()

    await client.quit()

    tmp_file.unlink()
    nose.tools.eq_(r, b"")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_stor_0(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    await client.login()
    async with client.upload_stream("foo.txt", offset=0) as stream:

        await stream.write(b"foobar")

    await client.quit()

    with tmp_file.open(mode="rb") as fin:

        r = fin.read()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foobar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_stor_3(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.upload_stream("foo.txt", offset=3) as stream:

        await stream.write(b"foo")

    await client.quit()

    with tmp_file.open(mode="rb") as fin:

        r = fin.read()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foofoo")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_stor_10(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.upload_stream("foo.txt", offset=10) as stream:

        await stream.write(b"foo")

    await client.quit()

    with tmp_file.open(mode="rb") as fin:

        r = fin.read()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foobar" + b"\x00" * 4 + b"foo")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_appe_10(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    async with client.append_stream("foo.txt", offset=10) as stream:

        await stream.write(b"foo")

    await client.quit()

    with tmp_file.open(mode="rb") as fin:

        r = fin.read()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foobar" + b"\x00" * 4 + b"foo")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_restart_reset(loop, client, server, *, tmp_dir):

    tmp_file = tmp_dir / "foo.txt"
    with tmp_file.open(mode="w") as fout:

        fout.write("foobar")

    await client.login()
    await client.command("REST 3", "350")
    async with client.download_stream("foo.txt") as stream:

        r = await stream.read()

    await client.quit()

    tmp_file.unlink()
    nose.tools.eq_(r, b"foobar")


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@expect_codes_in_exception("501")
@with_connection
async def test_restart_syntax_error(loop, client, server):

    await client.login()
    await client.command("REST 3abc", "350")
