import functools
import pathlib
import asyncio

import nose

from common import *  # noqa


def test_parse_directory_response():

    parse = functools.partial(aioftp.Client.parse_directory_response, None)

    nose.tools.eq_(
        parse('foo "baz "" test nop" """""fdfs """'),
        pathlib.PurePosixPath('baz " test nop'),
    )


def test_connection_del_future():

    loop = asyncio.new_event_loop()
    c = aioftp.Connection(loop=loop)
    c.foo = "bar"
    del c.future.foo


@nose.tools.raises(AttributeError)
def test_connection_not_in_storage():

    loop = asyncio.new_event_loop()
    c = aioftp.Connection(loop=loop)
    getattr(c, "foo")


@nose.tools.raises(ValueError)
def test_available_connections_too_much_acquires():

    ac = aioftp.AvailableConnections(3)
    ac.acquire()
    ac.acquire()
    ac.acquire()
    ac.acquire()


@nose.tools.raises(ValueError)
def test_available_connections_too_much_releases():

    ac = aioftp.AvailableConnections(3)
    ac.acquire()
    ac.release()
    ac.release()
