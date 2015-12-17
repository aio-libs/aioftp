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
