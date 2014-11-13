import os
from cgi import FieldStorage
from StringIO import StringIO
from shutil import rmtree
from logging import getLogger
from tempfile import mkdtemp
from datetime import date

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest
from pyramid_mailer import get_mailer

from pycchdo.tests import (
    RequestBaseTest, PersonBaseTest, MockFieldStorage, MockFile, MockSession
    )
from pycchdo.models.serial import Cruise, FSFile, DBSession, UOW, Note
from pycchdo.views.staff import _moderate_attribute, as_received


log = getLogger(__name__)


class TestGlobal(RequestBaseTest):
    def test_file_response_content_type(self):
        """content_type must be a string."""
        from pycchdo.views import file_response
        fname = 'somename.txt'
        fst = MockFieldStorage(
            MockFile('', fname), contentType='text/plain')
        fff = FSFile.from_fieldstorage(fst)
        resp = file_response(self.request, fff)

        self.assertTrue(isinstance(resp.content_type, basestring))

        self.assertTrue(resp.content_disposition.split('filename=')[1], fname)


class TestView(PersonBaseTest):
    def test__collapse_dict(self):
        """Collapse a dictionary tree based on a given value being invalid."""
        from pycchdo.views import collapse_dict
        d = {}
        self.assertEquals(collapse_dict(d, 1), 1)
        d = {'a': 1, 'b': None}
        self.assertEquals(collapse_dict(d), {'a': 1})
        d = {'a': 1, 'b': None, 'c': {'d': None, 'e': 2}}
        self.assertEquals(collapse_dict(d), {'a': 1, 'c': {'e': 2}})
        d = {'a': 1, 'b': 1, 'c': {'d': 1, 'e': 1}}
        self.assertEquals(collapse_dict(d, 1), 1)
        d = {'a': 1, 'b': [{'d': None, 'e': None}]}
        self.assertEquals(collapse_dict(d), {'a': 1})

    def test_cruise_show(self):
        # XXX HACK because route_url doesn't work without route config
        self.config.add_route('cruise_new', 'test')
        self.config.add_route('cruise_show', 'test')
        from pycchdo.views.cruise import cruise_show
        request = testing.DummyRequest()
        with self.assertRaises(HTTPBadRequest):
            cruise_show(request)

        ccc = Cruise.create(self.testPerson).obj

        request.matchdict['cruise_id'] = ccc.uid
        request.user = None

        result = cruise_show(request)

    def test_cruise_show_suggest_file(self):
        # XXX HACK because route_url doesn't work without route config
        self.config.add_route('cruise_new', 'test')
        self.config.add_route('cruise_show', 'test')

        from pycchdo.views.cruise import cruise_show
        from pyramid.renderers import render_to_response

        ccc = Cruise.create(self.testPerson).obj

        mock_file = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')

        request = testing.DummyRequest()
        request.matchdict['cruise_id'] = ccc.uid
        request.user = self.testPerson
        request.method = 'POST'
        request.params['_method'] = 'PUT'
        request.params['action'] = 'suggest_file'
        request.params['type'] = 'invalid_type'
        request.params['file'] = mock_file

        request.session = MockSession()

        dictionary = cruise_show(request)

        #response = render_to_response(
        #    'templates/cruise/show.jinja2', cruise_show(request),
        #    request=request)
        # TODO test response for recognizing bad type


class TestSubmit(RequestBaseTest):
    def test_submit_post(self):
        from pycchdo.views.submit import submit
        self.request.method = 'POST'

        submit(self.request)
        self.assertEqual(self.request.response.status, '400 Bad Request')
        self.assertEqual(
            self.request.session.pop_flash('error'),
            ['Please correct the errors below'])

    def test_create_submission(self):
        from pycchdo.views.submit import _create_submission
        self.request.method = 'POST'
        self.request.params['name'] = 'direct_name'
        self.request.params['email'] = 'direct_email'

        ddd = {
            'files': [
                MockFieldStorage(MockFile('aaa', 'aaa.txt')), 
                MockFieldStorage(MockFile('bbb', 'bbb.txt'))]
        }
        sub = _create_submission(self.request, ddd)

    def test_submit_response(self):
        from pycchdo.views.submit import response_from_submission_request
        fst = MockFieldStorage(
            MockFile('hello', 'asdf.txt'), 'asdf.txt', 'text/plain')
        self.request.method = 'POST'
        self.request.POST['files[0]'] = fst
        self.request.POST['name'] = 'name'
        self.request.POST['email'] = 'email'
        resp = response_from_submission_request(self.request)
        self.assertEqual(resp['submission'].file.open_file().read(), 'hello')


class TestCruise(RequestBaseTest):
    def test_add_note(self):
        from pycchdo.views.cruise import _add_note

        ccc = Cruise.create(self.testPerson).obj

        _add_note(self.request, ccc)

        self.assertEqual(self.request.response.status, '400 Bad Request')

        self.request.params['note_data_type'] = 'data_type'
        self.request.params['note_action'] = 'action'
        self.request.params['note_summary'] = 'summary'
        self.request.params['note_note'] = 'note'

        _add_note(self.request, ccc)


