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
Thanks to (`rsichny <https://github.com/rsichny>`_) and
(`jettify <https://github.com/jettify>`_)

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
Thanks to (`rsichny <https://github.com/rsichny>`_)

0.1.3 (28-08-2015)
------------------

- pep8 "Method definitions inside a class are surrounded by a single blank line"
- MemoryPathIO.Stats should include st_mode
Thanks to (`rsichny <https://github.com/rsichny>`_)

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
