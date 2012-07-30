from jinja2 import Template as Jinja2Template

from . import *

from pyramid import testing

import pycchdo


# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
class ViewIntegrationTests(BaseTest):
    def setUp(self):
        """This sets up the application registry with the registrations your
        application declares in its ``includeme`` function.

        """
        super(ViewIntegrationTests, self).setUp()
        self.config = testing.setUp()
#        self.config.include('pycchdo.home')

    def tearDown(self):
        """Clear out the application registry."""
        super(ViewIntegrationTests, self).tearDown()
        testing.tearDown()

    def test_show_cruise(self):
        pass

    def test_empty_login_redirects(self):
        from pycchdo.views import session
        pass