class TestCountry(RequestBaseTest):
    def test_index(self):
        from pycchdo.views.country import countries_index, countries_index_json
        countries_index(self.request)
        countries_index_json(self.request)


class TestInstitution(RequestBaseTest):
    def test_index(self):
        from pycchdo.views.institution import institutions_index, institutions_index_json
        institutions_index(self.request)
        institutions_index_json(self.request)


class TestShip(RequestBaseTest):
    def test_index(self):
        from pycchdo.views.ship import ships_index, ships_index_json
        ships_index(self.request)
        ships_index_json(self.request)


class TestCollection(RequestBaseTest):
    def test_index(self):
        from pycchdo.views.collection import collections_index, collections_index_json
        collections_index(self.request)
        collections_index_json(self.request)


class TestDatacart(RequestBaseTest):
    def setUp(self):
        super(TestDatacart, self).setUp()
        from pycchdo.models.datacart import Datacart
        self.request.datacart = Datacart()
        self.request.is_xhr = False
        self.request.referrer = ''

    def tearDown(self):
        del self.request.datacart
        super(TestDatacart, self).tearDown()

    def test_add(self):
        ccc = Cruise.create(self.testPerson).obj
        fst = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')
        ccc = ccc.set(self.testPerson, 'bottle_exchange', fst)
        from pycchdo.views.datacart import add
        self.request.params['id'] = unicode(ccc.id)
        add(self.request)

    def test_remove(self):
        ccc = Cruise.create(self.testPerson).obj
        fst = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')
        fff = ccc.set(self.testPerson, 'bottle_exchange', fst)
        from pycchdo.views.datacart import add, add_cruise, remove
        self.request.params['id'] = unicode(fff.id)
        add(self.request)
        remove(self.request)

        self.request.params['id'] = unicode(ccc.id)
        add_cruise(self.request)
        self.request.params['id'] = unicode(fff.id)
        remove(self.request)

    def test_clear(self):
        from pycchdo.views.datacart import clear
        self.request.method = 'POST'
        clear(self.request)
        

