import pathlib

import nose

from common import *  # noqa


async def not_implemented(connection, rest):

    connection.response("502", ":P")
    return True

async def implemented_badly(connection, rest):

    nose.tools.ok_(False, 'should not be called')

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

@aioftp_setup(server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_client_list_override(loop, client, server, *, tmp_dir):

    server.mlsd = implemented_badly

    await client.login()
    await client.make_directory("bar")

    (path, stat), *_ = files = await client.list(raw_command="LIST")
    nose.tools.eq_(len(files), 1)
    nose.tools.eq_(path, pathlib.PurePosixPath("bar"))
    nose.tools.eq_(stat["type"], "dir")

@nose.tools.raises(ValueError)
@aioftp_setup()
@with_connection
async def test_client_list_override_invalid_raw_command(loop, client, server):
    await client.list(raw_command="FOO")

def test_client_list_windows():
    p = aioftp.Client.parse_list_line_windows
    test_str = """
 11/4/2018   9:09 PM  <DIR>         .
 8/10/2018   1:02 PM  <DIR>         ..
 9/23/2018   2:16 PM  <DIR>         bin
10/16/2018  10:25 PM  <DIR>         Desktop
 11/4/2018   3:31 PM  <DIR>         dow
10/16/2018   8:21 PM  <DIR>         Downloads
10/14/2018   5:34 PM  <DIR>         msc
  9/9/2018   9:32 AM  <DIR>         opt
 10/3/2018   2:58 PM    34,359,738,368  win10.img
 6/30/2018   8:36 AM    3,939,237,888  win10.iso
 7/26/2018   1:11 PM           189  win10.sh
10/29/2018  11:46 AM    34,359,738,368  win7.img
 6/30/2018   8:35 AM    3,319,791,616  win7.iso
10/29/2018  10:55 AM           219  win7.sh   
       6 files           75,978,506,648 bytes
       3 directories     22,198,362,112 bytes free
  """
    test_str = test_str.strip().split("\n")
    entities = []
    for x in test_str:
        try:
            entities.append(p(aioftp.Client,x))
        except ValueError as e:
            pass
    # The spaces in "win7.sh   " are supposed to be there
    # We parse file names with spaces to the best of our ability
    correct_names = set(["bin","Desktop","dow","Downloads","msc","opt","win10.img","win10.iso","win10.sh","win7.img","win7.iso","win7.sh   "])
    nose.tools.eq_(len(correct_names),len(entities))
    for x in entities:
        correct_names.remove(str(x[0]))
    nose.tools.eq_(len(correct_names),0)
