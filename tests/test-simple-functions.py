import pathlib
import asyncio
import datetime
import itertools

import nose

import aioftp
from common import *  # noqa


def test_parse_directory_response():
    nose.tools.eq_(
        aioftp.Client.parse_directory_response('foo "baz "" test nop" """""fdfs """'),
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


def test_parse_pasv_response():
    p = aioftp.Client.parse_pasv_response
    nose.tools.eq_(p("(192,168,1,0,1,0)"), ("192.168.1.0", 256))


def test_parse_epsv_response():
    p = aioftp.Client.parse_epsv_response
    nose.tools.eq_(p("some text (ha-ha) (|||665|) ((((666() (|fd667s)."), (None, 666))
    nose.tools.eq_(p("some text (ha-ha) (|||665|) (6666666)."), (None, 666))


def _c_locale_time(d):
    with aioftp.common.setlocale("C"):
        return d.strftime("%b %d %H:%M")


def test_parse_list_datetime_not_older_than_6_month_format():
    p = aioftp.Client.parse_ls_date
    date_to_p = lambda d: d.strftime("%Y%m%d%H%M00")  # noqa
    dates = (
        datetime.datetime(year=2000, month=1, day=1),
        datetime.datetime(year=2000, month=12, day=31),
    )
    dt = datetime.timedelta(seconds=15778476 // 2)
    deltas = (datetime.timedelta(), dt, -dt)
    for now, delta in itertools.product(dates, deltas):
        d = now + delta
        nose.tools.eq_(p(_c_locale_time(d), now=d), date_to_p(d))
