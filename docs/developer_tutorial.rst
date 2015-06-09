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

    import aioftp
    import asyncio


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def noop(self):

            yield from self.command("NOOP", "2xx")

Lets take a look to a more complex example. Say, we want to collect some data
via extra connection. For this one you need one of «extra connection» methods:
:py:meth:`aioftp.Client.store` and :py:meth:`aioftp.Client.retrieve`.
Here we implements some «COLL» command. I don't know what it does, but it sends
some data via extra connection.

::

    import aioftp
    import asyncio


    class MyClient(aioftp.Client):

        @asyncio.coroutine
        def collect(self, source):

            def callback(data):

                for x in data:

                    if x % 2 == 0:

                        collected.append(x)

            collected = []
            yield from self.retrieve(
                "COLL " + str(source),
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

    import aioftp
    import asyncio


    class MyClient(aioftp.Server):

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

  You can add your own flags and value to the «connection» and edit the
  existing ones of course.

* rest: :py:class:`str` rest part of command string

There is also a good decorator for unpacking «connection» values
:py:class:`aioftp.unpack_keywords`.

As major count of commands goes with path as «rest» you definitely should take
a look at :py:class:`aioftp.PathConditions` and
:py:class:`aioftp.PathPermissions`.

And the last one: :py:class:`aioftp.ConnectionConditions` — some basic checks
for logging, passive connected, etc.
