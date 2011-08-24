import unittest
from pyramid.config import Configurator
from pyramid import testing

class TestViewIntegration(unittest.TestCase):
  def setUp(self):
    self.config = testing.setUp()

  def tearDown(self):
    testing.tearDown()

  def test_cruises_view(self):
    from pycchdo.views.cruise import cruise_show
    request = testing.DummyRequest()
    request.matchdict['cruise_id'] = 'fake_cruise'

    result = cruise_show(request)
    self.assertEqual(result, {'data_files': None, 'cruise_dict': {},
                              'history': [], 'cruise': None})
