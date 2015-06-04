.. client_tutorial:

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

    >>> ftp = aioftp.Client()
    >>> yield from ftp.connect("ftp.server.com")
    >>> yield from ftp.login("user", "pass")

Download and upload paths
-------------------------

:py:meth:`aioftp.Client.upload` and :py:meth:`aioftp.Client.download`
coroutines are pretty similar, except data flow direction. You can
upload/download file or directory. There is "source" and "destination". When
you does not specify "destination", then current working directory will be
used as destination.

Lets upload some file to current directory
::

    >>> yield from ftp.upload("test.py")

If you want specify new name, or different path to uploading/downloading path
you should use "write_into" argument, which works for directory as well
::

    >>> yield from ftp.upload("test.py", "tmp/test.py", write_into=True)
    >>> yield from ftp.upload("folder1", "folder2", write_into=True)

After that you get
::

    tmp/test.py
    folder2/*content of folder1*

If you will not use "write_into", you will get something you probably did not
expect
::

    tmp/test.py/test.py
    folder2/folder1/*content of folder1*

Or you can download path as is and then rename it
(:py:meth:`aioftp.Client.rename`)

Downloading is pretty same
::

    >>> yield from ftp.download("tmp/test.py", "foo.py", write_into=True)
    >>> yield from ftp.download("folder2")

Also there is a "callback" parameter for upload/download, which main purpose in
this context is keep progress. And here we have some more complex example.
::

    size = 0
    for p in pathlib.Path("folder").rglob("*"):

        if p.is_file():

            size += p.stat().st_size

    def progress(data):

        nonlocal current
        current += len(data)
        print(
            str.format(
                "{:.2f}% ({} of {})",
                current * 100 / size,
                current,
                size,
            )
        )

    current = 0
    yield from ftp.upload("folder", callback=progress)

This will produce something like this
::

    5.54% (8192 of 147968)
    11.07% (16384 of 147968)
    15.92% (23552 of 147968)
    21.45% (31744 of 147968)
    26.64% (39424 of 147968)
    32.18% (47616 of 147968)
    37.72% (55808 of 147968)
    43.25% (64000 of 147968)
    44.29% (65536 of 147968)
    49.83% (73728 of 147968)
    55.36% (81920 of 147968)
    60.90% (90112 of 147968)
    66.44% (98304 of 147968)
    71.97% (106496 of 147968)
    72.66% (107520 of 147968)
    78.20% (115712 of 147968)
    83.74% (123904 of 147968)
    89.27% (132096 of 147968)
    94.81% (140288 of 147968)
    100.00% (147968 of 147968)

Listing paths
-------------

For listing paths you should use :py:meth:`aioftp.Client.list` coroutine, which
can list paths recursively and produce a :py:class:`list`, or deal with
callback

::

    >>> yield from ftp.list("/")
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', 'unix.gid': '954669020', 'type': 'dir', 'sizd': '4096', 'unix.uid': '954669020', 'modify': '20150314131116'}), (PosixPath('/DO_NOT_UPLOAD_HERE'), {'unix.mode': '0644', 'unique': '801g4800d43', 'unix.gid': '954669020', 'size': '0', 'type': 'file', 'unix.uid': '954669020', 'modify': '20140529110939'}), (PosixPath('/public_html'), {'unix.mode': '0755', 'unique': '801g4804044', 'unix.gid': '954669020', 'type': 'dir', 'sizd': '20480', 'unix.uid': '954669020', 'modify': '20150417122614'})]

::

    >>> yield from ftp.list("/", callback=print)
    /.logs {'sizd': '4096', 'modify': '20150314131116', 'unix.uid': '954669020', 'type': 'dir', 'unique': '801g4804045', 'unix.mode': '0755', 'unix.gid': '954669020'}
    /DO_NOT_UPLOAD_HERE {'modify': '20140529110939', 'size': '0', 'unix.uid': '954669020', 'type': 'file', 'unique': '801g4800d43', 'unix.mode': '0644', 'unix.gid': '954669020'}
    /public_html {'sizd': '20480', 'modify': '20150417122614', 'unix.uid': '954669020', 'type': 'dir', 'unique': '801g4804044', 'unix.mode': '0755', 'unix.gid': '954669020'}

::

    >>> yield from ftp.list("/", recursive=True, callback=print)
    /.logs {'type': 'dir', 'unix.gid': '954669020', 'unix.uid': '954669020', 'modify': '20150314131116', 'unix.mode': '0755', 'unique': '801g4804045', 'sizd': '4096'}
    /DO_NOT_UPLOAD_HERE {'type': 'file', 'size': '0', 'unix.uid': '954669020', 'modify': '20140529110939', 'unix.mode': '0644', 'unique': '801g4800d43', 'unix.gid': '954669020'}
    /public_html {'type': 'dir', 'unix.gid': '954669020', 'unix.uid': '954669020', 'modify': '20150422182535', 'unix.mode': '0755', 'unique': '801g4804044', 'sizd': '20480'}
    /public_html/test.py {'type': 'file', 'size': '2922', 'unix.uid': '954669020', 'modify': '20150422183609', 'unix.mode': '0644', 'unique': '801g480a508', 'unix.gid': '954669020'}

Callback variant is more «async», lazy and does not accumulate stats to list,
anyway if you don't care, then non-callback method looks much simpler.

If you ommit path argument, result will be list for current working directory

::

    >>> yield from c.list()
    [(PosixPath('test.py'), {'unique': '801g480a508', 'size': '3102', 'unix.gid': '954669020', 'unix.mode': '0644', 'unix.uid': '954669020', 'type': 'file', 'modify': '20150422184255'})]

You can pass path to file as well

::

    >>> yield from ftp.list("/public_html/test.py", recursive=True, callback=print)
    /public_html/test.py {'unix.gid': '954669020', 'modify': '20150422184005', 'size': '3000', 'unique': '801g480a508', 'type': 'file', 'unix.mode': '0644', 'unix.uid': '954669020'}

But it is overkill, cause this (MLSD ftp command) create extra connection to
server. You should use :py:meth:`aioftp.Client.stat` instead (cause it
use MLST and same connection). See section below.

Getting path stats
------------------

When you need get some path stats you should use :py:meth:`aioftp.Client.stat`

::

    >>> yield from ftp.stat("/public_html/test.py")
    {'unix.uid': '954669020', 'type': 'file', 'modify': '20150422184255', 'size': '3102', 'unique': '801g480a508', 'unix.mode': '0644', 'unix.gid': '954669020'}
    >>> yield from ftp.stat("/public_html")
    {'unix.uid': '954669020', 'type': 'dir', 'modify': '20150422182535', 'unique': '801g4804044', 'unix.mode': '0755', 'unix.gid': '954669020', 'sizd': '20480'}

If you need just to check path for is it file, directory or exists you can use

    :py:meth:`aioftp.Client.is_file`

    :py:meth:`aioftp.Client.is_dir`

    :py:meth:`aioftp.Client.exists`

::

    >>> yield from ftp.if_file("/public_html")
    False
    >>> yield from ftp.is_dir("/public_html")
    True
    >>> yield from ftp.is_file("test.py")
    True
    >>> yield from ftp.exists("test.py")
    True
    >>> yield from ftp.exists("naked-guido.png")
    False

Take a look on the last example. You can pass relative paths in any path
oriented methods, but in this case you should know the current working
directory.

If you need just check if path exists

Remove path
-----------

For removing paths you have universal coroutine :py:meth:`aioftp.Client.remove`
which can remove file or directory recursive. So, you don't need to do borring
checks.

::

    >>> yield from ftp.remove("tmp.py")
    >>> yield from ftp.remove("folder1")

Dealing with directories
------------------------

Directories coroutines are pretty simple.

:py:meth:`aioftp.Client.get_current_directory`

:py:meth:`aioftp.Client.change_directory`

:py:meth:`aioftp.Client.make_directory`

::

    >>> yield from ftp.get_current_directory()
    PosixPath('/public_html')
    >>> yield from ftp.change_directory("folder1")
    >>> yield from ftp.get_current_directory()
    PosixPath('/public_html/folder1')
    >>> yield from ftp.change_directory()
    >>> yield from ftp.get_current_directory()
    PosixPath('/public_html')
    >>> yield from ftp.make_directory("folder2")
    >>> yield from ftp.change_directory("folder2")
    >>> yield from ftp.get_current_directory()
    PosixPath('/public_html/folder2')

Rename (move) path
------------------

To change name (move) file or directory use :py:meth:`aioftp.Client.rename`.

::

    >>> yield from ftp.list()
    [(PosixPath('test.py'), {'modify': '20150423090041', 'type': 'file', 'size': '3164', 'unique': '801g480a594', 'unix.gid': '954669020', 'unix.uid': '954669020', 'unix.mode': '0644'})]
    >>> yield from ftp.rename("test.py", "foo.py")
    >>> yield from ftp.list()
    [(PosixPath('foo.py'), {'modify': '20150423090041', 'type': 'file', 'size': '3164', 'unique': '801g480a594', 'unix.gid': '954669020', 'unix.uid': '954669020', 'unix.mode': '0644'})]

Closing connection
------------------

:py:meth:`aioftp.Client.quit` coroutine will send "QUIT" ftp command and close
connection.

::

    >>> yield from ftp.quit()

Advanced download and upload
----------------------------

File read/write operations are blocking and slow. So if you want just
parse/calculate something on the fly when receiving file, or generate data
to upload it to file system on ftp server, then you should use
:py:meth:`aioftp.Client.download_file` and
:py:meth:`aioftp.Client.upload_file`

Download deal with callback only, and upload deal with file-like object with
read method.

::

    >>> yield from ftp.download_file("foo.py", callback=lambda d: print(len(d)))
    2720
    444
    >>> file_like = io.BytesIO(str.encode("1234567890", "utf-8"))
    >>> yield from ftp.upload_file("bar.py", file_like)
    >>> yield from ftp.stat("bar.py")
    {'size': '10', 'modify': '20150423131047', 'type': 'file', 'unix.mode': '0644', 'unique': '801g48003d7', 'unix.gid': '954669020', 'unix.uid': '954669020'}
    >>> yield from ftp.download_file("bar.py", callback=print)
    b'1234567890'

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
    ftp = aioftp.Client(tunnel.create_connection)
