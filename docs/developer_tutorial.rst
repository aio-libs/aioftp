.. developer_tutorial:

Tutorial is deprecated!

Developer tutorial
==================

Both, client and server classes are inherit-minded when created. So, you need
to inherit class and override and/or add methods to bring your functionality.

Client
------

For simple commands, which requires no extra connection, realization of new
method is pretty simple. You just need to use :py:meth:`aioftp.Client.command`
(or even don't use it). For example, lets realize «NOOP» command, which do
nothing:

::

    import asyncio

    import aioftp


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def noop(self):

            yield from self.command("NOOP", "2xx")

Lets take a look to a more complex example. Say, we want to collect some data
via extra connection. For this one you need one of «extra connection» methods:
:py:meth:`aioftp.Client.store` and :py:meth:`aioftp.Client.retrieve`.
Here we implements some «COLL x» command. I don't know what it does, but it
retrieve some data via extra connection. And the size of data is equal to «x».

::

    import asyncio

    import aioftp


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def collect(self, count):

            def callback(data):

                for x in data:

                    if x % 2 == 0:

                        collected.append(x)

            collected = []
            yield from self.retrieve(
                "COLL " + str(count),
                "1xx",
                callback=callback,
            )
            return collected

And that is all for client. It is a good idea you to see source code of
:py:class:`aioftp.Client` in client.py to see when and why this or that
techniques used.

Server
------

Server class based on dispatcher, which call methods by name of commands it
received. Returns «not implemented» when there is no method to call. There is
only one method that must be implemented: greeting. It calls when new
connection established. Lets say we want implement «NOOP» command for server
again:

::

    import asyncio

    import aioftp


    class MyServer(aioftp.Server):

        @asyncio.coroutine
        def noop(self, connection, rest):

            return True, "200", "boring"

What we have here? Dispatcher calls our method with some arguments:

* connection: :py:class:`dict` of «state» of connection

  * client_host: :py:class:`str`
  * client_port: :py:class:`int`
  * server_host: :py:class:`str`
  * server_port: :py:class:`int`
  * command_connection: pair of streams of command connection (
    :py:class:`asyncio.StreamReader`, :py:class:`asyncio.StreamWriter`)
  * socket_timeout: :py:class:`int` or :py:class:`float`
  * path_timeout: :py:class:`int` or :py:class:`float`
  * idle_timeout: :py:class:`int` or :py:class:`float`
  * block_size: :py:class:`int`, read operations block size
  * path_io: :py:class:`aioftp.AbstractPathIO` path abstraction layer
  * loop: :py:class:`asyncio.BaseEventLoop`

  Optional (they don't exists all the time):

  * logged: :py:class:`bool`
  * current_directory: :py:class:`pathlib.Path`
  * user: :py:class:`aioftp.User`
  * rename_from: :py:class:`str`
  * abort: :py:class:`bool`
  * transfer_type: :py:class:`str`
  * passive_connection: pair of streams of passive connection (
    :py:class:`asyncio.StreamReader`, :py:class:`asyncio.StreamWriter`)
  * passive_server: :py:class:`asyncio.Server`

  You can add your own flags and values to the «connection» and edit the
  existing ones of course.

* rest: :py:class:`str` rest part of command string

There is also a good decorator for unpacking «connection» values
:py:class:`aioftp.unpack_keywords`.

As major count of commands goes with path as «rest» you definitely should take
a look at :py:class:`aioftp.PathConditions` and
:py:class:`aioftp.PathPermissions`.

And the last one: :py:class:`aioftp.ConnectionConditions` — some basic checks
for login, passive connected, etc.

For more complex example lets try to realize same client «COLL x» command.

::

    import asyncio
    import contextlib

    import aioftp


    class MyServer(aioftp.Server):

        @aioftp.ConnectionConditions(
            aioftp.ConnectionConditions.login_required,
            aioftp.ConnectionConditions.passive_server_started,
            aioftp.ConnectionConditions.passive_connection_made)
        @aioftp.unpack_keywords
        @asyncio.coroutine
        def coll(self, connection, count, *, socket_timeout, loop):

            def coll_worker():

                data_reader, data_writer = connection.pop("passive_connection")
                with contextlib.closing(data_writer) as data_writer:

                    c = int(count)
                    data = bytes(range(256)) * (8192 // 256)
                    for x in range(0, c, 8192):

                        data_writer.write(data[:min(8192, c - x)])
                        yield from asyncio.wait_for(
                            data_writer.drain(),
                            socket_timeout,
                            loop=loop,
                        )

                reader, writer = connection["command_connection"]
                code, info = "200", "data transfer done"
                yield from self.write_response(
                    reader,
                    writer,
                    code,
                    info,
                    loop=loop,
                    socket_timeout=socket_timeout,
                )

            # asyncio.ensure_future since 3.5
            asyncio.async(coll_worker(), loop=loop)
            return True, "150", "list transfer started"

This action requires passive connection, that is why we use worker. We
should be able to receive commands when receiving data with extra connection,
that is why we use async worker and do not use linear flow. «COLL x» sends
increasing bytes to client, this operation have no «mind» behind, but pretty
good to show mechanic of aioftp.

Lets combine two commands into one class and run our code to see some
results and logging information.

::

    import asyncio
    import contextlib

    import aioftp


    class MyServer(aioftp.Server):

        @aioftp.ConnectionConditions(
            aioftp.ConnectionConditions.login_required,
            aioftp.ConnectionConditions.passive_server_started,
            aioftp.ConnectionConditions.passive_connection_made)
        @aioftp.unpack_keywords
        @asyncio.coroutine
        def coll(self, connection, count, *, socket_timeout, loop):

            def coll_worker():

                data_reader, data_writer = connection.pop("passive_connection")
                with contextlib.closing(data_writer) as data_writer:

                    c = int(count)
                    data = bytes(range(256)) * (8192 // 256)
                    for x in range(0, c, 8192):

                        data_writer.write(data[:min(8192, c - x)])
                        yield from asyncio.wait_for(
                            data_writer.drain(),
                            socket_timeout,
                            loop=loop,
                        )

                reader, writer = connection["command_connection"]
                code, info = "200", "data transfer done"
                yield from self.write_response(
                    reader,
                    writer,
                    code,
                    info,
                    loop=loop,
                    socket_timeout=socket_timeout,
                )

            # asyncio.ensure_future since 3.5
            asyncio.async(coll_worker(), loop=loop)
            return True, "150", "list transfer started"

        @asyncio.coroutine
        def noop(self, connection, rest):

            return True, "200", "boring"


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def collect(self, count):

            def callback(data):

                for x in data:

                    if x % 2 == 0:

                        collected.append(x)

            collected = []
            yield from self.retrieve(
                "COLL " + str(count),
                "1xx",
                callback=callback,
            )
            return collected

        @asyncio.coroutine
        def noop(self):

            yield from self.command("NOOP", "2xx")


    if __name__ == "__main__":

        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="[%H:%M:%S]:",
        )

        @asyncio.coroutine
        def worker(client):

            yield from client.connect("127.0.0.1", 8021)
            yield from client.login()
            yield from client.noop()
            r = yield from client.collect(100)
            print("Worker receive:", r)
            yield from client.quit()

        loop = asyncio.get_event_loop()
        client = MyClient()
        server = MyServer()
        loop.run_until_complete(server.start(None, 8021))
        # asyncio.ensure_future since 3.5
        asyncio.async(worker(client))
        try:

            loop.run_forever()

        except KeyboardInterrupt:

            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

        print("done")


And the output for this is:

::

    [10:26:58]: aioftp server: serving on 0.0.0.0:8021
    [10:26:58]: aioftp server: new connection from 127.0.0.1:59490
    [10:26:58]: aioftp server: 220 welcome
    [10:26:58]: aioftp client: 220 welcome
    [10:26:58]: aioftp client: USER anonymous
    [10:26:58]: aioftp server: USER anonymous
    [10:26:58]: aioftp server: 230 anonymous login
    [10:26:58]: aioftp client: 230 anonymous login
    [10:26:58]: aioftp client: NOOP
    [10:26:58]: aioftp server: NOOP
    [10:26:58]: aioftp server: 200 boring
    [10:26:58]: aioftp client: 200 boring
    [10:26:58]: aioftp client: TYPE I
    [10:26:58]: aioftp server: TYPE I
    [10:26:58]: aioftp server: 200
    [10:26:58]: aioftp client: 200
    [10:26:58]: aioftp client: PASV
    [10:26:58]: aioftp server: PASV
    [10:26:58]: aioftp server: 227-listen socket created
    [10:26:58]: aioftp server: 227 (0,0,0,0,232,40)
    [10:26:58]: aioftp client: 227-listen socket created
    [10:26:58]: aioftp client: 227 (0,0,0,0,232,40)
    [10:26:58]: aioftp client: COLL 100
    [10:26:58]: aioftp server: COLL 100
    [10:26:58]: aioftp server: 150 list transfer started
    [10:26:58]: aioftp server: 200 data transfer done
    [10:26:58]: aioftp client: 150 list transfer started
    [10:26:58]: aioftp client: 200 data transfer done
    Worker receive: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98]
    [10:26:58]: aioftp client: QUIT
    [10:26:58]: aioftp server: QUIT
    [10:26:58]: aioftp server: 221 bye
    [10:26:58]: aioftp server: closing connection from 127.0.0.1:59490
    [10:26:58]: aioftp client: 221 bye

Now lets try to modify the client part and add a callback from user space.
And also add the abort after some data received. Since this we should modify
and server part too, for checking the abort requested.

::

    import asyncio
    import contextlib

    import aioftp


    class MyServer(aioftp.Server):

        @aioftp.ConnectionConditions(
            aioftp.ConnectionConditions.login_required,
            aioftp.ConnectionConditions.passive_server_started,
            aioftp.ConnectionConditions.passive_connection_made)
        @aioftp.unpack_keywords
        @asyncio.coroutine
        def coll(self, connection, count, *, socket_timeout, loop):

            def coll_worker():

                data_reader, data_writer = connection.pop("passive_connection")
                with contextlib.closing(data_writer) as data_writer:

                    c = int(count)
                    data = bytes(range(256)) * (8192 // 256)
                    info = "data transfer done"
                    for x in range(0, c, 8192):

                        if connection.get("abort", False):

                            connection["abort"] = False
                            info = "data transfer aborted"
                            break

                        data_writer.write(data[:min(8192, c - x)])
                        yield from asyncio.wait_for(
                            data_writer.drain(),
                            socket_timeout,
                            loop=loop,
                        )

                reader, writer = connection["command_connection"]
                code = "200"
                yield from self.write_response(
                    reader,
                    writer,
                    code,
                    info,
                    loop=loop,
                    socket_timeout=socket_timeout,
                )

            # asyncio.ensure_future since 3.5
            asyncio.async(coll_worker(), loop=loop)
            return True, "150", "list transfer started"

        @asyncio.coroutine
        def noop(self, connection, rest):

            return True, "200", "boring"


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def collect(self, count, *, callback=None):

            def _callback(data):

                for x in data:

                    if x % 2 == 0:

                        collected.append(x)

            collected = []
            yield from self.retrieve(
                "COLL " + str(count),
                "1xx",
                callback=callback or _callback,
            )
            return collected

        @asyncio.coroutine
        def noop(self):

            yield from self.command("NOOP", "2xx")


    if __name__ == "__main__":

        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="[%H:%M:%S]:",
        )

        def AwesomeCallback():

            def callback(data):

                nonlocal abort_done
                if not abort_done:

                    for x in data:

                        print("awesome_callback receive:", x)
                        if x > 10:

                            print("awesome_callback: aborting...")
                            asyncio.async(client.abort())
                            abort_done = True
                            break

            abort_done = False
            return callback

        @asyncio.coroutine
        def worker():

            yield from client.connect("127.0.0.1", 8021)
            yield from client.login()
            yield from client.noop()
            r = yield from client.collect(10 ** 10, callback=AwesomeCallback())
            print("Worker receive:", r)
            yield from client.quit()

        loop = asyncio.get_event_loop()
        client = MyClient()
        server = MyServer()
        loop.run_until_complete(server.start(None, 8021))
        # asyncio.ensure_future since 3.5
        asyncio.async(worker())
        try:

            loop.run_forever()

        except KeyboardInterrupt:

            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

        print("done")

And the output for this is:

::

    [11:17:03]: aioftp server: serving on 0.0.0.0:8021
    [11:17:03]: aioftp server: new connection from 127.0.0.1:59641
    [11:17:03]: aioftp server: 220 welcome
    [11:17:03]: aioftp client: 220 welcome
    [11:17:03]: aioftp client: USER anonymous
    [11:17:03]: aioftp server: USER anonymous
    [11:17:03]: aioftp server: 230 anonymous login
    [11:17:03]: aioftp client: 230 anonymous login
    [11:17:03]: aioftp client: NOOP
    [11:17:03]: aioftp server: NOOP
    [11:17:03]: aioftp server: 200 boring
    [11:17:03]: aioftp client: 200 boring
    [11:17:03]: aioftp client: TYPE I
    [11:17:03]: aioftp server: TYPE I
    [11:17:03]: aioftp server: 200
    [11:17:03]: aioftp client: 200
    [11:17:03]: aioftp client: PASV
    [11:17:03]: aioftp server: PASV
    [11:17:03]: aioftp server: 227-listen socket created
    [11:17:03]: aioftp server: 227 (0,0,0,0,145,232)
    [11:17:03]: aioftp client: 227-listen socket created
    [11:17:03]: aioftp client: 227 (0,0,0,0,145,232)
    [11:17:03]: aioftp client: COLL 10000000000
    [11:17:03]: aioftp server: COLL 10000000000
    [11:17:03]: aioftp server: 150 list transfer started
    [11:17:03]: aioftp client: 150 list transfer started
    awesome_callback receive: 0
    awesome_callback receive: 1
    awesome_callback receive: 2
    awesome_callback receive: 3
    awesome_callback receive: 4
    awesome_callback receive: 5
    awesome_callback receive: 6
    awesome_callback receive: 7
    awesome_callback receive: 8
    awesome_callback receive: 9
    awesome_callback receive: 10
    awesome_callback receive: 11
    awesome_callback: aborting...
    [11:17:03]: aioftp client: ABOR
    [11:17:03]: aioftp server: ABOR
    [11:17:03]: aioftp server: 150 abort requested
    [11:17:03]: aioftp server: 200 data transfer aborted
    [11:17:03]: aioftp client: 150 abort requested
    [11:17:03]: aioftp client: 200 data transfer aborted
    Worker receive: []
    [11:17:03]: aioftp client: QUIT
    [11:17:03]: aioftp server: QUIT
    [11:17:03]: aioftp server: 221 bye
    [11:17:03]: aioftp server: closing connection from 127.0.0.1:59641
    [11:17:03]: aioftp client: 221 bye

And that is all for server. It is a good idea you to see source code of
:py:class:`aioftp.Server` in server.py to see when and why this or that
techniques used.

Path abstraction layer
----------------------

Since file io is blocking and aioftp tries to be non-blocking ftp library, we
need some abstraction layer for filesystem operations. That is why pathio
exists. If you want to create your own pathio, then you should inherit
:py:class:`aioftp.AbstractPathIO` and override it methods.
