import unittest
import datetime

from pyramid.config import Configurator
from pyramid import testing


class TestModel(unittest.TestCase):
    def setUp(self):
        from pycchdo.models import Person
        self.config = testing.setUp()
        self.testPerson = Person(identifier='testid')
        self.testPerson.save()

    def tearDown(self):
        self.testPerson.remove()
        del self.testPerson
        testing.tearDown()

    def test_Stamp_requires_saved_Person(self):
        """ Stamp requires a saved Person. """
        from pycchdo.models import Stamp, Person
        p = Person(identifier='testid1')
        Stamp(self.testPerson)
        self.assertRaises(ValueError, lambda: Stamp(p))

    def test_new_Change(self):
        """ Newly created objects have correct values for stamps and notes """
        from pycchdo.models import _Change
        before = datetime.datetime.utcnow()
        change = _Change(self.testPerson)
        after = datetime.datetime.utcnow()
        self.assertTrue(change['creation_stamp']['timestamp'] >= before)
        self.assertTrue(change['creation_stamp']['timestamp'] <= after)
        self.assertTrue(change['pending_stamp'] is None)
        self.assertTrue(change['judgment_stamp'] is None)
        self.assertFalse(change['accepted'])
        self.assertTrue(change['note'] is None)

        from pycchdo.models import Note
        change1 = _Change(self.testPerson, note=Note('action', 'data_type', 'subject', 'body'))
        self.assertEqual(change1['note']['action'], 'action')
        self.assertEqual(change1['note']['data_type'], 'data_type')
        self.assertEqual(change1['note']['subject'], 'subject')
        self.assertEqual(change1['note']['body'], 'body')

    def test_accept_Change(self):
        """ Acceptance of _Change """
        from pycchdo.models import _Change, Person
        change = _Change(self.testPerson)
        change.accept(self.testPerson)
        self.assertTrue(change.is_accepted())
        self.assertTrue(change['accepted'])
        change.remove()

    def test_reject_Change(self):
        """ Rejection of _Change """
        from pycchdo.models import _Change, Person
        change = _Change(self.testPerson)
        change.reject(self.testPerson)
        self.assertTrue(change.is_rejected())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_acknowledge_Change(self):
        """ Acknowledgement of _Change """
        from pycchdo.models import _Change
        change = _Change(self.testPerson)
        change.acknowledge(self.testPerson)
        self.assertTrue(change.is_acknowledged())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_get_Obj_Attrs(self):
        """ Obj should always return an _Attrs dict """
        from pycchdo.models import Obj, _Attrs
        obj = Obj(self.testPerson)
        attrs = obj.attrs
        self.assertTrue(isinstance(attrs, _Attrs))

    def test_Attrs_data_model(self):
        """ Disallow setting and deleting from _Attrs without giving a Person
        responsible (i.e. using Python data model) to prevent misleading.
        
        """
        from pycchdo.models import Obj, Attr
        obj = Obj(self.testPerson)
        obj.save()

        attrs = obj.attrs
        def test_setter():
            attrs['a'] = '1'
        self.assertRaises(NotImplementedError, test_setter)
        def test_deleter():
            del attrs['a']
        self.assertRaises(NotImplementedError, test_deleter)

        obj.remove()

    def test_Attrs_get_scalar(self):
        """ Getting a scalar value in _Attr should return the latest accepted
        value.

        """
        from pycchdo.models import Obj, Attr
        obj = Obj(self.testPerson)
        obj.save()

        attrs = obj.attrs
        key = 'a'

        attrs.set(key, '0', self.testPerson)
        attrs.set(key, '1', self.testPerson)
        attrs.set(key, '2', self.testPerson)

        self.assertRaises(KeyError, lambda: attrs[key])
        Attr.map_mongo(attrs.history(key, value='1'))[0].accept(self.testPerson)
        self.assertEquals(attrs[key], '1')
        Attr.map_mongo(attrs.history(key, value='2'))[0].accept(self.testPerson)
        self.assertEquals(attrs[key], '2')
        Attr.map_mongo(attrs.history(key, value='0'))[0].accept(self.testPerson)
        self.assertEquals(attrs[key], '0')
        attrs.delete(key, self.testPerson)
        attrs.unacknowledged_changes[0].accept(self.testPerson)
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_Attrs_set_scalar(self):
        """ Setting a scalar value in _Attr should create a new Attr.
        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
        from pycchdo.models import Obj, Attr
        obj = Obj(self.testPerson)
        obj.save()
        attrs = obj.attrs
        key = 'a'
        value = '0'
        attrs.set(key, value, self.testPerson)
        self.assertRaises(KeyError, lambda: attrs[key])
        history = attrs.history(key)
        last_attr = Attr.map_mongo(history)[0]
        self.assertEquals(last_attr['value'], value)
        last_attr.accept(self.testPerson)
        self.assertEquals(attrs[key], value)

        value1 = '1'
        attrs.set(key, value1, self.testPerson)
        self.assertEquals(attrs[key], value)
        attrs.unacknowledged_changes[0].accept(self.testPerson)
        self.assertEquals(attrs[key], value1)

        attrs.delete(key, self.testPerson)
        self.assertEquals(attrs[key], value1)
        attrs.unacknowledged_changes[0].accept(self.testPerson)
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_new_Obj(self):
        """ New Objs are instances of _Change """
        from pycchdo.models import Obj, _Change
        obj = Obj(self.testPerson)
        self.assertTrue(isinstance(obj, _Change))
        self.assertEqual(obj['_obj_type'], 'Obj')

    def test_remove_Obj(self):
        """ Removing an Obj also removes all Attrs it is associated with. """
        from pycchdo.models import Obj, Attr
        obj = Obj(self.testPerson)
        obj.save()
        attr = Attr(self.testPerson, 'a', '0', obj['_id'])
        attr.save()
        self.assertEqual(Attr.map_mongo(Attr.find({'obj': obj['_id']}))[0]['_id'], attr['_id'])
        obj.remove()
        self.assertEqual(Attr.find({'obj': obj['_id']}).count(True), 0)

    def test_Obj_has_obj_type(self):
        """ Objs are required to have an _obj_type key that is just the class
        name """
        from pycchdo.models import Obj, Person
        obj = Obj(self.testPerson)
        obj.save()
        self.assertEqual(Obj.__name__, obj['_obj_type'])
        obj.remove()
        self.assertEqual(Person.__name__, self.testPerson['_obj_type'])

    def test_new_Attr(self):
        """ New Attrs are instances of _Change """
        from pycchdo.models import Attr, _Change
        attr = Attr(self.testPerson)
        self.assertTrue(isinstance(attr, _Change))

    def test_Person_new(self):
        """ New people are Objs """
        from pycchdo.models import Person, Obj
        p = Person(name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertTrue(isinstance(p, Obj))

    def test_Person_new_without_id_provider(self):
        """ A new Person without an ID must supply their first and last name,
        institution, country, and email.
        """
        from pycchdo.models import Person
        # Missing name_first
        self.assertRaises(ValueError, lambda: Person(
            name_last="Tester",
            institution="Test University", country="Testland",
            email="test@test.com"))
        # Missing name_last
        self.assertRaises(ValueError, lambda: Person(
            name_first="Ryan",
            institution="Test University", country="Testland",
            email="test@test.com"))
        # Missing institution
        self.assertRaises(ValueError, lambda: Person(
            name_first="Ryan", name_last="Tester",
            country="Testland", email="test@test.com"))
        # Missing country
        self.assertRaises(ValueError, lambda: Person(
            name_first="Ryan", name_last="Tester",
            institution="Test University", email="test@test.com"))
        # Missing email
        self.assertRaises(ValueError, lambda: Person(
            name_first="Ryan", name_last="Tester",
            institution="Test University", country="Testland"))
        Person(name_first="Ryan", name_last="Tester",
               institution="Test University", country="Testland",
               email="test@test.com")

    def test_Person_new_with_id(self):
        """ A Person with an ID can supply their own information """
        from pycchdo.models import Person
        p = Person(identifier='testid', name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertTrue(p.is_verified())
        self.assertEquals(p['name_first'], 'Ryan')
        self.assertEquals(p['name_last'], 'Tester')
        self.assertEquals(p['institution'], 'Test University')
        self.assertEquals(p['country'], 'Testland')
        self.assertEquals(p['email'], 'test@test.com')

    def test_Person_is_verified(self):
        """ If they are associated with an ID provider then they are verified
        """
        from pycchdo.models import Person
        p = Person(name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertFalse(p.is_verified())
        p['identifier'] = 'testid'
        self.assertTrue(p.is_verified())

    def test_Person_is_required_for_stamp(self):
        """ Stamps are required to be signed off by a Person """
        from pycchdo.models import Person, Stamp
        self.assertRaises(TypeError, lambda: Stamp())
        self.assertRaises(TypeError, lambda: Stamp(None))
        Stamp(self.testPerson)
