from unittest import TestCase
import logging
from StringIO import StringIO as pyStringIO
import transaction
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO

from pyramid import testing

from sqlalchemy import create_engine

from pycchdo.models.models import (
    DBSession, Base, reset_fs, FSFile, Person, 
    )
from pycchdo.log import ColoredLogger, ColoredFormatter


__all__ = [
    'log', 'BaseTest', 'PersonBaseTest', 'MockFile', 'MockFieldStorage',
    'MockSession', 'setUpModule', 'tearDownModule',
    ]


log = ColoredLogger(__name__)


db_uri = 'postgresql://pycchdo:pycchd0@315@sui.ucsd.edu:5432/test_pycchdo'
db_echo = True
engine = None


def setUpModule():
    global engine
    if engine is None:
        log.info('connecting')
        engine = create_engine(db_uri)
        DBSession.configure(bind=engine)
        FSFile.reconfig_fs_storage()

        if db_echo:
            sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
            color_formatter = ColoredFormatter()
            console = logging.StreamHandler()
            console.setFormatter(color_formatter)
            sqlalchemy_logger.addHandler(console)
            sqlalchemy_logger.setLevel(logging.DEBUG)


def tearDownModule():
    reset_fs()
    engine = None


class BaseTest(TestCase):
    def setUp(self):
        self.config = testing.setUp()
        transaction.get().doom()

    def tearDown(self):
        del self.config
        DBSession.flush()
        DBSession.rollback()
        testing.tearDown()


class PersonBaseTest(BaseTest):
    def setUp(self):
        super(PersonBaseTest, self).setUp()
        self.testPerson = Person(identifier='testperson')
        DBSession.add(self.testPerson)
        DBSession.flush()
        self.testPerson.accept(self.testPerson)

    def tearDown(self):
        super(PersonBaseTest, self).tearDown()


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
