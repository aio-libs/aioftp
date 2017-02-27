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
MLST, RNFR, RNTO, DELE, STOR, APPE, RETR, TYPE, PASV, ABOR, QUIT, REST

Server support this commands: USER, PASS, QUIT, PWD, CWD, CDUP, MKD, RMD, MLSD,
LIST (but it's not recommended to use it, cause it has no standard format),
MLST, RNFR, RNTO, DELE, STOR, RETR, TYPE (only "I"), PASV, ABOR, APPE, REST

This subsets are enough for 99% of tasks, but if you need something, then you
can easily extend current set of commands.

Server benchmark
----------------

Compared with `pyftpdlib <https://github.com/giampaolo/pyftpdlib>`_ and
checked with its ftpbench script.

aioftp 0.4.1

::

    $ ./ftpbench -u anonymous -p none -P 8021 -b all
    STOR (client -> server)                              146.06 MB/sec
    RETR (server -> client)                              273.88 MB/sec
    200 concurrent clients (connect, login)                0.36 secs
    STOR (1 file with 200 idle clients)                  121.02 MB/sec
    RETR (1 file with 200 idle clients)                  274.31 MB/sec
    200 concurrent clients (RETR 10.0M file)              16.09 secs
    200 concurrent clients (STOR 10.0M file)              19.03 secs
    200 concurrent clients (QUIT)                          0.11 secs

pyftpdlib 1.5.0

::

    $ ./ftpbench -u anonymous -p none -P 8021 -b all
    STOR (client -> server)                              198.65 MB/sec
    RETR (server -> client)                             3361.68 MB/sec
    200 concurrent clients (connect, login)                0.09 secs
    STOR (1 file with 200 idle clients)                  209.34 MB/sec
    RETR (1 file with 200 idle clients)                 3367.59 MB/sec
    200 concurrent clients (RETR 10.0M file)               1.04 secs
    200 concurrent clients (STOR 10.0M file)               1.98 secs
    200 concurrent clients (QUIT)                          0.02 secs

Dependencies
------------

- Python 3.5
- docopt (for execution module as script only)

License
-------

aioftp is offered under the WTFPL license.

Library installation
--------------------

::

   pip install aioftp

Getting started
---------------

Client example

.. code-block:: python

    import asyncio
    import aioftp


    async def get_mp3(host, port, login, password):

        async with aioftp.ClientSession(host, port, login, password) as client:

            for path, info in (await client.list(recursive=True)):

                if info["type"] == "file" and path.suffix == ".mp3":

                    await client.download(path)


    loop = asyncio.get_event_loop()
    tasks = (
        get_mp3("server1.com", 21, "login", "password")),
        get_mp3("server2.com", 21, "login", "password")),
        get_mp3("server3.com", 21, "login", "password")),
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
