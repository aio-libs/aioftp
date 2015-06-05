.. server_tutorial:

Server tutorial
===============

Configuring server
------------------

Firstly you should create :class:`aioftp.Server` instance and start it

:py:meth:`aioftp.Server.start`

::

    >>> ftp = aioftp.Server()
    >>> yield from ftp.start()

Default arguments allow anonymous login and read/write current directory. So,
there is one user with anonymous login and read/write permissions on "/"
virtual path. Real path is current working directory.

Dealing with users and permissions
----------------------------------

You can specify as much users as you want, just pass list of them when creating
:class:`aioftp.Server` instance

:class:`aioftp.User`

:class:`aioftp.Permission`

::

    >>> users = (
    ...     aioftp.User(
    ...         "Guido",
    ...         "secret_password",
    ...         home_path="/Guido",
    ...         permissions=(
    ...             aioftp.Permission("/", readable=False, writable=False),
    ...             aioftp.Permission("/Guido", readable=True, writable=True),
    ...         )
    ...     ),
    ...     aioftp.User(
    ...         home_path="/anon",
    ...         permissions=(
    ...             aioftp.Permission("/", readable=False, writable=False),
    ...             aioftp.Permission("/anon", readable=True),
    ...         )
    ...     ),
    ... )
    >>> ftp = aioftp.Server(users)
    >>> yield from ftp.start()

This will create two users: "Guido", who can read and write to "/Guido" folder,
which is home folder, but can't read/write the root and other directories and
anonymous user, who home directory is "/anon" and there is only read
permission.

Path abstraction layer
----------------------

Server provides abstraction of file system operations. You can use on of
existence:

* :py:class:`aioftp.PathIO` — blocking path operations
* :py:class:`aioftp.AsyncPathIO` — non-blocking path operations, this one is
  blocking ones just wrapped with
  :py:meth:`asyncio.BaseEventLoop.run_in_executor`
* :py:class:`aioftp.MemoryPathIO` — in-memory realization of file system, this
  one is just proof of concept and probably not too fast (as it can be).

You can specify `path_io_factory` when creating :py:class:`aioftp.Server`
instance. Default factory is :py:class:`aioftp.AsyncPathIO`.

::

    >>> ftp = aioftp.Server(path_io_factory=aioftp.MemoryPathIO)
    >>> yield from ftp.start()

Dealing with timeouts
---------------------

There is three different timeouts you can specify:

* `socket_timeout` — timeout for low-level socket operations
  :py:meth:`asyncio.StreamReader.read`,
  :py:meth:`asyncio.StreamReader.readline` and
  :py:meth:`asyncio.StreamWriter.drain`. This one does not affects awaiting
  command read operation.
* `path_timeout` — timeout for file system operations
* `idle_timeout` — timeout for socket read operation when awaiting command,
  another words: how long user can keep silence without sending commands

Default values for timeouts is :py:class:`None`

Stopping the server
-------------------

When you request to stop server all listen and active connections will be
closed. But this one doesn't stop the server immediately, if you want to wait
for server to stop use :py:meth:`aioftp.Server.wait_closed`

::

    >>> ftp.close()
    >>> yield from ftp.wait_closed()
