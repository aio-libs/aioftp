import unittest
import aioftp


class TestYoba(unittest.TestCase):

    def test_yoba(self):

        c = aioftp.Client()
        self.assertEqual(True, True)

    def test_foo(self):

        self.assertEqual(True, True)
