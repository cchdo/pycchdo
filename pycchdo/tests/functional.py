from jinja2 import Template as Jinja2Template

import unittest

from pyramid import testing

# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
class ViewIntegrationTests(unittest.TestCase):
    def setUp(self):
        """ This sets up the application registry with the
        registrations your application declares in its ``includeme``
        function.
        """
        import pycchdo
        self.config = testing.setUp()
#        self.config.include('pycchdo.home')

    def tearDown(self):
        """ Clear out the application registry """
        testing.tearDown()

    def test_show_cruise(self):
        pass

    def test_empty_login_redirects(self):
        from pycchdo.views import session
        pass
