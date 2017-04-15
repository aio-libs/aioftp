import pathlib

import nose

from common import *  # noqa


async def not_implemented(connection, rest):

    connection.response("502", ":P")
    return True


@aioftp_setup(server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_client_fallback_to_list_at_list(loop, client, server, *, tmp_dir):

    server.mlst = not_implemented
    server.mlsd = not_implemented

    await client.login()
    await client.make_directory("bar")
    async with client.upload_stream("bar/foo.txt") as stream:

        await stream.write(b"foo")

    (path, stat), *_ = files = await client.list()
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

    (path, stat), *_ = files = await client.list("bar")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar/foo.txt"))
    nose.tools.eq_(stat["type"], "file")

    await client.remove("bar")
    files = await client.list()
    nose.tools.eq_(len(files), 0)
