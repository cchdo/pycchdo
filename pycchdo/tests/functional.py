from cgi import FieldStorage
from datetime import datetime, timedelta
from StringIO import StringIO

from pyramid import testing
from pyramid.httpexceptions import HTTPSeeOther, HTTPUnauthorized
from pyramid_mailer import get_mailer

# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
#from jinja2 import Template as Jinja2Template

from pycchdo.tests import (
    PersonBaseTest, RequestBaseTest, MockFieldStorage, MockFile,
    )
from pycchdo.models.serial import DBSession, Cruise, Person, Collection, Note
from pycchdo.log import getLogger
from pycchdo.views.toplevel import home
from pycchdo.views.cruise import cruise_show, cruises_index
from pycchdo.views.submit import response_from_submission_request
from pycchdo.views.staff import moderation, submission_attach, uow
from pycchdo.views.collection import collections_index


log = getLogger(__name__)


class TestToplevel(RequestBaseTest):
    def test_home(self):
        result = home(self.request)
        self.assertEqual(result, {'updated': []})


class TestCruise(RequestBaseTest):
    def test_show(self):
        expocode = '33RR20090320'

        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'expocode', expocode)

        fst = MockFieldStorage(
            MockFile('hello', 'btl_hy1.csv'), 'btl_hy1.csv', 'text/csv')
        ccc.sugg(self.testPerson, 'bottle_exchange', fst).accept(self.testPerson)

        ccc.notes.append(Note(self.testPerson, 'a note'))

        self.request.matchdict['cruise_id'] = str(ccc.id)
        with self.assertRaises(HTTPSeeOther):
            cruise_show(self.request)

        self.request.matchdict['cruise_id'] = ccc.uid
        cruise_show(self.request)

    def test_index_reduced_specificity(self):
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

        ccc = Collection.propose(self.testPerson).obj

        result = collections_index(self.request)
        self.assertEqual(0, len(result['collections']))

        ccc.change.accept(self.testPerson)
        result = collections_index(self.request)
        self.assertEqual(1, len(result['collections']))

        ccc.change.reject(self.testPerson)
        result = collections_index(self.request)
        self.assertEqual(0, len(result['collections']))


class TestSubmit(RequestBaseTest):
    def test_response_from_submission_request(self):
        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')
        self.request.POST['files[0]'] = fst
        response_from_submission_request(self.request)

        mailer = get_mailer(self.request)
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject,
                         "[CCHDO] Submission by None:  ")


class TestStaffModeration(RequestBaseTest):
    def test_moderation_create_asr(self):
        self.request.user = ppp = Person()
        ppp.permissions = [u'staff']

        ccc = Cruise.create(self.testPerson).obj

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')

        self.request.params['_method'] = 'PUT'
        self.request.params['action'] = 'create'
        self.request.params['cruise_id'] = str(ccc.id)
        self.request.params['data_type'] = 'data_suggestion'
        self.request.POST['data'] = fst

        result = moderation(self.request)

    def test_submission_attach(self):
        mailer = get_mailer(self.request)

        self.request.params['_method'] = 'PUT'
        self.request.user = None

        with self.assertRaises(HTTPUnauthorized):
            result = submission_attach(self.request)

        self.request.user = ppp = Person()
        ppp.permissions = []

        ccc = Cruise.create(self.testPerson).obj
        self.request.params['cruise_id'] = str(ccc.id)

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')
        self.request.POST['data'] = fst

        result = submission_attach(self.request)

        self.assertEqual(len(mailer.outbox), 0)

        ppp.permissions = [u'staff']

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')
        self.request.POST['data'] = fst

        result = submission_attach(self.request)

        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject,
                         "Data available As Received for {0}".format(ccc.uid))

    def test_moderate_acknowledge_email(self):
        self.request.user = ppp = Person()
        ppp.permissions = [u'staff']

        ccc = Cruise.create(self.testPerson).obj

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')
        asr = ccc.sugg(ppp, 'bottle_exchange', fst)

        self.request.params['_method'] = 'PUT'
        self.request.params['action'] = 'Acknowledge'
        self.request.params['cruise_id'] = str(ccc.id)
        self.request.params['attr'] = str(asr.id)

        result = moderation(self.request)

        mailer = get_mailer(self.request)

        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject,
                         "Data available As Received for {0}".format(ccc.uid))
