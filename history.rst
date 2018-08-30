0.11.1 (30-08-2018)
------------------

- server: fix memory pathio is not shared between connections
- client: add argument to `list` to allow manually specifying raw command (#78)
Thanks to `thirtyseven <https://github.com/thirtyseven>`_


0.11.0 (04-07-2018)
------------------

- client: fix parsing `ls` modify time (#60)
- all: add python3.7 support (`__aiter__` must be regular function since now) (#76, #77)
Thanks to `saulcruz <https://github.com/saulcruz>`_,
    `NickG123 <https://github.com/NickG123>`_,
    `rsichny <https://github.com/rsichny>`_,
    `Modelmat <https://github.com/Modelmat>`_,
    `webknjaz <https://github.com/webknjaz>`_

0.10.1 (01-03-2018)
-------------------

- client: more flexible `EPSV` response parsing
Thanks to `p4l1ly <https://github.com/p4l1ly>`_

0.10.0 (03-02-2018)
-------------------

- server: fix ipv6 peername unpack
- server: `connection` object is accessible from path-io layer since now
- main: add command line argument to set version of IP protocol
- setup: fix failed test session return zero exit code
- client: fix `download`-`mkdir` (issue #68)
- client/server: add initial ipv6 support (issue #63)
- client: change `PASV` to `EPSV` with fallback to `PASV`
Thanks to `jacobtomlinson <https://github.com/jacobtomlinson>`_ and
    `mbkr1992 <https://github.com/mbkr1992>`_

0.9.0 (04-01-2018)
------------------

- server: fix server address in passive mode
- server: do not reraise dispatcher exceptions
- server: remove `wait_closed`, `close` is coroutine since now
Thanks to `yieyu <https://github.com/yieyu>`_ and
    `jkr78 <https://github.com/jkr78>`_

0.8.1 (08-10-2017)
------------------

- client: ignore LIST lines, which can't be parsed
Thanks to `bachya <https://github.com/bachya>`_

0.8.0 (06-08-2017)
------------------

- client/server: add explicit encoding
Thanks to `anan-lee <https://github.com/anan-lee>`_

0.7.0 (17-04-2017)
------------------

- client: add base `LIST` parsing
- client: add `client.list` fallback on `MLSD` «not implemented» status code to `LIST`
- client: add `client.stat` fallback on `MLST` «not implemented» status code to `LIST`
- common: add `setlocale` context manager for `LIST` parsing, formatting and thread-safe usage of locale
- server: add `LIST` support for non-english locales
- server: fix `PASV` sequencies before data transfer (latest `PASV` win)
Thanks to `jw4js <https://github.com/jw4js>`_ and
    `rsichny <https://github.com/rsichny>`_

0.6.3 (02-03-2017)
------------------

- `stream.read` will read whole data by default (as `asyncio.StreamReader.read`)
Thanks to `sametmax <https://github.com/sametmax>`_

0.6.2 (27-02-2017)
------------------

- replace `docopt` with `argparse`
- add `syst` server command
- improve client `list` documentation
Thanks to `thelostt <https://github.com/thelostt>`_ and
`yieyu <https://github.com/yieyu>`_

0.6.1 (16-04-2016)
------------------

- fix documentation main page client example

0.6.0 (16-04-2016)
------------------

- fix `modifed time` field for `list` command result
- add `ClientSession` context
- add `REST` command to server and client
Thanks to `rsichny <https://github.com/rsichny>`_

0.5.0 (12-02-2016)
------------------

- change development status to production/stable
- add configuration to restrict port range for passive server
- build LIST string with stat.filemode
Thanks to `rsichny <https://github.com/rsichny>`_

0.4.1 (21-12-2015)
------------------

- improved performance on non-throttled streams
- default path io layer for client and server is PathIO since now
- added benchmark result

0.4.0 (17-12-2015)
------------------

- `async for` for pathio list function
- async context manager for streams and pathio files io
- python 3.5 only
- logging provided by "aioftp.client" and "aioftp.server"
- all path errors are now reraised as PathIOError
- server does not drop connection on path io errors since now, but return "451" code

0.3.1 (09-11-2015)
------------------

- fixed setup.py long-description

0.3.0 (09-11-2015)
------------------

- added handling of OSError in dispatcher
- fixed client/server close not opened file in finally
- handling PASS after login
- handling miltiply USER commands
- user manager for dealing with user accounts
- fixed client usage WindowsPath instead of PurePosixPath on windows for virtual paths
- client protected from "0.0.0.0" ip address in PASV
- client use pathio
- throttle deal with multiply connections
- fixed throttle bug when slow path io (#20)
- path io timeouts moved to pathio.py
- with_timeout decorator for methods
- StreamIO deals with timeouts
- all socket streams are ThrottleStreamIO since now
Thanks to `rsichny <https://github.com/rsichny>`_
`tier2003 <https://github.com/tier2003>`_

0.2.0 (22-09-2015)
------------------

- client throttle
- new server dispatcher (can wait for connections)
- maximum connections per user/server
- new client stream api
- end of line character "\r\n" everywhere
- setup.py support
- tests via "python setup.py test"
- "sh" module removed from test requirements
Thanks to `rsichny <https://github.com/rsichny>`_ and
`jettify <https://github.com/jettify>`_

0.1.7 (03-09-2015)
------------------

- bugfix on windows (can't make passive connection to 0.0.0.0:port)
- default host is "127.0.0.1" since now
- silently ignoring ipv6 sockets in server binding list

0.1.6 (03-09-2015)
------------------

- bugfix on windows (ipv6 address come first in list of binded sockets)

0.1.5 (01-09-2015)
------------------

- bugfix server on windows (PurePosixPath for virtual path)

0.1.4 (31-08-2015)
------------------

- close data connection after client disconnects
Thanks to `rsichny <https://github.com/rsichny>`_

0.1.3 (28-08-2015)
------------------

- pep8 "Method definitions inside a class are surrounded by a single blank line"
- MemoryPathIO.Stats should include st_mode
Thanks to `rsichny <https://github.com/rsichny>`_

0.1.2 (11-06-2015)
------------------

- aioftp now executes like script ("python -m aioftp")

0.1.1 (10-06-2015)
------------------

- typos in server strings
- docstrings for path abstraction layer

0.1.0 (05-06-2015)
------------------

- server functionality
- path abstraction layer

0.0.1 (24-04-2015)
------------------

- first release (client only)
