.. aioftp documentation master file, created by
   sphinx-quickstart on Fri Apr 17 16:21:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

aioftp
======

.. image:: https://travis-ci.com/aio-libs/aioftp.svg?branch=master
   :target: https://travis-ci.com/aio-libs/aioftp
   :alt: Travis status for master branch

.. image:: https://codecov.io/gh/aio-libs/aioftp/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/aio-libs/aioftp

.. image:: https://img.shields.io/pypi/v/aioftp.svg
    :target: https://pypi.python.org/pypi/aioftp

.. image:: https://img.shields.io/pypi/pyversions/aioftp.svg
    :target: https://pypi.python.org/pypi/aioftp

.. image:: https://pypi-badges.global.ssl.fastly.net/svg?package=aioftp&timeframe=monthly
    :target: https://pypi.python.org/pypi/aioftp

ftp client/server for asyncio (http://aioftp.readthedocs.org)

.. _GitHub: https://github.com/aio-libs/aioftp

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
MLST, RNFR, RNTO, DELE, STOR, APPE, RETR, TYPE, PASV, ABOR, QUIT, REST, LIST
(as fallback)

Server support this commands: USER, PASS, QUIT, PWD, CWD, CDUP, MKD, RMD, MLSD,
LIST (but it's not recommended to use it, cause it has no standard format),
MLST, RNFR, RNTO, DELE, STOR, RETR, TYPE ("I" and "A"), PASV, ABOR, APPE, REST

This subsets are enough for 99% of tasks, but if you need something, then you
can easily extend current set of commands.

Server benchmark
----------------

Compared with `pyftpdlib <https://github.com/giampaolo/pyftpdlib>`_ and
checked with its ftpbench script.

aioftp 0.8.0

::

    STOR (client -> server)                              284.95 MB/sec
    RETR (server -> client)                              408.44 MB/sec
    200 concurrent clients (connect, login)                0.18 secs
    STOR (1 file with 200 idle clients)                  287.52 MB/sec
    RETR (1 file with 200 idle clients)                  382.05 MB/sec
    200 concurrent clients (RETR 10.0M file)              13.33 secs
    200 concurrent clients (STOR 10.0M file)              12.56 secs
    200 concurrent clients (QUIT)                          0.03 secs

pyftpdlib 1.5.2

::

    STOR (client -> server)                             1235.56 MB/sec
    RETR (server -> client)                             3960.21 MB/sec
    200 concurrent clients (connect, login)                0.06 secs
    STOR (1 file with 200 idle clients)                 1208.58 MB/sec
    RETR (1 file with 200 idle clients)                 3496.03 MB/sec
    200 concurrent clients (RETR 10.0M file)               0.55 secs
    200 concurrent clients (STOR 10.0M file)               1.46 secs
    200 concurrent clients (QUIT)                          0.02 secs

Dependencies
------------

- Python 3.5.3+

License
-------

aioftp is offered under the Apache 2 license.

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
        loop.run_until_complete(server.close())
        loop.close()

Or just use simple server

.. code-block:: shell

    python -m aioftp --help
