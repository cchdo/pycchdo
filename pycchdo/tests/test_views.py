import unittest
import datetime

from pycchdo.config import Configurator
from pyramid import testing

class ViewTests(unittest.TestCase):
  def setUp(self):
    self.config = testing.setUp()

  def tearDown(self):
    testing.tearDown()


