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
    >>> yield from client.connect("ftp.server.com")
    >>> yield from client.login("user", "pass")

Download and upload paths
-------------------------

:py:meth:`aioftp.Client.upload` and :py:meth:`aioftp.Client.download`
coroutines are pretty similar, except data flow direction. You can
upload/download file or directory. There is "source" and "destination". When
you does not specify "destination", then current working directory will be
used as destination.

Lets upload some file to current directory
::

    >>> yield from client.upload("test.py")

If you want specify new name, or different path to uploading/downloading path
you should use "write_into" argument, which works for directory as well
::

    >>> yield from client.upload("test.py", "tmp/test.py", write_into=True)
    >>> yield from client.upload("folder1", "folder2", write_into=True)

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

    >>> yield from client.download("tmp/test.py", "foo.py", write_into=True)
    >>> yield from client.download("folder2")

Listing paths
-------------

For listing paths you should use :py:meth:`aioftp.Client.list` coroutine, which
can list paths recursively and produce a :py:class:`list`

::

    >>> yield from client.list("/")
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', ...

::

    >>> yield from client.list("/", recursive=True)
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', ...

If you ommit path argument, result will be list for current working directory

::

    >>> yield from c.list()
    [(PosixPath('test.py'), {'unique': '801g480a508', 'size': '3102', ...

Getting path stats
------------------

When you need get some path stats you should use :py:meth:`aioftp.Client.stat`

::

    >>> yield from client.stat("tmp2.py")
    {'size': '909', 'create': '1445437246.4320722', 'type': 'file', ...
    >>> yield from client.stat(".git")
    {'create': '1445435702.6441028', 'type': 'dir', 'size': '4096', ...

If you need just to check path for is it file, directory or exists you can use

    :py:meth:`aioftp.Client.is_file`

    :py:meth:`aioftp.Client.is_dir`

    :py:meth:`aioftp.Client.exists`

::

    >>> yield from client.if_file("/public_html")
    False
    >>> yield from client.is_dir("/public_html")
    True
    >>> yield from client.is_file("test.py")
    True
    >>> yield from client.exists("test.py")
    True
    >>> yield from client.exists("naked-guido.png")
    False

Remove path
-----------

For removing paths you have universal coroutine :py:meth:`aioftp.Client.remove`
which can remove file or directory recursive. So, you don't need to do borring
checks.

::

    >>> yield from client.remove("tmp.py")
    >>> yield from client.remove("folder1")

Dealing with directories
------------------------

Directories coroutines are pretty simple.

:py:meth:`aioftp.Client.get_current_directory`

:py:meth:`aioftp.Client.change_directory`

:py:meth:`aioftp.Client.make_directory`

::

    >>> yield from client.get_current_directory()
    PosixPath('/public_html')
    >>> yield from client.change_directory("folder1")
    >>> yield from client.get_current_directory()
    PosixPath('/public_html/folder1')
    >>> yield from client.change_directory()
    >>> yield from client.get_current_directory()
    PosixPath('/public_html')
    >>> yield from client.make_directory("folder2")
    >>> yield from client.change_directory("folder2")
    >>> yield from client.get_current_directory()
    PosixPath('/public_html/folder2')

Rename (move) path
------------------

To change name (move) file or directory use :py:meth:`aioftp.Client.rename`.

::

    >>> yield from client.list()
    [(PosixPath('test.py'), {'modify': '20150423090041', 'type': 'file', ...
    >>> yield from client.rename("test.py", "foo.py")
    >>> yield from client.list()
    [(PosixPath('foo.py'), {'modify': '20150423090041', 'type': 'file', ...

Closing connection
------------------

:py:meth:`aioftp.Client.quit` coroutine will send "QUIT" ftp command and close
connection.

::

    >>> yield from client.quit()

Advanced download and upload, abort
-----------------------------------

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

    stream = yield from client.download_stream("tmp.py")
    while True:

        block = yield from stream.read(8192)
        if not block:

            yield from stream.finish()
            break

        # do something with data
        if something_not_interesting:

            yield from client.abort()
            stream.close()
            break

It is important not to `finish` stream after abort, cause there is no «return»
from worker.

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

aioftp provides abstraction of file system operations. You can use on of
existence:

* :py:class:`aioftp.PathIO` — blocking path operations
* :py:class:`aioftp.AsyncPathIO` — non-blocking path operations, this one is
  blocking ones just wrapped with
  :py:meth:`asyncio.BaseEventLoop.run_in_executor`
* :py:class:`aioftp.MemoryPathIO` — in-memory realization of file system, this
  one is just proof of concept and probably not too fast (as it can be).

You can specify `path_io_factory` when creating :py:class:`aioftp.Client`
instance. Default factory is :py:class:`aioftp.AsyncPathIO`.

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
        path_timeout=1,
        path_io_factory=pathio.AsyncPathIO
    )

Using proxy
-----------

Simplest way to use proxy is
`twunnel3 <https://github.com/jvansteirteghem/twunnel3>`_. aioftp was designed
with this library in mind.

::

    configuration = {
        "PROXY_SERVERS": [
            {
                "TYPE": "SOCKS4",
                "ADDRESS": "127.0.0.1",
                "PORT": 9050,
                "ACCOUNT": {
                    "NAME": ""
                }
            },
        ]
    }
    tunnel = twunnel3.proxy_server.create_tunnel(configuration)
    client = aioftp.Client(create_connection=tunnel.create_connection)

Futher reading
--------------
:doc:`client_api`
