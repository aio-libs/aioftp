import nose

from common import *  # noqa


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
async def test_abort_stor(loop, client, server, *, tmp_dir):

    async def request_abort():

        await asyncio.sleep(0.1, loop=loop)
        await client.abort()
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    await client.login()
    stream = await client.upload_stream("/test.txt")
    loop.create_task(request_abort())
    while True:

        try:

            for _ in range(5):

                await stream.write(b"-" * 8192)
                await asyncio.sleep(0.1, loop=loop)

            await stream.finish()
            raise Exception("Not aborted")

        except (ConnectionResetError, BrokenPipeError):

            break

    await future
    await client.quit()
    file = (tmp_dir / "test.txt")
    nose.tools.ok_(file.stat().st_size)
    file.unlink()


class FakeSlowPathIO(aioftp.PathIO):

    async def exists(self, path):

        return True

    async def is_file(self, path):

        return True

    async def _open(self, path, *args, **kwargs):

        return path

    async def close(self, *args, **kwargs):

        return

    async def read(self, *args, **kwargs):

        await asyncio.sleep(0.05, loop=self.loop)
        return b"-" * 8192


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)],
                 {"path_io_factory": FakeSlowPathIO}))
@with_connection
@with_tmp_dir("foo")
async def test_abort_retr(loop, client, server, *, tmp_dir):

    async def request_abort():

        await asyncio.sleep(0.1, loop=loop)
        await client.abort()
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    await client.login()
    stream = await client.download_stream("/test.txt")
    loop.create_task(request_abort())
    while True:

        data = await stream.read(8192)
        if not data:

            break

    await future
    await client.quit()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)],
                 {"path_io_factory": FakeSlowPathIO}))
@expect_codes_in_exception("426")
@with_connection
@with_tmp_dir("foo")
async def test_abort_retr_no_wait(loop, client, server, *, tmp_dir):

    async def request_abort():

        await asyncio.sleep(0.1, loop=loop)
        await client.abort(wait=False)
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    await client.login()
    stream = await client.download_stream("/test.txt")
    loop.create_task(request_abort())
    while True:

        data = await stream.read(8192)
        if not data:

            await stream.finish()
            break

    await future
    await client.quit()


@aioftp_setup()
@with_connection
async def test_nothing_to_abort(loop, client, server):

    await client.login()
    await client.abort()
    await client.quit()


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )
    # this test for testing infinite loop of
    # WARNING:asyncio:socket.send() raised exception
    test_abort_stor()
    test_abort_retr()
    test_abort_retr_no_wait()
    test_nothing_to_abort()
    print("done")
