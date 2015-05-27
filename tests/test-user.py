import nose

from common import *


@nose.tools.raises(aioftp.PathIsNotAbsolute)
def test_user_not_absolute_home():

    aioftp.User(home_path="foo")
