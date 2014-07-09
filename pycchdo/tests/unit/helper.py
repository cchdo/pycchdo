from logging import getLogger

from pyramid import testing

from pycchdo.tests import (
    PersonBaseTest, MockFieldStorage, MockFile
    )
from pycchdo.models.types import File
from pycchdo.models.serial import DBSession, Cruise, Person, FSFile, Submission
from pycchdo.doc_rest import reST_to_html_div
from pycchdo.helpers import data_file_link, data_uri


log = getLogger(__name__)


class TestHelper(PersonBaseTest):
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
        request = testing.DummyRequest()

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
        answer = unicode(data_file_link(request, 'bottle_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)

        answer_parts = [
            'class="ctd zip exchange"',
            '<abbr title="ZIP archive of ASCII .csv CTD data with station information">',
            '<a href="/data/b/c{id}/testfile.txt">CTD</a>'.format(id=data.id),
        ]
        answer = unicode(data_file_link(request, 'ctd_zip_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)

    def test_rest_to_html_div(self):
        output = reST_to_html_div('\xe2\x80\x9cDEG_C\xe2\x80\x9d')
        self.assertEqual(output, u'<div id="doc" class="history-note rendered">\n\n\n<p>\u201cDEG_C\u201d</p>\n</div>')
