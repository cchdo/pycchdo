from cgi import FieldStorage
from datetime import datetime, timedelta
from StringIO import StringIO
from collections import OrderedDict

from pyramid import testing
from pyramid.httpexceptions import (
    HTTPMethodNotAllowed, HTTPSeeOther, HTTPUnauthorized, HTTPBadRequest
)
from pyramid_mailer import get_mailer

# TODO Planning on figuring out how to render the jinja2 templates and search
# them for expected results.
#from jinja2 import Template as Jinja2Template

from pycchdo.tests import (
    PersonBaseTest, RequestBaseTest, MockFieldStorage, MockFile,
    )
from pycchdo.models.serial import (
    DBSession, Cruise, Person, Collection, Note, Institution,
    )
from pycchdo.log import getLogger
from pycchdo.views.toplevel import home
from pycchdo.views.cruise import cruise_show, cruises_index, _edit_attr
from pycchdo.views.submit import response_from_submission_request
from pycchdo.views.staff import moderation, submission_attach, uow
from pycchdo.views.collection import collections_index
from pycchdo.views.person import person_edit


log = getLogger(__name__)


class TestToplevel(RequestBaseTest):
    def test_home(self):
        result = home(self.request)
        self.assertEqual(result, {'updated': OrderedDict()})


class TestDatacart(RequestBaseTest):
    def test_download(self):
        from pycchdo.views.datacart import download
        with self.assertRaises(HTTPMethodNotAllowed):
            result = download(self.request)
        with self.assertRaises(HTTPBadRequest):
            self.request.params['_method'] = 'POST'
            result = download(self.request)
        with self.assertRaises(HTTPBadRequest):
            self.request.params['archive'] = ''
            result = download(self.request)

        ccc = Cruise.create(self.testPerson).obj
        fff = MockFieldStorage(MockFile('asdf', 'qwer.txt'))
        aaa = ccc.set(self.testPerson, 'bottle_exchange', fff)

        self.request.params['archive'] = str(aaa.id)
        self.request.fsstore = self.request.registry.settings['fsstore']
        result = download(self.request)
        self.assertEqual(result._status, '200 OK')
        self.assertTrue(result.headers['Content-Disposition'].startswith(
            'attachment; filename=cchdo_datacart_'))
        self.assertTrue(result.headers['Content-Disposition'].endswith(
            '.zip'))
        content = result._app_iter.next()
        self.assertEqual(content[:2], 'PK')


class TestObj(RequestBaseTest):
    def test_index(self):
        from pycchdo.views.obj import objs
        with self.assertRaises(HTTPUnauthorized):
            result = objs(self.request)

        self.request.user.permissions = ['staff']
        result = objs(self.request)
        self.assertTrue('objs' in result)


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

    def _setup_participant_suggest(self):
        self.request.params['_method'] = 'PUT'
        self.request.params['key'] = 'participants'
        self.request.params['action'] = 'edit_attr'
        self.request.params['edit_action'] = 'Set participants'

    def test_suggest_participant_no_person(self):
        ccc = Cruise.create(self.testPerson).obj

        self.request.matchdict['cruise_id'] = str(ccc.id)
        self._setup_participant_suggest()
        self.request.params['role0'] = 'Chief Scientist'
        self.request.params['person0'] = ''
        self.request.params['institution0'] = ''

        _edit_attr(self.request, ccc)

        self.assertEqual(ccc.changes(), [])

    def test_suggest_participant_no_inst(self):
        ccc = Cruise.create(self.testPerson).obj

        self.request.matchdict['cruise_id'] = str(ccc.id)
        self._setup_participant_suggest()
        self.request.params['role0'] = 'Chief Scientist'
        self.request.params['person0'] = str(self.testPerson.id)
        self.request.params['institution0'] = ''

        _edit_attr(self.request, ccc)

        participant = ccc.changes()[0].value[0]
        self.assertEqual(participant.person, self.testPerson)
        self.assertEqual(participant.institution, None)
        self.assertEqual(participant.role, 'Chief Scientist')

    def test_suggest_participant(self):
        ccc = Cruise.create(self.testPerson).obj
        iii = Institution.create(self.testPerson).obj

        self.request.matchdict['cruise_id'] = str(ccc.id)
        self._setup_participant_suggest()
        self.request.params['role0'] = 'Chief Scientist'
        self.request.params['person0'] = str(self.testPerson.id)
        self.request.params['institution0'] = str(iii.id)

        _edit_attr(self.request, ccc)

        participant = ccc.changes()[0].value[0]
        self.assertEqual(participant.person, self.testPerson)
        self.assertEqual(participant.institution, iii)
        self.assertEqual(participant.role, 'Chief Scientist')


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
        self.request.POST['name'] = 'name'
        self.request.POST['email'] = 'email'
        response_from_submission_request(self.request)

        mailer = get_mailer(self.request)
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject,
                         "[CCHDO] Submission by name:  ")


class TestStaffSubmissions(RequestBaseTest):
    def test_submissions(self):
        self.request.user = ppp = Person()
        ppp.permissions = [u'staff']

        from webob.multidict import MultiDict
        from pycchdo.views.staff import submissions

        resp = submissions(self.request)
        self.assertEqual(resp['ltype'], 'Not attached not Argo')

        self.request.params = MultiDict(self.request.params)

        self.request.url = 'http://localhost/staff/submissions.html'

        self.request.params['query'] = 'asdf'
        self.request.params['ltype'] = 'bad'
        # ValueError due to inability to generate route
        with self.assertRaises(ValueError):
            resp = submissions(self.request)
        self.assertEqual(resp['ltype'], 'Not attached not Argo')

        self.request.params['query'] = 'bad'
        self.request.params['ltype'] = 'id'
        with self.assertRaises(HTTPBadRequest):
            submissions(self.request)


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


class TestInputForms(RequestBaseTest):
    def test_person_modification(self):
        ppp = self.testPerson
        ppp.permissions = [u'staff']

        self.request.matchdict['person_id'] = str(ppp.id)

        self.request.params['_method'] = u'PUT'
        self.request.params['identifier'] = u'test_id'
        self.request.params['name'] = u'test_name'
        self.request.params['name_first'] = u'test_first_name'
        self.request.params['name_last'] = u'test_last_name'
        self.request.params['institution'] = u'textstr'
        self.request.params['country'] = u'textstr'
        self.request.params['permissions'] = u''

        result = person_edit(self.request)
        self.assertIsInstance(result, HTTPSeeOther)
        self.assertIn("_f_form_error_institution", self.request.session)
        self.assertIn("_f_form_error_country", self.request.session)
