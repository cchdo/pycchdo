import unittest
from pyramid.config import Configurator
from pyramid import testing

class ViewTests(unittest.TestCase):
  def setUp(self):
    self.config = testing.setUp()

  def tearDown(self):
    testing.tearDown()

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
