.. aioftp documentation master file, created by
   sphinx-quickstart on Fri Apr 17 16:21:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

aioftp
======

.. image:: https://github.com/aio-libs/aioftp/actions/workflows/ci.yml/badge.svg?branch=master
   :target: https://github.com/aio-libs/aioftp/actions/workflows/ci.yml
   :alt: Github actions ci for master branch

.. image:: https://codecov.io/gh/aio-libs/aioftp/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/aio-libs/aioftp

.. image:: https://img.shields.io/pypi/v/aioftp.svg
    :target: https://pypi.python.org/pypi/aioftp

.. image:: https://img.shields.io/pypi/pyversions/aioftp.svg
    :target: https://pypi.python.org/pypi/aioftp

.. image:: https://pepy.tech/badge/aioftp/month
    :target: https://pypi.python.org/pypi/aioftp

ftp client/server for asyncio (http://aioftp.readthedocs.org)

.. _GitHub: https://github.com/aio-libs/aioftp

Features
--------

- Simple.
- Extensible.
- Client socks proxy via `siosocks <https://github.com/pohmelie/siosocks>`_
  (`pip install aioftp[socks]`).

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

- Python 3.7+

0.13.0 is the last version which supports python 3.5.3+

0.16.1 is the last version which supports python 3.6+

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
        async with aioftp.Client.context(host, port, login, password) as client:
            for path, info in (await client.list(recursive=True)):
                if info["type"] == "file" and path.suffix == ".mp3":
                    await client.download(path)


    async def main():
        tasks = [
            asyncio.create_task(get_mp3("server1.com", 21, "login", "password")),
            asyncio.create_task(get_mp3("server2.com", 21, "login", "password")),
            asyncio.create_task(get_mp3("server3.com", 21, "login", "password")),
        ]
        await asyncio.wait(tasks)

    asyncio.run(main())

Server example

.. code-block:: python

    import asyncio
    import aioftp


    async def main():
        server = aioftp.Server([user], path_io_factory=path_io_factory)
        await server.run()

    asyncio.run(main())

Or just use simple server

.. code-block:: shell

    python -m aioftp --help
