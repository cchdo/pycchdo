import os
import os.path
from unittest import TestCase
from logging import getLogger, DEBUG

from pyramid import testing
from pyramid.paster import bootstrap

import transaction

from sqlalchemy.exc import InvalidRequestError

from sqlalchemy_imageattach.context import (
    pop_store_context, push_store_context)

from pycchdo import initialize_from_settings
from pycchdo.routes import configure_routes
from pycchdo.util import StringIO, pyStringIO, MemFile as MockFile
from pycchdo.models.serial import (
    DBSession, reset_fs, Person, 
    )
from pycchdo.log import color_console


log = getLogger(__name__)


db_echo = False
pyramid_settings = None
log_name_engine = 'sqlalchemy.engine'


INI_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'test.ini')


def setUpModule():
    global pyramid_settings
    if pyramid_settings is None:
        env = bootstrap(INI_PATH)
        pyramid_settings = env['registry'].settings
        initialize_from_settings(pyramid_settings)

        if db_echo:
            logger = getLogger(log_name_engine)
            logger.addHandler(color_console)
            logger.setLevel(DEBUG)


def tearDownModule():
    reset_fs(pyramid_settings['fsstore'])


class BaseTest(TestCase):
    def setUp(self):
        push_store_context(pyramid_settings['fsstore'])
        self.config = testing.setUp()
        transaction.begin()

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


class RequestBaseTest(PersonBaseTest):
    def setUp(self):
        super(RequestBaseTest, self).setUp()
        self.config.include('pyramid_mailer.testing')
        configure_routes(self.config)
        self.request = testing.DummyRequest()
        self.request.registry = self.config.registry
        self.request.registry.settings = pyramid_settings
        self.request.user = self.testPerson


class MockFieldStorage():
    def __init__(self, file, filename='mockfile.txt',
                 contentType='application/octet-stream'):
        self.file = file
        try:
            self.filename = file.name
        except AttributeError:
            self.filename = self.filename
        self.type = contentType

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
