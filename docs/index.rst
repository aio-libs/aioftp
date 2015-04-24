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

Dependencies
------------

- Python 3.3
- asyncio
- pathlib

or

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

            if info["type"] == "file" and str.endswith(path.name, ".mp3"):

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

    Coming soon

Futher reading
--------------

.. toctree::
    :maxdepth: 2

    client_tutorial
    server_tutorial
    client_api
    server_api

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`
