from pyramid import testing

from pycchdo.tests import (
    PersonBaseTest, MockFieldStorage, MockFile
    )
from pycchdo.models.types import File
from pycchdo.models.serial import DBSession, Cruise, Person


class TestHelper(PersonBaseTest):
    def test_helper_data_file_link(self):
        """Given a Change with a file, provide a link to a file next to its
        description.

        """
        from pycchdo.helpers import data_file_link
        request = testing.DummyRequest()

        self.config.add_route('datacart_add', 'test')

        key = 'data_suggestion'
        Person.allow_attr(key, File)

        ccc = Cruise.create(self.testPerson).obj

        file = MockFieldStorage(
            MockFile('', 'testfile.txt'), contentType='text/plain')
        data = ccc.set(self.testPerson, key, file)
        DBSession.flush()

        answer_parts = [
            'class="bottle exchange"',
            '<abbr title="ASCII .csv bottle data with station information">',
            '<a href="/data/b/{id}">Bottle</a>'.format(id=data.id),
        ]
        answer = unicode(data_file_link(request, 'bottle_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)

        answer_parts = [
            'class="ctd zip exchange"',
            '<abbr title="ZIP archive of ASCII .csv CTD data with station information">',
            '<a href="/data/b/{id}">CTD</a>'.format(id=data.id),
        ]
        answer = unicode(data_file_link(request, 'ctd_zip_exchange', data))
        for part in answer_parts:
            self.assertIn(part, answer)
