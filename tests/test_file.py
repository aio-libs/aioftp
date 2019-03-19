import pytest


@pytest.mark.asyncio
async def test_remove_single_file(pair_factory):
    async with pair_factory() as pair:
        await pair.make_server_files("foo.txt")
        assert await pair.server_paths_exists("foo.txt")
        await pair.client.remove_file("foo.txt")
        assert await pair.server_paths_exists("foo.txt") is False


@pytest.mark.asyncio
async def test_recursive_remove(pair_factory):
    async with pair_factory() as pair:
        paths = ["foo/bar.txt", "foo/baz.txt", "foo/bar_dir/foo.baz"]
        await pair.make_server_files(*paths)
        await pair.client.remove("foo")
        assert await pair.server_paths_exists(*paths) is False


@pytest.mark.asyncio
async def test_file_download(pair_factory):
    async with pair_factory() as pair:
        await pair.make_server_files("foo", size=1, atom=b"foobar")
        async with pair.client.download_stream("foo") as stream:
            data = await stream.read()
        assert data == b"foobar"


@pytest.mark.asyncio
async def test_file_upload(pair_factory):
    async with pair_factory() as pair:
        async with pair.client.upload_stream("foo") as stream:
            await stream.write(b"foobar")
        async with pair.client.download_stream("foo") as stream:
            data = await stream.read()
        assert data == b"foobar"


