import unittest
import datetime

from pyramid.config import Configurator
from pyramid import testing

import shapely.geometry.linestring
import shapely.geometry.polygon

import pycchdo.models as M
from pycchdo.models.models import collectablemongodoc, Stamp, Obj, _Change, \
                                  _Attrs, Attr, Note, Country, Cruise, Person


def global_setUp(self):
    self.config = testing.setUp()
    M.init_conn({'db_uri': 'mongodb://dimes.ucsd.edu:28018/?journal=true&wtimeout=300'})
    M.cchdo().objs.drop()
    M.cchdo().attrs.drop()
    self.testPerson = Person(identifier='testid')
    self.testPerson.save()


def global_tearDown(self):
    self.testPerson.remove()
    del self.testPerson
    testing.tearDown()


class _mock_FieldStorage:
    def __init__(self, filename, file, contentType):
        self.filename = filename
        self.file = file
        self.type = contentType


class TestModel(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def test_Stamp_requires_saved_Person(self):
        """ Stamp requires a saved Person. """
        p = Person(identifier='testid1')
        Stamp(self.testPerson)
        self.assertRaises(ValueError, lambda: Stamp(p))

    def test_new_Change(self):
        """ Newly created objects have correct values for stamps and notes """
        before = datetime.datetime.utcnow()
        change = _Change(self.testPerson)
        after = datetime.datetime.utcnow()
        self.assertTrue(change['creation_stamp']['timestamp'] >= before)
        self.assertTrue(change['creation_stamp']['timestamp'] <= after)
        self.assertTrue(change['pending_stamp'] is None)
        self.assertTrue(change['judgment_stamp'] is None)
        self.assertFalse(change['accepted'])
        self.assertTrue(change['note'] is None)

        change1 = _Change(self.testPerson, note=Note('body', 'action', 'data_type', 'subject'))
        self.assertEqual(change1['note']['action'], 'action')
        self.assertEqual(change1['note']['data_type'], 'data_type')
        self.assertEqual(change1['note']['subject'], 'subject')
        self.assertEqual(change1['note']['body'], 'body')

    def test_accept_Change(self):
        """ Acceptance of _Change """
        change = _Change(self.testPerson)
        change.accept(self.testPerson)
        self.assertTrue(change.is_accepted())
        self.assertTrue(change['accepted'])
        change.remove()

    def test_reject_Change(self):
        """ Rejection of _Change """
        change = _Change(self.testPerson)
        change.reject(self.testPerson)
        self.assertTrue(change.is_rejected())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_acknowledge_Change(self):
        """ Acknowledgement of _Change """
        change = _Change(self.testPerson)
        change.acknowledge(self.testPerson)
        self.assertTrue(change.is_acknowledged())
        self.assertFalse(change['accepted'])
        change.remove()

    def test_Attrs_accepted_changes(self):
        """ Accepted changes """
        o = Obj(self.testPerson)
        o.save()
        self.assertEquals([], o.attrs.accepted_changes())
        o.attrs.set('a', 'b', self.testPerson)
        self.assertEquals([], o.attrs.accepted_changes())
        Attr.map_mongo(o.attrs.history()[0]).accept(self.testPerson)
        self.assertEquals([o.attrs.history()[0]], o.attrs.accepted_changes())
        o.remove()

    def test_Attrs_keys(self):
        """ Accepted keys """
        o = Obj(self.testPerson)
        o.save()
        self.assertEquals([], o.attrs.keys())
        o.attrs.set('a', 'b', self.testPerson)
        Attr.map_mongo(o.attrs.history()[0]).accept(self.testPerson)
        self.assertEquals(['a'], o.attrs.keys())
        o.remove()

    def test_get_Obj_Attrs(self):
        """ Obj should always return an _Attrs dict """
        obj = Obj(self.testPerson)
        attrs = obj.attrs
        self.assertTrue(isinstance(attrs, _Attrs))

    def test_Attrs_data_model(self):
        """ Disallow setting and deleting from _Attrs without giving a Person
        responsible (i.e. using Python data model) to prevent misleading.
        
        """
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
        attrs.unacknowledged_changes()[0].accept(self.testPerson)
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_Attrs_get_default(self):
        """ Getting a non-existant value should return default. """
        obj = Obj(self.testPerson)
        obj.save()

        attrs = obj.attrs

        self.assertEquals(attrs.get('a'), None)
        self.assertEquals(attrs.get('a', 'b'), 'b')

        obj.remove()

    def test_Attrs_set_scalar(self):
        """ Setting a scalar value in _Attr should create a new Attr.
        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
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
        attrs.unacknowledged_changes()[0].accept(self.testPerson)
        self.assertEquals(attrs[key], value1)

        attrs.delete(key, self.testPerson)
        self.assertEquals(attrs[key], value1)
        attrs.unacknowledged_changes()[0].accept(self.testPerson)
        self.assertRaises(KeyError, lambda: attrs[key])

        obj.remove()

    def test_Attrs_delete(self):
        """ Deleting an Attr will write a new Attr with its deleted attribute
        True. It will no longer appear in the current key value pairs.

        This maintains the history of the Attr and differentiates a None
        value and deletion.
        """
        obj = Obj(self.testPerson)
        obj.save()
        a = obj.attrs

        a.set('a', 'b', self.testPerson).accept(self.testPerson)
        self.assertTrue('a' in a.keys())
        a.delete('a', self.testPerson).accept(self.testPerson)
        # TODO intermittent error
        self.assertFalse('a' in a.current_pairs)
        self.assertFalse('a' in a.keys())

        obj.remove()

    def test_new_Obj(self):
        """ New Objs are instances of _Change """
        obj = Obj(self.testPerson)
        self.assertTrue(isinstance(obj, _Change))
        self.assertEqual(obj['_obj_type'], 'Obj')

    def test_remove_Obj(self):
        """ Removing an Obj also removes all Attrs it is associated with. """
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
        obj = Obj(self.testPerson)
        obj.save()
        self.assertEqual(Obj.__name__, obj['_obj_type'])
        obj.remove()
        self.assertEqual(Person.__name__, self.testPerson['_obj_type'])

    def test_Obj_has_notes(self):
        """ A generic Obj can have notes added about it.

        Consider a Cruise gets email or someone would like to make an arbitrary
        note about an Institution but aren't sure of its validity.
        """
        obj = Obj(self.testPerson)
        obj.save()
        try:
            self.assertTrue(hasattr(obj, 'notes'))
            note = obj.add_note(Note('test note'), self.testPerson)
            self.assertEqual(len(obj.notes()), 0)
            note.accept(self.testPerson)
            self.assertEqual(len(obj.notes()), 1)
            all_attrs = filter(lambda x: not x, [isinstance(x, Attr) for x in obj.notes()])
            self.assertTrue(len(all_attrs) is 0)
            all_notes = filter(lambda x: not x, [x.is_note() for x in obj.notes()])
            self.assertTrue(len(all_notes) is 0)
        finally:
            obj.remove()

    def test_new_Attr(self):
        """ New Attrs are instances of _Change """
        attr = Attr(self.testPerson)
        self.assertTrue(isinstance(attr, _Change))

    def test_Person_new(self):
        """ New people are Objs """
        p = Person(name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertTrue(isinstance(p, Obj))

    def test_Person_new_without_id_provider(self):
        """ A new Person without an ID must supply their first and last name,
        institution, country, and email.
        """
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
        p = Person(name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertFalse(p.is_verified())
        p['identifier'] = 'testid'
        self.assertTrue(p.is_verified())

    def test_Person_is_required_for_stamp(self):
        """ Stamps are required to be signed off by a Person """
        self.assertRaises(TypeError, lambda: Stamp())
        self.assertRaises(TypeError, lambda: Stamp(None))
        Stamp(self.testPerson)

    def test_collectablemongodoc_find_id_with_invalid_id_raises_ValueError(self):
        """ Attempting to find an invalid collectablemongodoc raises ValueError. """
        self.assertRaises(ValueError, lambda: collectablemongodoc.find_id('invalid_object_id'))

    def test_Obj_map_mongo(self):
        """ An Obj mapped from a mongo doc will have the correct _obj_type """
        id = self.testPerson['_id']
        o = Obj.get_id(id)
        self.assertEquals(o['_obj_type'], 'Person')

    def test_Obj_find_id_with_invalid_id_returns_None(self):
        """ Attempting to find an invalid ObjectId returns None. """
        self.assertEquals(None, Obj.find_id('invalid_object_id'))

    def test_Obj_finders_find_Objs(self):
        """ Obj finders should find Objs based on their class """
        obj = Obj(self.testPerson)
        obj.save()
        self.assertTrue(Obj.find_one({'_id': obj['_id']}) != None)
        self.assertTrue(Person.find_one({'_id': self.testPerson['_id']}) != None)
        obj.remove()

    def test_Change_stamp_properties(self):
        """ The properties for _Changes corresponding to stamps should return a mapped object """
        obj = Obj(self.testPerson)
        obj.save()
        self.assertTrue(type(obj.creation_stamp) is Stamp)
        self.assertTrue(obj.pending_stamp is None)
        self.assertTrue(obj.judgment_stamp is None)
        obj.acknowledge(self.testPerson)
        self.assertTrue(type(obj.pending_stamp) is Stamp)
        obj.accept(self.testPerson)
        self.assertTrue(type(obj.judgment_stamp) is Stamp)
        obj.remove()

    def test_new_Attr_returns_Attr(self):
        obj = Obj(self.testPerson)
        obj.save()
        self.assertTrue(type(obj.attrs.set('a', 'v', self.testPerson)) is Attr)
        obj.remove()

    def test_Attr_list(self):
        """ Setting a list on an Obj's attrs stores a list """
        obj = Obj(self.testPerson)
        obj.save()

        a = obj.attrs.set('a', [], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a['value']) is list)
        a = obj.attrs.set('a', ['b'], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a['value']) is list)
        self.assertTrue(a['value'] == ['b'])

        obj.remove()

    def test_Attr_file_suggesting(self):
        """ Setting an Attr to some binary data adds a Attr that has file set
        to True. Such an object must be given some data. It may optionally be
        given
            a MIME type.
        """
        from StringIO import StringIO
        obj = Obj(self.testPerson)
        obj.save()

        file_data = StringIO('this is a test file object\nwith two lines')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')

        a = obj.attrs.set('a', file, self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a) is Attr)
        self.assertTrue(a['file'])
        obj.remove()

    def test_Attr_file_creation(self):
        """ Creating a Attr with a file stores the file in an object store. """
        from StringIO import StringIO
        file_data = StringIO('this is a test file object\nwith two lines')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')
        note = None

        d = Attr(self.testPerson, 'a', file, 'testid', note)
        d.save()

        file.file.seek(0)
        self.assertEquals(d.file.read(), file.file.read())
        d.remove()

    def test_Attr_track_suggesting(self):
        """ Setting an Attr to a track saves the value in track.
        """
        obj = Obj(self.testPerson)
        obj.save()

        a = obj.attrs.set('track', [[32, -117], [33, 118]], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a) is Attr)
        self.assertTrue(a['track'])
        obj.remove()

    def test_Cruise_has_country(self):
        """ Get a Cruise's country """
        c = Cruise(self.testPerson)
        c.save()
        country = Country(self.testPerson)
        country.save()
        c.attrs.set('country', country.id, self.testPerson).accept(self.testPerson)
        self.assertTrue(c.country is not None)
        self.assertTrue(c.country().id, country.id)
        country.remove()
        c.remove()

    def test_Cruise_track(self):
        """ Getting a Cruise's track either gives None or a
        shapely.geometry.linestring.LineString
        
        """
        c = Cruise(self.testPerson)
        c.save()
        t = c.track()
        self.assertTrue(t is None)
        c.attrs.set('track', [[0, 0], [1, 1]], self.testPerson).accept(self.testPerson)
        t = c.track()
        self.assertTrue(t is not None)
        self.assertTrue(type(t) is shapely.geometry.linestring.LineString)
        c.remove()

    def test_Cruise_filter_geo(self):
        """ Filter a list of Cruises by a geo function """
        c0 = Cruise(self.testPerson)
        c0.save()
        c0.attrs.set('track', [[0, 0], [0, 1]], self.testPerson).accept(self.testPerson)
        c1 = Cruise(self.testPerson)
        c1.save()
        c1.attrs.set('track', [[2, 0], [3, 1]], self.testPerson).accept(self.testPerson)

        cs = Cruise.map_mongo(Cruise.all())

        p0 = shapely.geometry.polygon.Polygon([[-1, -1], [-1, 2], [4, 2], [4, -1], [-1, -1]])
        p1 = shapely.geometry.polygon.Polygon([[1, -1], [1, 2], [4, 2], [4, -1], [1, -1]])

        self.assertEquals(Cruise.filter_geo(p0.intersects, cs), cs)
        self.assertEquals(Cruise.filter_geo(p1.intersects, cs), [cs[1]])

        c0.remove()
        c1.remove()


