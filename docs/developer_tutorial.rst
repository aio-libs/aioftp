.. developer_tutorial:

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

    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def noop(self):

            yield from self.command("NOOP", "2xx")

Lets take a look to a more complex example. Say, we want to collect some data
via extra connection. For this one you need one of «extra connection» methods:
:py:meth:`aioftp.Client.download_stream`,
:py:meth:`aioftp.Client.upload_stream`, :py:meth:`aioftp.Client.append_stream`
or (for more complex situations) :py:meth:`aioftp.Client.get_stream`
Here we implements some «COLL x» command. I don't know why, but it
retrieve some data via extra connection. And the size of data is equal to «x».

::

    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def collect(self, count):

            stream = yield from self.get_stream("COLL " + str(count), "1xx")
            collected = []
            while True:

                block = yield from stream.read(8)
                if not block:

                    yield from stream.finish()
                    break

                i = int.from_bytes(block, "big")
                print("received:", block, i)
                collected.append(i)

            return collected

Client retrieve passive (or active in future versions) via `get_stream` and
read blocks of data until connection is closed. Then finishing stream and
return result. Most of client functions (except low-level from BaseClient)
are made in pretty same manner. It is a good idea you to see source code of
:py:class:`aioftp.Client` in client.py to see when and why this or that
techniques used.

Server
------

Server class based on dispatcher, which wait for result of tasks via
:py:meth:`asyncio.wait`. Tasks are different: command-reader, result-writer,
commander-action, extra-connection-workers. FTP methods dispatched by name.

Lets say we want implement «NOOP» command for server again:

::

    class MyServer(aioftp.Server):

        @asyncio.coroutine
        def noop(self, connection, rest):

            connection.response("200", "boring")
            return True

What we have here? Dispatcher calls our method with some arguments:

* `connection` is state of connection, this can hold and wait for futures.
  There many connection values you can interest in: addresses, throttles,
  timeouts, extra_workers, response, etc. You can add your own flags and values
  to the «connection» and edit the existing ones of course. It's better to see
  source code of server, cause connection is heart of dispatcher ↔ task and
  task ↔ task interaction and state container.
* `rest`: rest part of command string

There is some decorators, which can help for routine checks: is user logged,
can he read/write this path, etc.
:py:class:`aioftp.ConnectionConditions`
:py:class:`aioftp.PathConditions`
:py:class:`aioftp.PathPermissions`

For more complex example lets try same client «COLL x» command.

::

    class MyServer(aioftp.Server):

        @aioftp.ConnectionConditions(
            aioftp.ConnectionConditions.login_required,
            aioftp.ConnectionConditions.passive_server_started)
        @asyncio.coroutine
        def coll(self, connection, rest):

            @aioftp.ConnectionConditions(
                aioftp.ConnectionConditions.data_connection_made,
                wait=True,
                fail_code="425",
                fail_info="Can't open data connection")
            @aioftp.worker
            @asyncio.coroutine
            def coll_worker(self, connection, rest):

                stream = connection.data_connection
                del connection.data_connection
                try:

                    for i in range(count):

                        binary = i.to_bytes(8, "big")
                        yield from stream.write(binary)

                finally:

                    stream.close()

                connection.response("200", "coll transfer done")
                return True

            count = int(rest)
            coro = coll_worker(self, connection, rest)
            task = connection.loop.create_task(coro)
            connection.extra_workers.add(task)
            connection.response("150", "coll transfer started")
            return True

This action requires passive connection, that is why we use worker. We
should be able to receive commands when receiving data with extra connection,
that is why we send our task to dispatcher via `extra_workers`. Task will be
pending on next «iteration» of dispatcher.

Lets see what we have.

::

    @asyncio.coroutine
    def test():

        server = MyServer()
        client = MyClient()

        yield from server.start("127.0.0.1", 8021)
        yield from client.connect("127.0.0.1", 8021)
        yield from client.login()

        collected = yield from client.collect(20)
        print(collected)

        yield from client.quit()
        server.close()
        yield from server.wait_closed()


    if __name__ == "__main__":

        logging.basicConfig(level=logging.INFO)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
        print("done")


