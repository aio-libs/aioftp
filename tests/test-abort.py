import nose

from common import *  # noqa


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)], {}))
@with_connection
@with_tmp_dir("foo")
def test_abort_stor(loop, client, server, *, tmp_dir):

    @asyncio.coroutine
    def request_abort():

        yield from asyncio.sleep(0.1, loop=loop)
        yield from client.abort()
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    yield from client.login()
    stream = yield from client.upload_stream("/test.txt")
    asyncio.async(request_abort(), loop=loop)
    while True:

        try:

            for _ in range(5):

                yield from stream.write(b"-" * 8192)
                yield from asyncio.sleep(0.1, loop=loop)

            yield from stream.finish()
            raise Exception("Not aborted")

        except (ConnectionResetError, BrokenPipeError):

            break

    yield from future
    yield from client.quit()
    file = (tmp_dir / "test.txt")
    nose.tools.ok_(file.stat().st_size)
    file.unlink()


class FakeSlowPathIO(aioftp.PathIO):

    @asyncio.coroutine
    def exists(self, path):

        return True

    @asyncio.coroutine
    def is_file(self, path):

        return True

    @asyncio.coroutine
    def open(self, path, *args, **kwargs):

        return

    @asyncio.coroutine
    def close(self, *args, **kwargs):

        return

    @asyncio.coroutine
    def read(self, *args, **kwargs):

        yield from asyncio.sleep(0.05, loop=self.loop)
        return b"-" * 8192


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)],
                 {"path_io_factory": FakeSlowPathIO}))
@with_connection
@with_tmp_dir("foo")
def test_abort_retr(loop, client, server, *, tmp_dir):

    @asyncio.coroutine
    def request_abort():

        yield from asyncio.sleep(0.1, loop=loop)
        yield from client.abort()
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    yield from client.login()
    stream = yield from client.download_stream("/test.txt")
    asyncio.async(request_abort(), loop=loop)
    while True:

        data = yield from stream.read(8192)
        if not data:

            break

    yield from future
    yield from client.quit()


@aioftp_setup(
    server_args=([(aioftp.User(base_path="tests/foo"),)],
                 {"path_io_factory": FakeSlowPathIO}))
@expect_codes_in_exception("426")
@with_connection
@with_tmp_dir("foo")
def test_abort_retr_no_wait(loop, client, server, *, tmp_dir):

    @asyncio.coroutine
    def request_abort():

        yield from asyncio.sleep(0.1, loop=loop)
        yield from client.abort(wait=False)
        future.set_result(True)

    future = asyncio.Future(loop=loop)
    yield from client.login()
    stream = yield from client.download_stream("/test.txt")
    asyncio.async(request_abort(), loop=loop)
    while True:

        data = yield from stream.read(8192)
        if not data:

            yield from stream.finish()
            break

    yield from future
    yield from client.quit()


@aioftp_setup()
@with_connection
def test_nothing_to_abort(loop, client, server):

    yield from client.login()
    yield from client.abort()
    yield from client.quit()


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
    # test_abort_retr()
    print("done")
