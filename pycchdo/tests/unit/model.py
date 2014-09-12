from datetime import datetime

from pyramid import testing

from pycchdo.log import getLogger
from pycchdo.tests import BaseTest, PersonBaseTest, RequestBaseTest
from pycchdo.models.serial import SerializerDateTime, Unit, Cruise
from pycchdo.models.searchsort import Sorter


log = getLogger(__name__)


class TestSerializerDateTime(BaseTest):
    def setUp(self):
        super(TestSerializerDateTime, self).setUp()
        self.dtime = datetime(1900, 1, 2, 3, 4, 5, 6)
        self.output = '{"type": "dt", "val": "1900-01-02T03:04:05.000006"}'

    def test_serialize(self):
        serial = SerializerDateTime.serialize(self.dtime)
        self.assertEqual(self.output, serial)

    def test_deserialize(self):
        deserial = SerializerDateTime.deserialize(self.output)
        self.assertEqual(deserial, self.dtime)


class TestSearch(BaseTest):
    def test_woce_line(self):
        """WOCE line numbers need to be detected and searched for differently.

        A query with a WOCE line number that is a single digit should be
        rewritten with a zero. e.g. I8S -> I08S, AR9 -> AR09

        """
        from pycchdo.models.search import adapt_query_string_for_woce_line
        qqq = "i8s"
        self.assertEqual(u"(i8s OR i08s)", adapt_query_string_for_woce_line(qqq))
        qqq = "ar9"
        self.assertEqual(u"(ar9 OR ar09)", adapt_query_string_for_woce_line(qqq))

    def test_woce_line_inside(self):
        """WOCE line substitution should happen for all terms inside a query."""
        from pycchdo.models.search import adapt_query_string_for_woce_line
        qqq = "ar9 AND blah"
        self.assertEqual(u"(ar9 OR ar09) AND blah", adapt_query_string_for_woce_line(qqq))
        qqq = "blah AND NOT ar9"
        self.assertEqual(u"blah AND NOT (ar9 OR ar09)", adapt_query_string_for_woce_line(qqq))
        qqq = "i8s AND ar9"
        self.assertEqual(u"(i8s OR i08s) AND (ar9 OR ar09)", adapt_query_string_for_woce_line(qqq))


class TestSearchIndex(RequestBaseTest):
    def test_writer_finally_commit(self):
        sidx = self.request.registry.settings['db.search_index']
        with sidx.writer('country') as ixw:
            doc = {
                'names': u'testcountry',
                'mtime': datetime.now(),
                'id': u'0'
            }
            ixw.update_document(**doc)

            # calling an extra commit, this somehow closes the bufferedwriter
            # and needs to be handled in a finally clause
            ixw.commit()
        idx = sidx.open_or_create_index('country')
        self.assertEqual([0], list(idx.reader().all_doc_ids()))

    def test_writer_commits_after(self):
        sidx = self.request.registry.settings['db.search_index']
        with self.assertRaises(ValueError):
            with sidx.writer('country') as ixw:
                doc = {
                    'names': u'testcountry',
                    'mtime': datetime.now(),
                    'id': u'0'
                }
                ixw.update_document(**doc)
                raise ValueError()
        idx = sidx.open_or_create_index('country')
        self.assertEqual([0], list(idx.reader().all_doc_ids()))


class TestSearchSort(BaseTest):
    def test_date_start(self):
        sorter = Sorter('')
        cruise = Cruise()
        self.assertEqual(datetime(1, 1, 1), sorter.date_start(cruise))


class TestObj(PersonBaseTest):
    def test_get_attr(self):
        obj = Unit.create(self.testPerson).obj
        aaa = obj.set(self.testPerson, 'name', 'aaa')
        bbb = obj.set(self.testPerson, 'name', 'bbb')

        change = obj.get_attr('name')
        self.assertEqual(bbb, change)

    def test_get_attrs_or(self):
        obj = Unit.create(self.testPerson).obj
        aaa = obj.set(self.testPerson, 'name', 'aaa')
        bbb = obj.set(self.testPerson, 'name', 'bbb')
        ccc = obj.set(self.testPerson, 'mnemonic', 'ccc')
        ddd = obj.set(self.testPerson, 'mnemonic', 'ddd')

        changes = obj.get_attrs_or(['name', 'mnemonic'])
        self.assertEqual([bbb, ddd], changes)


class TestCruise(PersonBaseTest):
    def test_get_by_id(self):
        ccc = Cruise.create(self.testPerson).obj
        with self.assertRaises(ValueError):
            Cruise.get_by_id('no such id')
