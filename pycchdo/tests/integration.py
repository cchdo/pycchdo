import unittest
from pyramid.config import Configurator
from pyramid import testing

from . import *


class ViewTests(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def _getFUT(self):
       from pycchdo.views import home
       return home

    def test_home_view(self):
        from pycchdo.views import home
        request = testing.DummyRequest()
        result = home(request)
        print dir(result)
        print "done\n"
        self.assertEqual(result, {})