class TestHelper(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def test_helper_data_file_link(self):
        """ Given an Attr with a file, provide a link to a file next to its description """
        from pycchdo.helpers import data_file_link
        from StringIO import StringIO
        file_data = StringIO('')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')
        data = Attr(self.testPerson, 'a', file, 'testid')
        data.save()
        id = data['_id']
        answer = ('<tr class="bottle exchange"><th><a href="/data/{id}">BOT'
                  '</a></th><td>ASCII .csv bottle data with station '
                  'information</td></tr>').format(id=id)
        self.assertEquals(data_file_link('bottle_exchange', data), answer)
        answer = ('<tr class="ctdzip exchange"><th><a href="/data/{id}">CTD'
                  '</a></th><td>ZIP archive of ASCII .csv CTD data with '
                  'station information</td></tr>').format(id=id)
        self.assertEquals(data_file_link('ctdzip_exchange', data), answer)
        data.remove()

        data = Attr(self.testPerson, 'a', 'b', 'testid')
        data.save()
        self.assertRaises(ValueError, lambda: data_file_link('ctdzip_exchange', data))
        data.remove()


class TestView(unittest.TestCase):
    def tearDown(self):
        testing.tearDown()

    def test__collapse_dict(self):
        """ Collapse a dictionary tree based on a given value being invalid. """
        from pycchdo.views import _collapsed_dict
        d = {}
        self.assertEquals(_collapsed_dict(d, 1), 1)
        d = {'a': 1, 'b': None}
        self.assertEquals(_collapsed_dict(d), {'a': 1})
        d = {'a': 1, 'b': None, 'c': {'d': None, 'e': 2}}
        self.assertEquals(_collapsed_dict(d), {'a': 1, 'c': {'e': 2}})
        d = {'a': 1, 'b': 1, 'c': {'d': 1, 'e': 1}}
        self.assertEquals(_collapsed_dict(d, 1), 1)

