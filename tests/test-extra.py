import asyncio
import contextlib

import nose

import aioftp
from common import *


class MyClient(aioftp.Client):

    async def collect(self, count):

        collected = []
        async with self.get_stream("COLL " + str(count), "1xx") as stream:

            async for line in stream.iter_by_line():

                collected.append(line)

        return collected


class MyServer(aioftp.Server):

    @aioftp.ConnectionConditions(
        aioftp.ConnectionConditions.login_required,
        aioftp.ConnectionConditions.passive_server_started)
    async def coll(self, connection, rest):

        @aioftp.ConnectionConditions(
            aioftp.ConnectionConditions.data_connection_made,
            wait=True,
            fail_code="425",
            fail_info="Can't open data connection")
        @aioftp.server.worker
        async def coll_worker(self, connection, rest):

            stream = connection.data_connection
            del connection.data_connection

            async with stream:

                for i in range(count):

                    await stream.write(str.encode(str(i) + "\n"))

            connection.response("200", "coll transfer done")
            return True

        count = int(rest)
        coro = coll_worker(self, connection, rest)
        task = connection.loop.create_task(coro)
        connection.extra_workers.add(task)
        connection.response("150", "coll transfer started")
        return True


def test_stream_iter_by_line():

    async def worker():

        server = MyServer(loop=loop)
        client = MyClient(loop=loop)

        await server.start("127.0.0.1", 8021)
        await client.connect("127.0.0.1", 8021)
        await client.login()

        count = 20
        expect = list(map(lambda i: str.encode(str(i) + "\n"), range(count)))
        collected = await client.collect(count)
        nose.tools.eq_(collected, expect)
        await client.quit()
        client.close()
        await server.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    loop.run_until_complete(worker())


class CustomException(Exception):

    pass


@aioftp_setup()
@with_connection
async def test_stream_close_without_finish(loop, client, server):

    def fake_finish(*args, **kwargs):

        raise Exception("Finish called")

    await client.login()
    with contextlib.suppress(CustomException):

        async with client.get_stream() as stream:

            stream.finish = fake_finish
            raise CustomException()


@nose.tools.raises(ConnectionRefusedError)
@aioftp_setup()
async def test_no_server(loop, *args, **kwargs):

    async with aioftp.ClientSession("127.0.0.1", loop=loop):

        pass


@aioftp_setup()
@with_connection
async def test_syst_command(loop, client, server):

    await client.login()
    code, info = await client.command("syst", "215")
    nose.tools.eq_(info, [" UNIX Type: L8"])
