from pyramid import testing

from jinja2 import Template as Jinja2Template

from . import *
import pycchdo


# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
class TestView(PersonBaseTest):
    def setUp(self):
        super(TestView, self).setUp()
        self.request = testing.DummyRequest()
        self.request.registry = self.config.registry
        self.request.user = self.testPerson

    def test_home(self):
        from pycchdo.views.toplevel import home
        result = home(self.request)
        self.assertEqual(result, {'updated': [], 'upcoming': []})

    def test_cruise_show(self):
        from pycchdo.views.cruise import cruise_show
        from pycchdo.models import DBSession, Cruise

        expocode = '33RR20090320'

        ccc = Cruise(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()
        ccc.set_accept('expocode', expocode, self.testPerson)

        self.config.add_route('submit_menu', '/submit.html')
        self.config.add_route('cruise_new', '/cruises/{cruise_id}/new')
        self.request.matchdict['cruise_id'] = str(ccc.id)
        result = cruise_show(self.request)
