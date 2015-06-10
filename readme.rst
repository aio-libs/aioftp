.. aioftp documentation master file, created by
   sphinx-quickstart on Fri Apr 17 16:21:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

aioftp
======

.. image:: https://travis-ci.org/pohmelie/aioftp.svg?branch=master
    :target: https://travis-ci.org/pohmelie/aioftp

.. image:: https://coveralls.io/repos/pohmelie/aioftp/badge.svg?branch=master
    :target: https://coveralls.io/r/pohmelie/aioftp?branch=master

ftp client/server for asyncio. (http://aioftp.readthedocs.org)

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

Client use this commands: USER, PASS, ACCT, PWD, CWD, CDUP, MKD, RMD, MLSD,
MLST, RNFR, RNTO, DELE, STOR, APPE, RETR, TYPE, PASV, ABOR, QUIT

Server support this commands: USER, PASS, QUIT, PWD, CWD, CDUP, MKD, RMD, MLSD,
LIST (but it's not recommended to use it, cause it has no standard format),
MLST, RNFR, RNTO, DELE, STOR, RETR, TYPE (only "I"), PASV, ABOR, APPE

This subsets are enough for 99% of tasks, but if you need something, then you
can easily extend current set of commands.

Dependencies
------------

- Python 3.4+

License
-------

aioftp is offered under the Apache 2 license.

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


    @asyncio.coroutine
    def get_mp3(host, login, password):

        ftp = aioftp.Client()
        yield from ftp.connect(host)
        yield from ftp.login(login, password)
        for path, info in (yield from ftp.list(recursive=True)):

            if info["type"] == "file" and path.suffix == ".mp3":

                yield from ftp.download(path, path.name)


    loop = asyncio.get_event_loop()
    tasks = (
        asyncio.async(get_mp3("server1.com", "login", "password")),
        asyncio.async(get_mp3("server2.com", "login", "password")),
        asyncio.async(get_mp3("server3.com", "login", "password")),
    )
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

Server example

.. code-block:: python

    import asyncio
    import aioftp


    loop = asyncio.get_event_loop()
    ftp = aioftp.Server()
    asyncio.async(ftp.start(None, 8021), loop=loop)
    try:

        loop.run_forever()

    except KeyboardInterrupt:

        ftp.close()
        loop.run_until_complete(ftp.wait_closed())
        loop.close()
