Client tutorial
===============

In 95% cases it is enough to use a little more than 10 client coroutines. So,
lets start!

Connecting to server
--------------------

Firstly you should create :class:`aioftp.Client` instance and connect to host

:py:meth:`aioftp.Client.connect`

:py:meth:`aioftp.Client.login`

::

    >>> client = aioftp.Client()
    >>> await client.connect("ftp.server.com")
    >>> await client.login("user", "pass")

Or just use :class:`aioftp.ClientSession` async context, which will connect,
login and quit automatically

::

    >>> async with aioftp.ClientSession("ftp.server.com", "user", "pass") as client:
    ...     # do

Download and upload paths
-------------------------

:py:meth:`aioftp.Client.upload` and :py:meth:`aioftp.Client.download`
coroutines are pretty similar, except data flow direction. You can
upload/download file or directory. There is "source" and "destination". When
you does not specify "destination", then current working directory will be
used as destination.

Lets upload some file to current directory
::

    >>> await client.upload("test.py")

If you want specify new name, or different path to uploading/downloading path
you should use "write_into" argument, which works for directory as well
::

    >>> await client.upload("test.py", "tmp/test.py", write_into=True)
    >>> await client.upload("folder1", "folder2", write_into=True)

After that you get
::

    tmp/test.py
    folder2/*content of folder1*

If you will not use "write_into", you will get something you probably did not
expect
::

    tmp/test.py/test.py
    folder2/folder1/*content of folder1*

Or you can upload path as is and then rename it
(:py:meth:`aioftp.Client.rename`)

Downloading is pretty same
::

    >>> await client.download("tmp/test.py", "foo.py", write_into=True)
    >>> await client.download("folder2")

Listing paths
-------------

For listing paths you should use :py:meth:`aioftp.Client.list` coroutine, which
can list paths recursively and produce a :py:class:`list` and can be used
with `async for`

::

    >>> await client.list("/")
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', ...

::

    >>> await client.list("/", recursive=True)
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', ...

::

    >>> async for path, info in client.list("/", recursive=True):
    ...     print(path)
    (PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', ...

If you ommit path argument, result will be list for current working directory

::

    >>> await c.list()
    [(PosixPath('test.py'), {'unique': '801g480a508', 'size': '3102', ...

In case of `async for` be careful, since asynchronous variation of list is lazy.
It means, that until you leave `async for` block you can't interact with server.
If you need list and interact with server you should use eager version of list:

::

    >>> for path, info in (await client.list()):
    ...     await client.download(path, path.name)

If you want to mix lazy `list` and client interaction, you can create two client
connections to server:

::

    >>> async for path, info in client1.list():
    ...     await client2.download(path, path.name)

Getting path stats
------------------

When you need get some path stats you should use :py:meth:`aioftp.Client.stat`

::

    >>> await client.stat("tmp2.py")
    {'size': '909', 'create': '1445437246.4320722', 'type': 'file', ...
    >>> await client.stat(".git")
    {'create': '1445435702.6441028', 'type': 'dir', 'size': '4096', ...

If you need just to check path for is it file, directory or exists you can use

    :py:meth:`aioftp.Client.is_file`

    :py:meth:`aioftp.Client.is_dir`

    :py:meth:`aioftp.Client.exists`

::

    >>> await client.is_file("/public_html")
    False
    >>> await client.is_dir("/public_html")
    True
    >>> await client.is_file("test.py")
    True
    >>> await client.exists("test.py")
    True
    >>> await client.exists("naked-guido.png")
    False

Remove path
-----------

For removing paths you have universal coroutine :py:meth:`aioftp.Client.remove`
which can remove file or directory recursive. So, you don't need to do borring
checks.

::

    >>> await client.remove("tmp.py")
    >>> await client.remove("folder1")

Dealing with directories
------------------------

Directories coroutines are pretty simple.

:py:meth:`aioftp.Client.get_current_directory`

:py:meth:`aioftp.Client.change_directory`

:py:meth:`aioftp.Client.make_directory`

::

    >>> await client.get_current_directory()
    PosixPath('/public_html')
    >>> await client.change_directory("folder1")
    >>> await client.get_current_directory()
    PosixPath('/public_html/folder1')
    >>> await client.change_directory()
    >>> await client.get_current_directory()
    PosixPath('/public_html')
    >>> await client.make_directory("folder2")
    >>> await client.change_directory("folder2")
    >>> await client.get_current_directory()
    PosixPath('/public_html/folder2')

Rename (move) path
------------------

To change name (move) file or directory use :py:meth:`aioftp.Client.rename`.

::

    >>> await client.list()
    [(PosixPath('test.py'), {'modify': '20150423090041', 'type': 'file', ...
    >>> await client.rename("test.py", "foo.py")
    >>> await client.list()
    [(PosixPath('foo.py'), {'modify': '20150423090041', 'type': 'file', ...

Closing connection
------------------

:py:meth:`aioftp.Client.quit` coroutine will send "QUIT" ftp command and close
connection.

::

    >>> await client.quit()

Advanced download and upload, abort, restart
--------------------------------------------

File read/write operations are blocking and slow. So if you want just
parse/calculate something on the fly when receiving file, or generate data
to upload it to file system on ftp server, then you should use
:py:meth:`aioftp.Client.download_stream`,
:py:meth:`aioftp.Client.upload_stream` and
:py:meth:`aioftp.Client.append_stream`. All this methods based on
:py:meth:`aioftp.Client.get_stream`, which return
:py:class:`aioftp.DataConnectionThrottleStreamIO`. The common pattern to
work with streams is:

::

    >>> async with client.download_stream("tmp.py") as stream:
    ...
    ...     async for block in stream.iter_by_block():
    ...
    ...         # do something with data

Or, if you want to abort transfer at some point

::

    >>> stream = await client.download_stream("tmp.py")
    ... async for block in stream.iter_by_block():
    ...
    ...     # do something with data
    ...
    ...     if something_not_interesting:
    ...
    ...         await client.abort()
    ...         stream.close()
    ...         break
    ...
    ... else:
    ...
    ...     await stream.finish()

For restarting upload/download at exact byte position (REST command) there is
`offset` argument for `*_stream` methods:

::

    >>> async with client.download_stream("tmp.py", offset=256) as stream:
    ...
    ...     async for block in stream.iter_by_block():
    ...
    ...         # do something with data

Or if you want to restore upload/download process:

::

    >>> while True:
    ...
    ...     try:
    ...
    ...         async with aioftp.ClientSession(HOST, PORT) as client:
    ...
    ...             if await client.exists(filename):
    ...
    ...                 stat = await client.stat(filename)
    ...                 size = int(stat["size"])
    ...
    ...             else:
    ...
    ...                 size = 0
    ...
    ...             file_in.seek(size)
    ...             async with client.upload_stream(filename, offset=size) as stream:
    ...
    ...                 while True:
    ...
    ...                     data = file_in.read(block_size)
    ...                     if not data:
    ...
    ...                         break
    ...
    ...                     await stream.write(data)
    ...
    ...         break
    ...
    ...     except ConnectionResetError:
    ...
    ...         pass

The idea is to seek position of source «file» for upload and start
upload + offset/append. Opposite situation for download («file» append and
download + offset)

Throttle
--------

Client have two types of speed limit: `read_speed_limit` and
`write_speed_limit`. Throttle can be set at initialization time:

::

    >>> client = aioftp.Client(read_speed_limit=100 * 1024)  # 100 Kib/s

And can be changed after creation:

::

    >>> client.throttle.write.limit = 250 * 1024

Path abstraction layer
----------------------

aioftp provides abstraction of file system operations. You can use exist ones:

* :py:class:`aioftp.PathIO` — blocking path operations
* :py:class:`aioftp.AsyncPathIO` — non-blocking path operations, this one is
  blocking ones just wrapped with
  :py:meth:`asyncio.BaseEventLoop.run_in_executor`. It's really slow, so it's
  better to avoid usage of this path io layer.
* :py:class:`aioftp.MemoryPathIO` — in-memory realization of file system, this
  one is just proof of concept and probably not too fast (as it can be).

You can specify `path_io_factory` when creating :py:class:`aioftp.Client`
instance. Default factory is :py:class:`aioftp.PathIO`.

::

    >>> client = aioftp.Client(path_io_factory=pathio.MemoryPathIO)

Timeouts
--------

:py:class:`aioftp.Client` have `socket_timeout` argument, which you can use
to specify global timeout for socket io operations.

::

    >>> client = aioftp.Client(socket_timeout=1)  # 1 second socket timeout

:py:class:`aioftp.Client` also have `path_timeout`, which is applied
**only for non-blocking path io layers**.

::

    >>> client = aioftp.Client(
    ...     path_timeout=1,
    ...     path_io_factory=pathio.AsyncPathIO
    ... )

Using proxy
-----------

Simplest way to use proxy is
`twunnel3 <https://github.com/jvansteirteghem/twunnel3>`_. aioftp was designed
with this library in mind.

::

    >>> configuration = {
    ...     "PROXY_SERVERS": [
    ...         {
    ...             "TYPE": "SOCKS4",
    ...             "ADDRESS": "127.0.0.1",
    ...             "PORT": 9050,
    ...             "ACCOUNT": {
    ...                 "NAME": ""
    ...             }
    ...         },
    ...     ]
    ... }
    tunnel = twunnel3.proxy_server.create_tunnel(configuration)
    client = aioftp.Client(create_connection=tunnel.create_connection)

Futher reading
--------------
:doc:`client_api`
