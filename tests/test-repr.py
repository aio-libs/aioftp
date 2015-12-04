import nose

import aioftp

from common import *  # noqa


def test_throttle_repr():

    t = aioftp.Throttle(loop="loop")
    nose.tools.eq_(repr(t), "Throttle(loop='loop', limit=None, reset_rate=10)")


def test_user_repr():

    u = aioftp.User()
    nose.tools.eq_(
        repr(u),
        "User("
            "None, "
            "None, "
            "base_path=PosixPath('.'), "
            "home_path=PurePosixPath('/'), "
            "permissions=["
                "Permission(PurePosixPath('/'), "
                "readable=True, "
                "writable=True)], "
            "maximum_connections=None, "
            "read_speed_limit=None, "
            "write_speed_limit=None, "
            "read_speed_limit_per_connection=None, "
            "write_speed_limit_per_connection=None)"
    )


def test_memory_path_io_repr():

    from aioftp.pathio import Node

    pio = aioftp.MemoryPathIO(loop="loop")
    pio.fs = [Node("dir", "/", 1, 1, content=[])]
    nose.tools.eq_(
        repr(pio),
        "[Node(type='dir', name='/', ctime=1, mtime=1, content=[])]"
    )


def test_permission_representation():

    p = aioftp.Permission(writable=False)
    nose.tools.eq_(
        repr(p),
        "Permission(PurePosixPath('/'), readable=True, writable=False)"
    )
