import pathlib

import pytest

import aioftp


@pytest.mark.asyncio
async def test_create_and_remove_directory(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar")
        (path, stat), *_ = files = await pair.client.list()
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("bar")
        assert stat["type"] == "dir"

        await pair.client.remove_directory("bar")
        files = await pair.client.list()
        assert len(files) == 0


@pytest.mark.asyncio
async def test_create_and_remove_directory_long(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar/baz")
        (path, stat), *_ = files = await pair.client.list()
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("bar")
        assert stat["type"] == "dir"

        (path, stat), *_ = files = await pair.client.list("bar")
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("bar/baz")
        assert stat["type"] == "dir"

        await pair.client.remove_directory("bar/baz")
        await pair.client.remove_directory("bar")
        files = await pair.client.list()
        assert len(files) == 0


@pytest.mark.asyncio
async def test_create_directory_long_no_parents(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar/baz", parents=False)
        await pair.client.remove_directory("bar/baz")
        await pair.client.remove_directory("bar")


@pytest.mark.asyncio
async def test_change_directory(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar")
        await pair.client.change_directory("bar")
        cwd = await pair.client.get_current_directory()
        assert cwd == pathlib.PurePosixPath("/bar")
        await pair.client.change_directory()
        cwd = await pair.client.get_current_directory()
        assert cwd == pathlib.PurePosixPath("/")


@pytest.mark.asyncio
async def test_change_directory_not_exist(pair_factory,
                                          expect_codes_in_exception):
    async with pair_factory() as pair:
        with expect_codes_in_exception("550"):
            await pair.client.change_directory("bar")


@pytest.mark.asyncio
async def test_rename_empty_directory(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar")
        (path, stat), *_ = files = await pair.client.list()
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("bar")
        assert stat["type"] == "dir"
        await pair.client.rename("bar", "baz")
        (path, stat), *_ = files = await pair.client.list()
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("baz")
        assert stat["type"] == "dir"


@pytest.mark.asyncio
async def test_rename_non_empty_directory(pair_factory):
    async with pair_factory() as pair:
        await pair.client.make_directory("bar")
        async with pair.client.upload_stream("bar/foo.txt") as stream:
            await stream.write(b"-")
        (path, stat), *_ = files = await pair.client.list("bar")
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("bar/foo.txt")
        assert stat["type"] == "file"
        await pair.client.make_directory("hurr")
        await pair.client.rename("bar", "hurr/baz")
        (path, stat), *_ = files = await pair.client.list()
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("hurr")
        assert stat["type"] == "dir"
        (path, stat), *_ = files = await pair.client.list("hurr")
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("hurr/baz")
        assert stat["type"] == "dir"
        (path, stat), *_ = files = await pair.client.list("/hurr/baz")
        assert len(files) == 1
        assert path == pathlib.PurePosixPath("/hurr/baz/foo.txt")
        assert stat["type"] == "file"


class FakeErrorPathIO(aioftp.MemoryPathIO):

    def list(self, path):

        class Lister(aioftp.AbstractAsyncLister):
            @aioftp.pathio.universal_exception
            async def __anext__(self):
                raise Exception("KERNEL PANIC")

        return Lister(timeout=self.timeout, loop=self.loop)


@pytest.mark.asyncio
async def test_exception_in_list(pair_factory, Server,
                                 expect_codes_in_exception):
    s = Server(path_io_factory=FakeErrorPathIO)
    async with pair_factory(None, s) as pair:
        with expect_codes_in_exception("451"):
            await pair.client.list()
