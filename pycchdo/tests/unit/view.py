from cgi import FieldStorage
from StringIO import StringIO
from logging import getLogger

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest
from pyramid_mailer import get_mailer

from pycchdo.tests import (
    RequestBaseTest, PersonBaseTest, MockFieldStorage, MockFile, MockSession
    )
from pycchdo.models.serial import Cruise, FSFile, DBSession
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

    def test_submit_response(self):
        from pycchdo.views.submit import response_from_submission_request
        fst = MockFieldStorage(
            MockFile('hello', 'asdf.txt'), 'asdf.txt', 'text/plain')
        self.request.method = 'POST'
        self.request.POST['files[0]'] = fst
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
    def test_clear(self):
        from pycchdo.views.datacart import clear
        self.request.method = 'POST'
        self.request.is_xhr = False
        self.request.referrer = ''
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
        cc0 = ccc.sugg(self.testPerson, 'expocode', 'qwer')
        cc1 = ccc.sugg(self.testPerson, 'expocode', 'asdf')
        DBSession.flush()
        self.request.params['ids'] = '{0},{1}'.format(cc0.id, cc1.id)
        result = as_received(self.request)
        self.assertTrue(cc0 in result)
        self.assertTrue(cc1 in result)

        change = ccc.sugg(self.testPerson, 'expocode', '1234')
        DBSession.flush()
        self.request.params['ids'] = str('ZZ9912345678')
        result = as_received(self.request)
        self.assertEqual([], result)
        

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
