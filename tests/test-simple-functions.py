import functools
import pathlib

import nose

from common import *


def test_parse_directory_response():

    parse = functools.partial(aioftp.Client.parse_directory_response, None)

    nose.tools.eq_(
        parse('foo "baz "" test nop" """""fdfs """'),
        pathlib.Path('baz " test nop'),
    )
