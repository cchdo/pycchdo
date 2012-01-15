import unittest
from pyramid.config import Configurator
from pyramid import testing

from . import *


class ViewTests(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def test_home_view(self):
        from pycchdo.views import home
        request = testing.DummyRequest()
        result = home(request)
        self.assertEqual(result, {'updated': []})