class TestStaff(RequestBaseTest):
    def test_create_asr_bad_data_type(self):
        from pycchdo.views.staff import create_asr
        ccc = Cruise.create(self.testPerson).obj

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')

        create_asr(self.request, self.testPerson, ccc, '', fst)
        self.assertEqual(self.request.response.status, '400 Bad Request')

    def test_create_asr(self):
        from pycchdo.views.staff import create_asr
        ccc = Cruise.create(self.testPerson).obj
        fst = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')
        fsf = FSFile.from_fieldstorage(fst)

        # Doing so as editor will not acknowledge, no history note
        len_prior = len(ccc.notes)
        asr = create_asr(
            self.request, self.testPerson, ccc, 'bottle_exchange', fsf)
        self.assertEqual(len(ccc.notes), len_prior)

        # Doing so as staff will acknowledge, and create a history note
        self.testPerson.permissions = ['staff']
        asr = create_asr(
            self.request, self.testPerson, ccc, 'bottle_exchange', fsf)
        self.assertEqual(len(ccc.notes) - 1, len_prior)
        self.testPerson.permissions = []

    def test_moderate_attribute(self):
        ccc = Cruise.create(self.testPerson).obj
        fst = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')
        asr = ccc.set(self.testPerson, 'bottle_exchange', fst)
        self.request.params['action'] = 'Acknowledge'
        self.request.params['attr'] = asr.id
        len_prior = len(ccc.notes)
        _moderate_attribute(self.request)
        self.assertEqual(len(ccc.notes) - 1, len_prior)

    def test_as_received(self):
        self.request.user = self.testPerson
        self.testPerson.permissions = ['staff']

        self.request.params['ids'] = ''
        result = as_received(self.request)
        self.assertEqual([], result)

        ccc = Cruise.create(self.testPerson).obj
        fst = MockFieldStorage(
            MockFile('qwer', 'test.txt'), 'test.txt', 'text/plain')
        cc0 = ccc.sugg(self.testPerson, 'data_suggestion', fst)
        fst = MockFieldStorage(
            MockFile('asdf', 'test.txt'), 'test.txt', 'text/plain')
        cc1 = ccc.sugg(self.testPerson, 'data_suggestion', fst)
        DBSession.flush()
        self.request.params['ids'] = '{0},{1}'.format(cc0.id, cc1.id)
        result = as_received(self.request)
        self.assertTrue(cc0 in result)
        self.assertTrue(cc1 in result)

        fst = MockFieldStorage(
            MockFile('1234', 'test.txt'), 'test.txt', 'text/plain')
        change = ccc.sugg(self.testPerson, 'data_suggestion', fst)
        DBSession.flush()
        self.request.params['ids'] = str('ZZ9912345678')
        result = as_received(self.request)
        self.assertEqual([], result)

    def test_create_history_repr(self):
        from pycchdo.views.staff import CruiseHistoryRepr
        ccc = Cruise.create(self.testPerson).obj

        # Case 1a
        fst = MockFieldStorage(
            MockFile('case1aa', 'case1aa'), 'case1aa', 'text/plain')
        chg1aa = ccc.sugg(self.testPerson, 'data_suggestion', fst)
        fst = MockFieldStorage(
            MockFile('case1ab', 'case1ab'), 'case1ab', 'text/plain')
        chg1aa.accept(self.testPerson, fst)

        # Case 1b
        uow = UOW()
        uow.note = Note(self.testPerson, 'readme', 'action', 'title', 'summary')
        fst = MockFieldStorage(
            MockFile('case1ba', 'case1ba'), 'case1ba', 'text/plain')
        uow.results.append(ccc.set(self.testPerson, 'bottle_exchange', fst))

        fst = MockFieldStorage(
            MockFile('case1bb', 'case1bb'), 'case1bb', 'text/plain')
        chg1bb = ccc.set(self.testPerson, 'data_suggestion', fst)
        uow.suggestions.append(chg1bb)

        fst = MockFieldStorage(
            MockFile('case1bc', 'case1bc'), 'case1bc', 'text/plain')
        chg1bc = ccc.sugg(self.testPerson, 'bottle_woce', fst)
        fst = MockFieldStorage(
            MockFile('case1bd', 'case1bd'), 'case1bd', 'text/plain')
        chg1bc.accept(self.testPerson, fst)
        uow.suggestions.append(chg1bc)

        # Case 2
        fst = MockFieldStorage(
            MockFile('case2', 'case2'), 'case2', 'text/plain')
        chg2 = ccc.sugg(self.testPerson, 'data_suggestion', fst)
        chg2.acknowledge(self.testPerson)

        tempdir = mkdtemp()
        try:
            fsstore = self.request.registry.settings['fsstore']
            CruiseHistoryRepr(fsstore, tempdir, ccc)

            # Case 1a
            uowdir = '{0}_{1}_{2}'.format(
                date.today().strftime('%Y.%m.%d'), str(chg1aa.id),
                self.testPerson.uid)

            self.assertEqual(
                ['case1aa'],
                os.listdir(os.path.join(tempdir, uowdir, 'originals')))
            self.assertEqual(
                ['case1ab'],
                os.listdir(os.path.join(tempdir, uowdir, 'to_go_online')))

            # Case 1b
            uowdir = '{0}_{1}_{2}'.format(
                date.today().strftime('%Y.%m.%d'), 'summary',
                self.testPerson.uid)
            self.assertTrue(uowdir in os.listdir(tempdir))

            readme_path = os.path.join(tempdir, uowdir, '00_README.txt')
            self.assertEqual(u'readme', open(readme_path, 'r').read(6))

            self.assertEqual(
                ['case1bb', 'case1bd'],
                os.listdir(os.path.join(tempdir, uowdir, 'originals')))
            self.assertEqual(
                ['case1bc'],
                os.listdir(os.path.join(tempdir, uowdir, 'submission')))
            self.assertEqual(
                ['case1ba'],
                os.listdir(os.path.join(tempdir, uowdir, 'to_go_online')))

            # Case 2
            self.assertEqual(
                ['case2'],
                os.listdir(os.path.join(tempdir, 'asr', str(chg2.id))))
        finally:
            rmtree(tempdir)
        

class TestMail(RequestBaseTest):
    def test_get_from_addr(self):
        from pycchdo.mail import get_email_addresses
        self.assertNotEqual(
            '', get_email_addresses(self.request, 'from_address')[0])

    def test_send_processing_email(self):
        from pycchdo.mail import send_processing_email
        readme_str = 'readme'
        uow_cfg = {
            'expocode': 'EXPOCODE',
            'q_infos': [
                {
                    'q_id': 'asr',
                    'submission_id': 'sub',
                    'filename': 'fname',
                    'submitted_by': 'submitter',
                    'date': '1970-01-01',
                    'data_type': 'data_suggestion',
                }
            ],
        }
        note_id = 'note'
        send_processing_email(self.request, readme_str, uow_cfg, note_id, False)

        mailer = get_mailer(self.request)
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject, "")
        self.assertEqual(mailer.outbox[0].body[:10], "Dear CCHDO")

    def test_send_processing_email_dryrun(self):
        from pycchdo.mail import send_processing_email
        readme_str = 'readme'
        uow_cfg = {
            'expocode': 'EXPOCODE',
            'q_infos': [
                {
                    'q_id': 'asr',
                    'submission_id': 'sub',
                    'filename': 'fname',
                    'submitted_by': 'submitter',
                    'date': '1970-01-01',
                    'data_type': 'data_suggestion',
                }
            ],
        }
        note_id = 'note'
        send_processing_email(self.request, readme_str, uow_cfg, note_id, True)

        mailer = get_mailer(self.request)
        self.assertEqual(len(mailer.outbox), 1)
        self.assertEqual(mailer.outbox[0].subject, "DRYRUN None")
        self.assertEqual(mailer.outbox[0].body[:10], "Dear CCHDO")
