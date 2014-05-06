import os
import os.path
from unittest import TestCase
from logging import getLogger, StreamHandler, DEBUG, INFO, CRITICAL
from sys import stderr
from tempfile import mkdtemp
from ConfigParser import SafeConfigParser

from pyramid import testing
from pyramid.paster import bootstrap

import transaction

from sqlalchemy import engine_from_config
from sqlalchemy.exc import InvalidRequestError

from sqlalchemy_imageattach.context import (
    pop_store_context, push_store_context)

from pycchdo.util import StringIO, pyStringIO, MemFile as MockFile
from pycchdo.models.serial import (
    DBSession, reset_fs, Person, 
    )
from pycchdo.models.filestorage import FSStore
from pycchdo.log import ColoredLogger, ColoredFormatter


log = ColoredLogger(__name__)


db_echo = False
engine = None
logger = None


fsstore = FSStore(path=mkdtemp(), base_url='/')


def setUpModule():
    global engine, logger
    if engine is None:
        env = bootstrap(os.path.join(os.path.dirname(__file__), '..', '..', 'test.ini'))
        settings = env['registry'].settings
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)

        if db_echo:
            logger = _add_logger('sqlalchemy.engine')
            engine_loglevel(DEBUG)


def engine_loglevel(level):
    if logger:
        logger.setLevel(level)


def _add_logger(logger_name):
    logger = getLogger(logger_name)
    color_formatter = ColoredFormatter()
    console = StreamHandler(stderr)
    console.setFormatter(color_formatter)
    logger.addHandler(console)
    return logger


def tearDownModule():
    reset_fs(fsstore)
    engine = None


class BaseTest(TestCase):
    def setUp(self):
        push_store_context(fsstore)
        self.config = testing.setUp()
        transaction.begin()
        transaction.get().doom()

    def tearDown(self):
        DBSession.flush()
        del self.config
        transaction.abort()
        testing.tearDown()
        pop_store_context()


class PersonBaseTest(BaseTest):
    def setUp(self):
        super(PersonBaseTest, self).setUp()
        self.testPerson = Person.create().obj
        self.testPerson.set_id_names('testperson')
        try:
            DBSession.flush()
        except InvalidRequestError:
            transaction.begin()
            transaction.get().doom()

    def tearDown(self):
        super(PersonBaseTest, self).tearDown()


class MockFieldStorage():
    def __init__(self, file, filename='mockfile.txt',
                 contentType='application/octet-stream'):
        self.file = file
        try:
            self.filename = file.name
        except AttributeError:
            self.filename = self.filename
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
        log.debug('Mock set {0!r} {1!r}'.format(key, value))

    def flash(self, queue, msg):
        log.debug('Mock Flash {0!r} {1!r}'.format(queue, msg))

    def peek_flash(self, queue):
        return 'Mock Flash peek for', queue

    def pop_flash(self, queue):
        return 'Mock Flash pop for', queue
