from unittest import TestCase
from StringIO import StringIO as pyStringIO
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO

from pyramid import testing

from sqlalchemy import create_engine

from pycchdo.models.models import (
    DBSession, Base, reset_database, reset_fs, FSFile,
    )
from pycchdo.log import ColoredLogger


__all__ = [
    'log', 'BaseTest', 'MockFile', 'MockFieldStorage', 'MockSession',
    'setUpModule', 'tearDownModule',
    ]


log = ColoredLogger(__name__)


db_uri = 'postgresql://pycchdo:pycchd0@315@sui.ucsd.edu:5432/dev_pycchdo'
db_echo = False
engine = None


def setUpModule():
    global engine
    if engine is None:
        engine = create_engine(db_uri, echo=db_echo)
        DBSession.configure(bind=engine)
        reset_database(engine)
        FSFile.reconfig_fs_storage()


def tearDownModule():
    reset_fs()
    engine = None


class BaseTest(TestCase):
    def setUp(self):
        self._config = testing.setUp()

    def tearDown(self):
        del self._config
        DBSession.flush()
        DBSession.rollback()
        testing.tearDown()


class MockFile(pyStringIO):
    def __init__(self, content, filename):
        pyStringIO.__init__(self, content)
        self.name = filename
        self.flush()

    @property
    def size(self):
        return len(self.getvalue())

    def __repr__(self):
        return u'MockFile({0!r:<10}, {1!r})'.format(self.getvalue(), self.name)


class MockFieldStorage:
    def __init__(self, file, filename='mockfile.txt',
                 contentType='application/octet-stream'):
        self.filename = filename
        self.file = file
        self.type = contentType
        
        if not self.filename and self.file.name:
            self.filename = self.file.name

    def __repr__(self):
        return u'MockFieldStorage({0!r}, {1!r}, {2!r})'.format(
            self.filename, self.type, self.file)


class MockSession:
    def get(self, key, default):
        return 'Mock Session value for', key, default

    def __setitem__(self, key, value):
        log.info('Mock set {0!r} {1!r}'.format(key, value))

    def flash(self, queue, msg):
        log.info('Mock Flash {0!r} {1!r}'.format(queue, msg))

    def peek_flash(self, queue):
        return 'Mock Flash peek for', queue

    def pop_flash(self, queue):
        return 'Mock Flash pop for', queue
