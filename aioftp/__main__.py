"""Simple aioftp-based server with one user (anonymous or not).

Usage: aioftp [(<login> <password>)] [options]

Options:
    -q, --quiet             set logging level to "ERROR" instead of "INFO"
    --host=host             host for binding [default: 127.0.0.1]
    --port=port             port for binding [default: 8021]
    --memory                use memory storage
"""
import asyncio
import logging

import docopt

import aioftp


args = docopt.docopt(__doc__, version=aioftp.__version__)
print(str.format("aioftp v{}", aioftp.__version__))

if not args["--quiet"]:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="[%H:%M:%S]:",
    )

if args["--memory"]:

    user = aioftp.User(args["<login>"], args["<password>"], base_path="/")
    path_io_factory = aioftp.MemoryPathIO

else:

    user = aioftp.User(args["<login>"], args["<password>"])
    path_io_factory = aioftp.PathIO

server = aioftp.Server([user], path_io_factory=path_io_factory)

loop = asyncio.get_event_loop()
loop.run_until_complete(server.start(args["--host"], int(args["--port"])))
try:

    loop.run_forever()

except KeyboardInterrupt:

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
