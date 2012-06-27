from unittest import TestCase
from shutil import rmtree
from StringIO import StringIO as pyStringIO
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO

from pyramid import testing

from sqlalchemy import create_engine

from pycchdo.models.models import (
    DBSession,
    Base,
    FSFile,
    )
import pycchdo.models as M
from pycchdo.util import FileProxyMixin
from pycchdo.log import ColoredLogger


__all__ = [
    'BaseTest', 'MockFile', 'MockFieldStorage', 'MockSession',
]


log = ColoredLogger(__name__)


class BaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup testing environment connections."""
        cls.log = log
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

        FSFile.reconfig_fs_storage()

    def setUp(self):
        self._config = testing.setUp()
        self.session = DBSession()

    def tearDown(self):
        DBSession.remove()
        del self._config
        testing.tearDown()

    @classmethod
    def tearDownClass(cls):
        """Tear down testing environment connections."""
        fss_root = FSFile._fs.base_location
        rmtree(fss_root)
        del cls.log


class MockFile(pyStringIO):
    def __init__(self, content, filename):
        pyStringIO.__init__(self, content)
        self.name = filename
        self.flush()

    @property
    def size(self):
        return len(self.getvalue())


class MockFieldStorage:
    def __init__(self, file, filename='mockfile.txt',
                 contentType='application/octet-stream'):
        self.filename = filename
        self.file = file
        self.type = contentType
        
        if not self.filename and self.file.name:
            self.filename = self.file.name


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
