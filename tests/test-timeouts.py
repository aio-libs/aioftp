import nose

from common import *


@nose.tools.raises(ConnectionResetError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {"idle_timeout": 1}))
@with_connection
def test_idle_timeout(loop, client, server):

    yield from asyncio.sleep(2, loop=loop)
    yield from client.login()


class SlowMemoryPathIO(aioftp.MemoryPathIO):

    @asyncio.coroutine
    def mkdir(self, path, parents=False):

        yield from asyncio.sleep(10, loop=self.loop)


@nose.tools.raises(ConnectionResetError)
@aioftp_setup(
    server_args=(
        [(aioftp.User(base_path="tests/foo", home_path="/"),)],
        {
            "path_timeout": 1,
            "path_io_factory": SlowMemoryPathIO,
        }))
@with_connection
def test_path_timeout(loop, client, server):

    yield from client.login()
    yield from client.make_directory("foo")


if __name__ == "__main__":

    import logging
    import os

    os.environ["AIOFTP_TESTS"] = "PathIO"
    logging.basicConfig(
        level=logging.INFO
    )

    test_path_timeout()
    print("done")
