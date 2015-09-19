import pathlib

import nose

from common import *


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

        except (ConnectionResetError, BrokenPipeError):

            break

    yield from stream.finish()
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

        yield from asyncio.sleep(1, loop=self.loop)
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

    abort_requested = False
    future = asyncio.Future(loop=loop)
    yield from client.login()
    stream = yield from client.download_stream("/test.txt")
    asyncio.async(request_abort(), loop=loop)
    while True:

        try:

            data = yield from stream.read(8192)
            if not data:

                break

        except (ConnectionResetError, BrokenPipeError):

            break

    yield from stream.finish()
    yield from future
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
