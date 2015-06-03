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

        yield from client.abort()
        future.set_result(True)

    class FakeInfiniteFile():

        def __init__(self):

            self.abort = True

        def read(self, count=1):

            if self.abort:

                self.abort = False
                asyncio.async(request_abort(), loop=loop)

            return b"-" * count

    future = asyncio.Future(loop=loop)
    yield from client.login()
    yield from client.upload_file("/test.txt", FakeInfiniteFile())
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

        yield from client.abort()
        future.set_result(True)

    def callback(data):

        nonlocal abort_requested
        nose.tools.eq_(set(data), set(b"-"))
        if not abort_requested:

            abort_requested = True
            asyncio.async(request_abort(), loop=loop)

    abort_requested = False
    future = asyncio.Future(loop=loop)
    yield from client.login()
    yield from client.download_file("/test.txt", callback=callback)
    yield from future
    yield from client.quit()


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )
    test_abort_retr()
    print("done")
