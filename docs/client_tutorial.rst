.. client_tutorial:

Client tutorial
===============

In 95% cases it is enough to use a little more than 10 client coroutines. So,
lets start!

Connecting to server
--------------------

Firstly you should create :class:`aioftp.Client` instance and connect to host::

    >>> ftp = aioftp.Client()
    >>> yield from ftp.connect("ftp.server.com")
    >>> yield from ftp.login("user", "pass")

Listing files
-------------

For listing files you should use :py:meth:`aioftp.Client.list` method, which
can list paths recursively and produce a list, or deal with callback::

    >>> yield from ftp.list("/")
    [(PosixPath('/.logs'), {'unix.mode': '0755', 'unique': '801g4804045', 'unix.gid': '954669020', 'type': 'dir', 'sizd': '4096', 'unix.uid': '954669020', 'modify': '20150314131116'}), (PosixPath('/DO_NOT_UPLOAD_HERE'), {'unix.mode': '0644', 'unique': '801g4800d43', 'unix.gid': '954669020', 'size': '0', 'type': 'file', 'unix.uid': '954669020', 'modify': '20140529110939'}), (PosixPath('/public_html'), {'unix.mode': '0755', 'unique': '801g4804044', 'unix.gid': '954669020', 'type': 'dir', 'sizd': '20480', 'unix.uid': '954669020', 'modify': '20150417122614'})]
    >>> yield from ftp.list("/", callback=print)
    /.logs {'sizd': '4096', 'modify': '20150314131116', 'unix.uid': '954669020', 'type': 'dir', 'unique': '801g4804045', 'unix.mode': '0755', 'unix.gid': '954669020'}
    /DO_NOT_UPLOAD_HERE {'modify': '20140529110939', 'size': '0', 'unix.uid': '954669020', 'type': 'file', 'unique': '801g4800d43', 'unix.mode': '0644', 'unix.gid': '954669020'}
    /public_html {'sizd': '20480', 'modify': '20150417122614', 'unix.uid': '954669020', 'type': 'dir', 'unique': '801g4804044', 'unix.mode': '0755', 'unix.gid': '954669020'}
    >>> yield from ftp.list("/", recursive=True, callback=print)
    /.logs {'type': 'dir', 'unix.gid': '954669020', 'unix.uid': '954669020', 'modify': '20150314131116', 'unix.mode': '0755', 'unique': '801g4804045', 'sizd': '4096'}
    /DO_NOT_UPLOAD_HERE {'type': 'file', 'size': '0', 'unix.uid': '954669020', 'modify': '20140529110939', 'unix.mode': '0644', 'unique': '801g4800d43', 'unix.gid': '954669020'}
    /public_html {'type': 'dir', 'unix.gid': '954669020', 'unix.uid': '954669020', 'modify': '20150422182535', 'unix.mode': '0755', 'unique': '801g4804044', 'sizd': '20480'}
    /public_html/test.py {'type': 'file', 'size': '2922', 'unix.uid': '954669020', 'modify': '20150422183609', 'unix.mode': '0644', 'unique': '801g480a508', 'unix.gid': '954669020'}

Callback variant is more «async» and lazy, anyway if you don't care, then
non-callback method looks much simpler.

You can pass path to file as well::

    >>> yield from c.list("/public_html/test.py", recursive=True, callback=print)
    /public_html/test.py {'unix.gid': '954669020', 'modify': '20150422184005', 'size': '3000', 'unique': '801g480a508', 'type': 'file', 'unix.mode': '0644', 'unix.uid': '954669020'}

But it is overkill, cause this (MLSD ftp command) create extra connection to
server. You should use :py:meth:`aioftp.Client.stat` instead (cause it
use MLST)::

    >>> yield from c.stat("/public_html/test.py")
    {'unix.uid': '954669020', 'type': 'file', 'modify': '20150422184255', 'size': '3102', 'unique': '801g480a508', 'unix.mode': '0644', 'unix.gid': '954669020'}
    >>> yield from c.stat("/public_html")
    {'unix.uid': '954669020', 'type': 'dir', 'modify': '20150422182535', 'unique': '801g4804044', 'unix.mode': '0755', 'unix.gid': '954669020', 'sizd': '20480'}