And the output for this is:

::

    INFO:aioftp:aioftp server: serving on 127.0.0.1:8021
    INFO:aioftp:aioftp server: new connection from 127.0.0.1:54476
    INFO:aioftp:aioftp server: 220 welcome
    INFO:aioftp:aioftp client: 220 welcome
    INFO:aioftp:aioftp client: USER anonymous
    INFO:aioftp:aioftp server: USER anonymous
    INFO:aioftp:aioftp server: 230 anonymous login
    INFO:aioftp:aioftp client: 230 anonymous login
    INFO:aioftp:aioftp client: TYPE I
    INFO:aioftp:aioftp server: TYPE I
    INFO:aioftp:aioftp server: 200
    INFO:aioftp:aioftp client: 200
    INFO:aioftp:aioftp client: PASV
    INFO:aioftp:aioftp server: PASV
    INFO:aioftp:aioftp server: 227-listen socket created
    INFO:aioftp:aioftp server: 227 (127,0,0,1,177,173)
    INFO:aioftp:aioftp client: 227-listen socket created
    INFO:aioftp:aioftp client: 227 (127,0,0,1,177,173)
    INFO:aioftp:aioftp client: COLL 20
    INFO:aioftp:aioftp server: COLL 20
    INFO:aioftp:aioftp server: 150 coll transfer started
    INFO:aioftp:aioftp client: 150 coll transfer started
    received: b'\x00\x00\x00\x00\x00\x00\x00\x00' 0
    received: b'\x00\x00\x00\x00\x00\x00\x00\x01' 1
    received: b'\x00\x00\x00\x00\x00\x00\x00\x02' 2
    received: b'\x00\x00\x00\x00\x00\x00\x00\x03' 3
    received: b'\x00\x00\x00\x00\x00\x00\x00\x04' 4
    received: b'\x00\x00\x00\x00\x00\x00\x00\x05' 5
    received: b'\x00\x00\x00\x00\x00\x00\x00\x06' 6
    received: b'\x00\x00\x00\x00\x00\x00\x00\x07' 7
    received: b'\x00\x00\x00\x00\x00\x00\x00\x08' 8
    received: b'\x00\x00\x00\x00\x00\x00\x00\t' 9
    received: b'\x00\x00\x00\x00\x00\x00\x00\n' 10
    received: b'\x00\x00\x00\x00\x00\x00\x00\x0b' 11
    received: b'\x00\x00\x00\x00\x00\x00\x00\x0c' 12
    received: b'\x00\x00\x00\x00\x00\x00\x00\r' 13
    received: b'\x00\x00\x00\x00\x00\x00\x00\x0e' 14
    received: b'\x00\x00\x00\x00\x00\x00\x00\x0f' 15
    received: b'\x00\x00\x00\x00\x00\x00\x00\x10' 16
    received: b'\x00\x00\x00\x00\x00\x00\x00\x11' 17
    received: b'\x00\x00\x00\x00\x00\x00\x00\x12' 18
    INFO:aioftp:aioftp server: 200 coll transfer done
    received: b'\x00\x00\x00\x00\x00\x00\x00\x13' 19
    INFO:aioftp:aioftp client: 200 coll transfer done
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    INFO:aioftp:aioftp client: QUIT
    INFO:aioftp:aioftp server: QUIT
    INFO:aioftp:aioftp server: 221 bye
    INFO:aioftp:aioftp server: closing connection from 127.0.0.1:54476
    INFO:aioftp:aioftp client: 221 bye
    done

It is a good idea you to see source code of :py:class:`aioftp.Server` in
server.py to see when and why this or that techniques used.

Path abstraction layer
----------------------

Since file io is blocking and aioftp tries to be non-blocking ftp library, we
need some abstraction layer for filesystem operations. That is why pathio
exists. If you want to create your own pathio, then you should inherit
:py:class:`aioftp.AbstractPathIO` and override it methods.

AbstractUserManager
-------------------

Soon.
