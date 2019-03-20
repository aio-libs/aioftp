import ssl
import collections
import contextlib
from pathlib import Path

import pytest
import trustme
from async_timeout import timeout

import aioftp


ca = trustme.CA()
server_cert = ca.issue_server_cert("127.0.0.1", "::1")

ssl_server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
server_cert.configure_cert(ssl_server)

ssl_client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ca.configure_trust(ssl_client)


class Container:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


@pytest.fixture
def Client():
    return Container


@pytest.fixture
def Server():
    return Container


def _wrap_with_defaults(kwargs):
    test_defaults = dict(
        path_io_factory=aioftp.MemoryPathIO,
    )
    return collections.ChainMap(kwargs, test_defaults)


@pytest.fixture
def pair_factory():

    class Factory:

        def __init__(self, client=None, server=None, *,
                     connected=True, logged=True, do_quit=True):
            if client is None:
                client = Container()
            self.client = aioftp.Client(*client.args,
                                        **_wrap_with_defaults(client.kwargs))
            if server is None:
                server = Container()
            self.server = aioftp.Server(*server.args,
                                        **_wrap_with_defaults(server.kwargs))
            self.connected = connected
            self.logged = logged
            self.do_quit = do_quit
            self.timeout = timeout(1)

        async def make_server_files(self, *paths, size=None, atom=b"-"):
            if size is None:
                size = aioftp.DEFAULT_BLOCK_SIZE * 3
            data = atom * size
            for p in paths:
                await self.client.make_directory(Path(p).parent)
                async with self.client.upload_stream(p) as stream:
                    await stream.write(data)

        async def make_client_files(self, *paths, size=None, atom=b"-"):
            if size is None:
                size = aioftp.DEFAULT_BLOCK_SIZE * 3
            data = atom * size
            for p in map(Path, paths):
                await self.client.path_io.mkdir(p.parent, parents=True,
                                                exist_ok=True)
                async with self.client.path_io.open(p, mode="wb") as f:
                    await f.write(data)

        async def server_paths_exists(self, *paths):
            values = []
            for p in paths:
                values.append(await self.client.exists(p))
            if all(values):
                return True
            if any(values):
                raise ValueError("Mixed exists/not exists list")
            return False

        async def client_paths_exists(self, *paths):
            values = []
            for p in paths:
                values.append(await self.client.path_io.exists(Path(p)))
            if all(values):
                return True
            if any(values):
                raise ValueError("Mixed exists/not exists list")
            return False

        async def __aenter__(self):
            self.timeout.__enter__()
            await self.server.start()
            if self.connected:
                await self.client.connect(self.server.server_host,
                                          self.server.server_port)
                if self.logged:
                    await self.client.login()
            return self

        async def __aexit__(self, *exc_info):
            if self.connected and self.do_quit:
                await self.client.quit()
            self.client.close()
            await self.server.close()
            self.timeout.__exit__(*exc_info)

    return Factory


@pytest.fixture
def expect_codes_in_exception():
    @contextlib.contextmanager
    def context(*codes):
        try:
            yield
        except aioftp.StatusCodeError as e:
            assert set(e.received_codes) == set(codes)
        else:
            raise RuntimeError("There was no exception")
    return context
