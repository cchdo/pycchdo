import unittest
import datetime

from pyramid.config import Configurator
from pyramid import testing


class TestModel(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_new_Change(self):
        """ Newly created objects have correct values for stamps and notes """
        from pycchdo.models import _Change
        before = datetime.datetime.now()
        change = _Change()
        after = datetime.datetime.now()
        self.assertTrue(change['creation_stamp']['timestamp'] >= before)
        self.assertTrue(change['creation_stamp']['timestamp'] <= after)
        self.assertTrue(change['pending_stamp'] is None)
        self.assertTrue(change['judgment_stamp'] is None)
        self.assertFalse(change['accepted'])
        self.assertTrue(change['note'] is None)

        from pycchdo.models import Note
        change1 = _Change(note=Note('action', 'data_type', 'subject', 'body'))
        self.assertEqual(change1['note']['action'], 'action')
        self.assertEqual(change1['note']['data_type'], 'data_type')
        self.assertEqual(change1['note']['subject'], 'subject')
        self.assertEqual(change1['note']['body'], 'body')

    def test_accept_Change(self):
        """ Acceptance of _Change """
        from pycchdo.models import _Change
        change = _Change()
        change.accept()
        self.assertTrue(change.is_accepted())
        self.assertTrue(change['accepted'])
        change.remove()

    def test_reject_Change(self):
        """ Rejection of _Change """
        from pycchdo.models import _Change
        change = _Change()
        change.reject()
        self.assertTrue(change.is_rejected())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_acknowledge_Change(self):
        """ Acknowledgement of _Change """
        from pycchdo.models import _Change
        change = _Change()
        change.acknowledge()
        self.assertTrue(change.is_acknowledged())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_get_Obj_Attrs(self):
        """ Obj should always return an _Attrs dict """
        from pycchdo.models import Obj, _Attrs
        obj = Obj()
        attrs = obj.attrs
        self.assertTrue(isinstance(attrs, _Attrs))

    def test_Attrs_get_scalar(self):
        """ Getting a scalar value in _Attr should return the latest accepted
        value.
        """
        from pycchdo.models import Obj, Attr
        obj = Obj()
        obj.save()

        attrs = obj.attrs
        key = 'a'

        attrs[key] = '0'
        attrs[key] = '1'
        attrs[key] = '2'

        self.assertRaises(KeyError, lambda: attrs[key])
        Attr.map_mongo(attrs.history(key, value='1'))[0].accept()
        self.assertEquals(attrs[key], '1')
        Attr.map_mongo(attrs.history(key, value='2'))[0].accept()
        self.assertEquals(attrs[key], '2')
        Attr.map_mongo(attrs.history(key, value='0'))[0].accept()
        self.assertEquals(attrs[key], '0')
        del attrs[key]
        attrs.unacknowledged_changes[0].accept()
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_Attrs_set_scalar(self):
        """ Setting a scalar value in _Attr should create a new Attr.
        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
        from pycchdo.models import Obj, Attr
        obj = Obj()
        obj.save()
        attrs = obj.attrs
        key = 'a'
        value = '0'
        attrs[key] = value
        self.assertRaises(KeyError, lambda: attrs[key])
        history = attrs.history(key)
        last_attr = Attr.map_mongo(history)[0]
        self.assertEquals(last_attr['value'], value)
        last_attr.accept()
        self.assertEquals(attrs[key], value)

        value1 = '1'
        attrs[key] = value1
        self.assertEquals(attrs[key], value)
        attrs.unacknowledged_changes[0].accept()
        self.assertEquals(attrs[key], value1)

        del attrs[key]
        self.assertEquals(attrs[key], value1)
        attrs.unacknowledged_changes[0].accept()
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_new_Obj(self):
        """ New Objs are instances of _Change """
        from pycchdo.models import Obj, _Change
        obj = Obj()
        self.assertTrue(isinstance(obj, _Change))
        self.assertEqual(obj['_obj_type'], 'Obj')

    def test_remove_Obj(self):
        """ Removing an Obj also removes all Attrs it is associated with. """
        from pycchdo.models import Obj, Attr
        obj = Obj()
        obj.save()
        attr = Attr('a', '0', obj['_id'])
        attr.save()
        self.assertEqual(Attr.map_mongo(Attr.find({'obj': obj['_id']}))[0]['_id'], attr['_id'])
        obj.remove()
        self.assertEqual(Attr.find({'obj': obj['_id']}).count(True), 0)

    def test_new_Attr(self):
        """ New Attrs are instances of _Change """
        from pycchdo.models import Attr, _Change
        attr = Attr()
        self.assertTrue(isinstance(attr, _Change))
