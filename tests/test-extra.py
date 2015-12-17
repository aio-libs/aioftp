import string
import asyncio

import nose

import aioftp


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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    loop.run_until_complete(worker())
