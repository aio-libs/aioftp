.. aioftp documentation master file, created by
   sphinx-quickstart on Fri Apr 17 16:21:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

aioftp
======

ftp client/server for asyncio.

.. _GitHub: https://github.com/pohmelie/aioftp

Features
--------

- Simple.
- Extensible.
- Proxy via `twunnel3 <https://github.com/jvansteirteghem/twunnel3>`_.

Goals
-----

- Minimum usable core.
- Do not use deprecated or overridden commands and features (if possible).
- Very high level api.

Client use this commands: USER, PASS, ACCT, PWD, CWD, CDUP, MKD, RMD, MLSD,
MLST, RNFR, RNTO, DELE, STOR, APPE, RETR, TYPE, PASV, ABOR, QUIT

Server support this commands: USER, PASS, QUIT, PWD, CWD, CDUP, MKD, RMD, MLSD,
LIST (but it's not recommended to use it, cause it has no standard format),
MLST, RNFR, RNTO, DELE, STOR, RETR, TYPE (only "I"), PASV, ABOR, APPE

This subsets are enough for 99% of tasks, but if you need something, then you
can easily extend current set of commands.

Dependencies
------------

- Python 3.5
- docopt (for execution module as script only)

License
-------

aioftp is offered under the WTFPL license.

Library Installation
--------------------

::

   pip install aioftp

Getting started
---------------

Client example

.. code-block:: python

    import asyncio
    import aioftp


    async def get_mp3(host, login, password):

        client = aioftp.Client()
        await client.connect(host)
        await client.login(login, password)
        async for path, info in client.list(recursive=True):

            if info["type"] == "file" and path.suffix == ".mp3":

                await client.download(path)

        await client.quit()


    loop = asyncio.get_event_loop()
    tasks = (
        get_mp3("server1.com", "login", "password")),
        get_mp3("server2.com", "login", "password")),
        get_mp3("server3.com", "login", "password")),
    )
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

Server example

.. code-block:: python

    import asyncio
    import aioftp


    loop = asyncio.get_event_loop()
    server = aioftp.Server()
    loop.run_until_complete(server.start(None, 8021))
    try:

        loop.run_forever()

    except KeyboardInterrupt:

        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()

Or just use simple server

.. code-block:: shell

    python -m aioftp --help

Further reading
---------------

.. toctree::
    :maxdepth: 2

    client_tutorial
    server_tutorial
    developer_tutorial
    client_api
    server_api
    common_api
    path_io_api

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`
