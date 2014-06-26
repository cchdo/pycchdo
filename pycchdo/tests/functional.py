from cgi import FieldStorage
from datetime import datetime, timedelta
from StringIO import StringIO

from pyramid import testing
from pyramid.httpexceptions import HTTPSeeOther

# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
#from jinja2 import Template as Jinja2Template

from pycchdo.tests import PersonBaseTest, RequestBaseTest
from pycchdo.models.serial import DBSession, Cruise, Person, Collection
from pycchdo.log import getLogger


log = getLogger(__name__)


class TestToplevel(RequestBaseTest):
    def test_home(self):
        from pycchdo.views.toplevel import home
        result = home(self.request)
        self.assertEqual(result, {'updated': [], 'upcoming': []})

    def test_cruise_show(self):
        from pycchdo.views.cruise import cruise_show
        expocode = '33RR20090320'

        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)

        self.request.matchdict['cruise_id'] = str(ccc.id)
        with self.assertRaises(HTTPSeeOther):
            cruise_show(self.request)

        self.request.matchdict['cruise_id'] = expocode
        cruise_show(self.request)


class TestCruise(RequestBaseTest):
    def test_index_reduced_specificity(self):
        from pycchdo.views.cruise import cruise_show
        expocode = '33RR20090320'

        future_date = datetime.now() + timedelta(seconds=1)

        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)
        ccc.set(self.testPerson, 'date_start', future_date)

        self.request.matchdict['cruise_id'] = expocode
        result = cruise_show(self.request)
        self.assertEqual(result['cruise'].date_start.year, future_date.year)

    def test_list_rejected_cruise(self):
        """Rejected cruise should not appear."""
        from pycchdo.views.cruise import cruises_index
        expocode = 'rejected'

        ccc = Cruise.propose(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)

        result = cruises_index(self.request)
        self.assertEqual(0, len(result['cruises']))

        ccc.change.accept(self.testPerson)
        result = cruises_index(self.request)
        self.assertEqual(1, len(result['cruises']))

        ccc.change.reject(self.testPerson)
        result = cruises_index(self.request)
        self.assertEqual(0, len(result['cruises']))

    def test_rejected_cruise(self):
        """Rejected cruise should not appear."""
        from pycchdo.views.cruise import cruise_show
        expocode = 'rejected'

        ccc = Cruise.propose(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)
        ccc.change.reject(self.testPerson)

        self.request.matchdict['cruise_id'] = expocode
        with self.assertRaises(HTTPSeeOther):
            cruise_show(self.request)
        

class TestCollection(RequestBaseTest):
    def test_list_rejected_cruise(self):
        """Rejected cruise should not appear."""
        from pycchdo.views.collection import collections_index

        ccc = Collection.propose(self.testPerson).obj

        result = collections_index(self.request)
        self.assertEqual(0, len(result['collections']))

        ccc.change.accept(self.testPerson)
        result = collections_index(self.request)
        self.assertEqual(1, len(result['collections']))

        ccc.change.reject(self.testPerson)
        result = collections_index(self.request)
        self.assertEqual(0, len(result['collections']))


class TestStaffModeration(RequestBaseTest):
    def test_moderation_create_asr(self):
        from pycchdo.views.staff import moderation
        self.request.user = ppp = Person()
        ppp.permissions = [u'staff']

        ccc = Cruise.create(self.testPerson).obj

        fst = FieldStorage()
        fst.filename = 'asr.txt'
        fst.type = 'text/plain'
        fst.file = StringIO('hello')

        self.request.params['_method'] = 'PUT'
        self.request.params['action'] = 'create'
        self.request.params['cruise_id'] = str(ccc.id)
        self.request.params['data_type'] = 'data_suggestion'
        self.request.POST['data'] = fst

        result = moderation(self.request)
