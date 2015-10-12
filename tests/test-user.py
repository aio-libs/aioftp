import pathlib

import nose

from common import *  # noqa


@nose.tools.raises(aioftp.PathIsNotAbsolute)
def test_user_not_absolute_home():

    aioftp.User(home_path="foo")


def test_user_representation():

    u = aioftp.User("foo", "bar", base_path=pathlib.PurePosixPath("."))
    nose.tools.eq_(
        repr(u),
        "User('foo', 'bar', base_path=PurePosixPath('.'), "
        "home_path=PurePosixPath('/'), permissions=" +
        repr([aioftp.Permission()]) +
        ", maximum_connections=" + repr(u.maximum_connections) + ")"
    )
