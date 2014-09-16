from logging import getLogger

from pyramid import testing

from pycchdo.tests import (
    PersonBaseTest, MockFieldStorage, MockFile
    )
from pycchdo.models.types import File
from pycchdo.models.serial import DBSession, Cruise, Person, FSFile, Submission
from pycchdo.doc_rest import reST_to_html_div
from pycchdo.helpers import data_file_link, data_uri
from pycchdo import helpers 


log = getLogger(__name__)


class TestHelper(PersonBaseTest):
    def setUp(self):
        super(TestHelper, self).setUp()
        self.req = testing.DummyRequest()

    def test_data_uri(self):
        fholder = Submission()
        DBSession.add(fholder)
        fname = 'testfile.txt'
        fholder.file = FSFile(MockFile('content', fname))
        DBSession.flush()
        output = data_uri(fholder)
        self.assertTrue(output.startswith("/data/b/"))
        self.assertTrue(output.endswith(fname))

    def test_data_file_link(self):
        """Given a Change with a file, provide a link to a file next to its
        description.

        """
        self.config.add_route('datacart_add', 'test')

        key = 'data_suggestion'
        Person.allow_attr(key, File)

        ccc = Cruise.create(self.testPerson).obj

        file = MockFieldStorage(
            MockFile('', 'testfile.txt'), 'testfile.txt', contentType='text/plain')
        data = ccc.set(self.testPerson, key, file)
        DBSession.flush()

        answer_parts = [
            'class="bottle exchange"',
            '<abbr title="ASCII .csv bottle data with station information">',
            '<a href="/data/b/c{id}/testfile.txt">Bottle</a>'.format(id=data.id),
        ]
        answer = unicode(data_file_link(self.req, 'bottle_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)

        answer_parts = [
            'class="ctd zip exchange"',
            '<abbr title="ZIP archive of ASCII .csv CTD data with station information">',
            '<a href="/data/b/c{id}/testfile.txt">CTD</a>'.format(id=data.id),
        ]
        answer = unicode(data_file_link(self.req, 'ctd_zip_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)

    def test_rest_to_html_div(self):
        output = reST_to_html_div('\xe2\x80\x9cDEG_C\xe2\x80\x9d')
        self.assertEqual(output, u'<div id="doc" class="history-note rendered">\n\n\n<p>\u201cDEG_C\u201d</p>\n</div>')

    def test_has_permission(self):
        # No permissions required means yes
        self.assertTrue(helpers.has_permission(self.req, []))
        # Permissions required but not available means no
        self.assertFalse(helpers.has_permission(self.req, ['staff']))
        # Permissions required and available means yes
        self.req.user = Person.create().obj
        self.assertFalse(helpers.has_permission(self.req, ['staff']))
        self.req.user.permissions = ['staff']
        self.assertTrue(helpers.has_permission(self.req, ['staff']))

