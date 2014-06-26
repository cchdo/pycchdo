from datetime import datetime

from pyramid import testing

from pycchdo.log import getLogger
from pycchdo.tests import BaseTest, PersonBaseTest, RequestBaseTest
from pycchdo.models.serial import SerializerDateTime, Unit


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
