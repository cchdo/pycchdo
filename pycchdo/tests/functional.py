from pyramid import testing
from pyramid.httpexceptions import HTTPSeeOther

from jinja2 import Template as Jinja2Template

from pycchdo.tests import PersonBaseTest
from pycchdo.models.serial import DBSession, Cruise


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
        expocode = '33RR20090320'

        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)

        self.config.add_route('submit_menu', '/submit.html')
        self.config.add_route('cruise_new', '/cruises/{cruise_id}/new')
        self.config.add_route('cruise_show', '/cruise/{cruise_id}')
        self.request.matchdict['cruise_id'] = str(ccc.id)
        with self.assertRaises(HTTPSeeOther):
            cruise_show(self.request)

        self.request.matchdict['cruise_id'] = expocode
        cruise_show(self.request)
