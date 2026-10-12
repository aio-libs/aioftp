"""Simple aioftp-based server with one user (anonymous or not)"""

import argparse
import asyncio
import contextlib
import logging
import socket
import ssl
from typing import Any

import aioftp

parser = argparse.ArgumentParser(
    prog="aioftp",
    usage="%(prog)s [options]",
    description="Simple aioftp-based server with one user (anonymous or not).",
)
parser.add_argument(
    "--user",
    metavar="LOGIN",
    dest="login",
    help="user name to login",
)
parser.add_argument(
    "--pass",
    metavar="PASSWORD",
    dest="password",
    help="password to login",
)
parser.add_argument(
    "-d",
    metavar="DIRECTORY",
    dest="home",
    help="the directory to share (default current directory)",
)
parser.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    help="set logging level to 'ERROR' instead of 'INFO'",
)
parser.add_argument("--memory", action="store_true", help="use memory storage")
parser.add_argument(
    "--host",
    default=None,
    help="host for binding [default: %(default)s]",
)
parser.add_argument(
    "--port",
    type=int,
    default=2121,
    help="port for binding [default: %(default)s]",
)
parser.add_argument(
    "--family",
    choices=("ipv4", "ipv6", "auto"),
    default="auto",
    help="Socket family [default: %(default)s]",
)
parser.add_argument(
    "--ftps",
    choices=("off", "implicit", "explicit"),
    default="off",
    help="enable FTPS support",
)
parser.add_argument(
    "--certfile",
    metavar="PATH",
    default=None,
    help="TLS certificate file",
)
parser.add_argument(
    "--keyfile",
    metavar="PATH",
    default=None,
    help="TLS key file",
)

args = parser.parse_args()
print(f"aioftp v{aioftp.__version__}")

if not args.quiet:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="[%H:%M:%S]:",
    )
if args.memory:
    user = aioftp.User(args.login, args.password, base_path="/")
    path_io_factory: type[aioftp.AbstractPathIO[Any]] = aioftp.MemoryPathIO
else:
    if args.home:
        user = aioftp.User(args.login, args.password, base_path=args.home)
    else:
        user = aioftp.User(args.login, args.password)
    path_io_factory = aioftp.PathIO

ssl_context: ssl.SSLContext | None = None
if args.ftps != "off":
    if not all((args.keyfile, args.certfile)):
        raise ValueError("certfile and keyfile is required for FTPS")
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(args.certfile, args.keyfile)
elif any((args.keyfile, args.certfile)):
    raise ValueError("--certfile and --keyfile args require --ftps to be set")

family = {
    "ipv4": socket.AF_INET,
    "ipv6": socket.AF_INET6,
    "auto": socket.AF_UNSPEC,
}[args.family]


async def main() -> None:
    server = aioftp.Server(
        [user],
        path_io_factory=path_io_factory,
        ssl=ssl_context,
        ssl_explicit=args.ftps == "explicit",
    )
    await server.run(args.host, args.port, family=family)


with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
