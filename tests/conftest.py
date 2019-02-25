import asyncio
import functools
import logging
import pathlib
import shutil
import socket
import ssl

import pytest
import trustme

import aioftp


ca = trustme.CA()
server_cert = ca.issue_server_cert("127.0.0.1", "::1")

ssl_server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
server_cert.configure_cert(ssl_server)

ssl_client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ca.configure_trust(ssl_client)

PORT = 8888
