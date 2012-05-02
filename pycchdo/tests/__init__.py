from unittest import TestCase

from pyramid import testing

import pycchdo.models as M


__all__ = ['BaseTest', 'MockFieldStorage', 'MockSession', ]


class BaseTest(TestCase):
    _connected = False
    def setUp(self):
        self.config = testing.setUp()
        if not self._connected:
            M.init_conn({
                'db_uri': 'mongodb://sui.ucsd.edu:27018/?w=1&fsync=true',
                'db_name': 'cchdo',
            })
            self._connected = True
        M.cchdo().objs.drop()
        M.cchdo().attrs.drop()

    def tearDown(self):
        M.cchdo().objs.drop()
        M.cchdo().attrs.drop()
        del self.config
        testing.tearDown()


class MockFieldStorage:
    def __init__(self, filename, file, contentType):
        self.filename = filename
        self.file = file
        self.type = contentType


class MockSession:
    def get(self, key, default):
        return 'Mock Session value for', key, default

    def __setitem__(self, key, value):
        print 'Mock set', key, value

    def flash(self, queue, msg):
        print 'Mock Flash', queue, msg

    def peek_flash(self, queue):
        return 'Mock Flash peek for', queue

    def pop_flash(self, queue):
        return 'Mock Flash pop for', queue