@pytest.mark.asyncio
async def test_file_append(pair_factory):
    async with pair_factory() as pair:
        await pair.make_server_files("foo", size=1, atom=b"foobar")
        async with pair.client.append_stream("foo") as stream:
            await stream.write(b"foobar")
        async with pair.client.download_stream("foo") as stream:
            data = await stream.read()
        assert data == b"foobar" * 2


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_upload_folder(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     ecdir = cdir / "extra"
#     ecdir.mkdir()

#     with make_some_files(cdir), make_some_files(ecdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(cdir),
#                 cdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.upload(cdir)
#         rpaths = set(
#             map(
#                 lambda p: p.relative_to(sdir / "client"),
#                 (sdir / "client").rglob("*"),
#             )
#         )
#         await client.remove("/")
#         await client.quit()

#     ecdir.rmdir()
#     cdir.rmdir()
#     nose.tools.eq_(spaths, rpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_upload_folder_into(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     ecdir = cdir / "extra"
#     ecdir.mkdir()

#     with make_some_files(cdir), make_some_files(ecdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(cdir),
#                 cdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.upload(cdir, write_into=True)
#         rpaths = set(
#             map(
#                 lambda p: p.relative_to(sdir),
#                 (sdir).rglob("*"),
#             )
#         )
#         await client.remove("/")
#         await client.quit()

#     ecdir.rmdir()
#     cdir.rmdir()
#     nose.tools.eq_(spaths, rpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo/server"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_upload_folder_into_another(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     esdir = sdir / "foo"
#     esdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     ecdir = cdir / "extra"
#     ecdir.mkdir()

#     with make_some_files(cdir), make_some_files(ecdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(cdir),
#                 cdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.upload(cdir, "foo", write_into=True)
#         rpaths = set(
#             map(
#                 lambda p: p.relative_to(esdir),
#                 (esdir).rglob("*"),
#             )
#         )
#         await client.remove("/")
#         await client.quit()

#     ecdir.rmdir()
#     cdir.rmdir()
#     nose.tools.eq_(spaths, rpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_download_folder(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     esdir = sdir / "extra"
#     esdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     with make_some_files(sdir), make_some_files(esdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(sdir),
#                 sdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.download("/server", cdir)
#         cpaths = set(
#             map(
#                 lambda p: p.relative_to(cdir / "server"),
#                 (cdir / "server").rglob("*"),
#             )
#         )
#         await client.remove("/client")
#         await client.quit()

#     esdir.rmdir()
#     sdir.rmdir()
#     nose.tools.eq_(spaths, cpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_download_folder_into(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     esdir = sdir / "extra"
#     esdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     with make_some_files(sdir), make_some_files(esdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(sdir),
#                 sdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.download("/server", cdir, write_into=True)
#         cpaths = set(
#             map(
#                 lambda p: p.relative_to(cdir),
#                 (cdir).rglob("*"),
#             )
#         )
#         await client.remove("/client")
#         await client.quit()

#     esdir.rmdir()
#     sdir.rmdir()
#     nose.tools.eq_(spaths, cpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_download_folder_into_another(loop, client, server, *, tmp_dir):

#     sdir = tmp_dir / "server"
#     sdir.mkdir()

#     esdir = sdir / "extra"
#     esdir.mkdir()

#     cdir = tmp_dir / "client"
#     cdir.mkdir()

#     with make_some_files(sdir), make_some_files(esdir):

#         spaths = set(
#             map(
#                 lambda p: p.relative_to(sdir),
#                 sdir.rglob("*")
#             )
#         )
#         await client.login()
#         await client.download("/server", cdir / "foo", write_into=True)
#         cpaths = set(
#             map(
#                 lambda p: p.relative_to(cdir / "foo"),
#                 (cdir / "foo").rglob("*"),
#             )
#         )
#         await client.remove("/client")
#         await client.quit()

#     esdir.rmdir()
#     sdir.rmdir()
#     nose.tools.eq_(spaths, cpaths)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_upload_file_into_another(loop, client, server, *, tmp_dir):

#     cfile = tmp_dir / "client_file.txt"
#     sfile = tmp_dir / "server_file.txt"
#     with cfile.open("w") as fout:

#         fout.write("foobar")

#     await client.login()
#     await client.upload(cfile, sfile.name, write_into=True)

#     with sfile.open() as fin:

#         data = fin.read()

#     cfile.unlink()
#     sfile.unlink()
#     nose.tools.eq_("foobar", data)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_download_file(loop, client, server, *, tmp_dir):

#     cfile = tmp_dir / "bar" / "server_file.txt"
#     sfile = tmp_dir / "server_file.txt"

#     with sfile.open("w") as fout:

#         fout.write("foobar")

#     await client.login()
#     await client.download(sfile.name, tmp_dir / "bar")
#     with cfile.open() as fin:

#         data = fin.read()

#     cfile.unlink()
#     cfile.parent.rmdir()
#     sfile.unlink()
#     nose.tools.eq_("foobar", data)


# @aioftp_setup(
#     server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
# @with_connection
# @with_tmp_dir("foo")
# async def test_download_file_write_into(loop, client, server, *, tmp_dir):

#     cfile = tmp_dir / "client_file.txt"
#     sfile = tmp_dir / "server_file.txt"

#     with sfile.open("w") as fout:

#         fout.write("foobar")

#     await client.login()
#     await client.download(sfile.name, cfile, write_into=True)

#     with cfile.open() as fin:

#         data = fin.read()

#     cfile.unlink()
#     sfile.unlink()
#     nose.tools.eq_("foobar", data)


# class OsErrorPathIO(aioftp.PathIO):

#     @aioftp.pathio.universal_exception
#     @aioftp.with_timeout
#     async def write(self, fout, data):

#         raise OSError("test os error")


# @aioftp_setup(
#     server_args=(
#         [(aioftp.User(base_path="tests/foo"),)],
#         {
#             "path_io_factory": OsErrorPathIO
#         }))
# @with_connection
# @expect_codes_in_exception("451")
# @with_tmp_dir("foo")
# async def test_upload_file_os_error(loop, client, server, *, tmp_dir):

#     await client.login()
#     stream = await client.upload_stream("file.txt")
#     try:

#         await stream.write(b"-" * 1024)
#         await stream.finish()

#     finally:

#         (tmp_dir / "file.txt").unlink()


# if __name__ == "__main__":

#     import logging
#     import os

#     os.environ["AIOFTP_TESTS"] = "PathIO"
#     logging.basicConfig(
#         level=logging.INFO
#     )
#     # test_remove_single_file()
#     # test_recursive_remove()
#     # test_file_download()
#     # test_file_upload()
#     # test_file_append()
#     # test_upload_folder()
#     # test_upload_folder_into()
#     # test_upload_folder_into_another()
#     # test_download_folder()
#     # test_download_folder_into()
#     # test_download_folder_into_another()
#     # test_upload_file_into_another()
#     test_download_file()
#     # test_download_file_write_into()
#     print("done")
