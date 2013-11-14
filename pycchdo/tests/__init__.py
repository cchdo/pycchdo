import os
from unittest import TestCase
from logging import getLogger, StreamHandler, DEBUG, INFO, CRITICAL
from sys import stderr
from ConfigParser import SafeConfigParser

from pyramid import testing
from pyramid.paster import bootstrap

import transaction

from sqlalchemy import engine_from_config
from sqlalchemy.exc import InvalidRequestError

from pycchdo.util import StringIO, pyStringIO, MemFile as MockFile
from pycchdo.models.models import (
    DBSession, Base, reset_fs, FSFile, Person, 
    )
from pycchdo.log import ColoredLogger, ColoredFormatter


__all__ = [
    'log', 'BaseTest', 'PersonBaseTest', 'MockFile', 'MockFieldStorage',
    'MockSession', 'engine_loglevel', 'DEBUG', 'CRITICAL', 'setUpModule',
    'tearDownModule',
    ]


log = ColoredLogger(__name__)


db_echo = False
engine = None
logger = None


def setUpModule():
    global engine, logger
    if engine is None:
        env = bootstrap(os.path.join(os.getcwd(), 'test.ini'))
        settings = env['registry'].settings
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)
        FSFile.fs_setup()

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
        try:
            DBSession.flush()
        except InvalidRequestError:
            transaction.begin()
            transaction.get().doom()
        self.testPerson.accept(self.testPerson)

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
        log.info('Mock set {0!r} {1!r}'.format(key, value))

    def flash(self, queue, msg):
        log.info('Mock Flash {0!r} {1!r}'.format(queue, msg))

    def peek_flash(self, queue):
        return 'Mock Flash peek for', queue

    def pop_flash(self, queue):
        return 'Mock Flash pop for', queue
