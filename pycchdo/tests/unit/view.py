from cgi import FieldStorage
from StringIO import StringIO
from logging import getLogger

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest

from pycchdo.tests import (
    RequestBaseTest, PersonBaseTest, MockFieldStorage, MockFile, MockSession
    )
from pycchdo.models.serial import Cruise, FSFile


log = getLogger(__name__)


class TestGlobal(RequestBaseTest):
    def test_file_response_content_type(self):
        """content_type must be a string."""
        from pycchdo.views import file_response
        fst = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')
        fff = FSFile.from_fieldstorage(fst)
        resp = file_response(self.request, fff)
        self.assertTrue(isinstance(resp.content_type, basestring))


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
        self.assertEqual(resp['submission'][0].file.open_file().read(), 'hello')
        

class TestStaff(RequestBaseTest):
    def test_create_asr_bad_data_type(self):
        from pycchdo.views.staff import create_asr
        ccc = Cruise.create(self.testPerson).obj

        fst = MockFieldStorage(
            MockFile('hello', 'asr.txt'), 'asr.txt', 'text/plain')

        create_asr(self.request, self.testPerson, ccc, '', fst)
        self.assertEqual(self.request.response.status, '400 Bad Request')
        

class TestMail(RequestBaseTest):
    def test_get_from_addr(self):
        from pycchdo.mail import get_email_addresses
        self.assertNotEqual(
            '', get_email_addresses(self.request, 'from_address')[0])
