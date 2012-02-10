import unittest
import datetime
from StringIO import StringIO

from pyramid import testing
from pyramid.config import Configurator

import shapely.geometry.linestring
import shapely.geometry.polygon

from pycchdo.models.models import mongodoc, collectablemongodoc, Stamp, Obj, _Change, \
                                  _Attr, Note, Country, Cruise, Person

from . import *


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
        self.assertTrue(change.creation_stamp.timestamp >= before)
        self.assertTrue(change.creation_stamp.timestamp <= after)
        self.assertTrue(change.pending_stamp is None)
        self.assertTrue(change.judgment_stamp is None)
        self.assertFalse(change.accepted)

        change1 = _Change(
            self.testPerson,
            note=Note(self.testPerson, 'body', 'action', 'data_type',
                      'subject'))
        change1.save()
        note = change1.notes[0]
        self.assertEqual(note.action, 'action')
        self.assertEqual(note.data_type, 'data_type')
        self.assertEqual(note.subject, 'subject')
        self.assertEqual(note.body, 'body')
        change1.remove()

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
        self.assertEquals([], o.accepted_tracked())
        o.set('a', 'b', self.testPerson)
        self.assertEquals([], o.accepted_tracked())
        _Attr.map_mongo(o.history()[0]).accept(self.testPerson)
        self.assertEquals([_Attr.map_mongo(o.history()[0])], o.accepted_tracked())
        o.remove()

    def test_Attrs_keys(self):
        """ Accepted keys """
        o = Obj(self.testPerson)
        o.save()
        self.assertEquals([], o.attr_keys)
        o.set('a', 'b', self.testPerson)
        _Attr.map_mongo(o.history()[0]).accept(self.testPerson)
        self.assertEquals(['a'], o.attr_keys)
        o.remove()

    def test_Attrs_get_scalar(self):
        """ Getting a scalar value in _Attr should return the latest accepted
        value.

        """
        obj = Obj(self.testPerson)
        obj.save()

        key = 'a'
        obj.set(key, '0', self.testPerson)
        obj.set(key, '1', self.testPerson)
        obj.set(key, '2', self.testPerson)

        self.assertEquals(None, obj.get(key))
        _Attr.map_mongo(obj.history(key, value='1')[0]).accept(self.testPerson)
        self.assertEquals(obj.get(key), '1')
        _Attr.map_mongo(obj.history(key, value='2')[0]).accept(self.testPerson)
        self.assertEquals(obj.get(key), '2')
        _Attr.map_mongo(obj.history(key, value='0')[0]).accept(self.testPerson)
        self.assertEquals(obj.get(key), '0')
        obj.delete(key, self.testPerson)
        obj.unacknowledged_tracked()[0].accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

        obj.remove()

    def test_Attrs_get_default(self):
        """ Getting a non-existant value should return default. """
        obj = Obj(self.testPerson)
        obj.save()

        self.assertEquals(obj.get('a'), None)
        self.assertEquals(obj.get('a', 'b'), 'b')

        obj.remove()

    def test_Attrs_set_scalar(self):
        """ Setting a scalar value in _Attr should create a new _Attr.
        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
        obj = Obj(self.testPerson)
        obj.save()
        key = 'a'
        value = '0'
        obj.set(key, value, self.testPerson)
        self.assertEquals(None, obj.get(key))
        history = obj.history(key)
        last_attr = _Attr.map_mongo(history)[0]
        self.assertEquals(last_attr['value'], value)
        last_attr.accept(self.testPerson)
        self.assertEquals(obj.get(key), value)

        value1 = '1'
        obj.set(key, value1, self.testPerson)
        self.assertEquals(obj.get(key), value)
        obj.unacknowledged_tracked()[0].accept(self.testPerson)
        self.assertEquals(obj.get(key), value1)

        obj.delete(key, self.testPerson)
        self.assertEquals(obj.get(key), value1)
        obj.unacknowledged_tracked()[0].accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

        obj.remove()

    def test_Attrs_delete(self):
        """ Deleting an _Attr will write a new _Attr with its deleted attribute
        True. It will no longer appear in the current key value pairs.

        This maintains the history of the _Attr and differentiates a None
        value and deletion.
        """
        obj = Obj(self.testPerson)
        obj.save()

        obj.set('a', 'b', self.testPerson).accept(self.testPerson)
        self.assertTrue('a' in obj.attr_keys)
        obj.delete('a', self.testPerson).accept(self.testPerson)
        self.assertFalse('a' in obj.attr_keys)

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
        attr = _Attr(self.testPerson, obj['_id'], 'a', '0')
        attr.save()
        self.assertEqual(_Attr.map_mongo(_Attr.find({'obj': obj['_id']}))[0]['_id'], attr['_id'])
        obj.remove()
        self.assertEqual(_Attr.find({'obj': obj['_id']}).count(True), 0)

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
            note = obj.add_note(Note(self.testPerson, 'test note'))
            self.assertEqual(len(obj.notes), 1)
        finally:
            obj.remove()

    def test_Obj_get_by_attrs(self):
        """ Retrieve objects whose current values for attrs matches the query.

        """
        objs = []
        ans = None
        num = 4
        for i in range(0, num + 1):
            obj = Obj(self.testPerson)
            obj.save()
            obj.accept(self.testPerson)
            obj.set_accept('a', i, self.testPerson)
            obj.set_accept('b', num - i, self.testPerson)
            objs.append(obj)
            if i == num / 2:
                ans = obj

        # TODO(jfields) Attributes can be accepted either as is or with a new
        # value. Make sure no Attrs with value matching but accepted_value not
        # matching are returned.

        try:
            objs_gotten = Obj.get_by_attrs(a=num / 2, b=num / 2)
            obj = objs_gotten[0]
            self.assertEquals(len(objs_gotten), 1)
            self.assertEquals(ans.get('a'), obj.get('a'))
        finally:
            for obj in objs:
                obj.remove()

    def test_new_Attr(self):
        """ New Attrs are instances of _Change """
        o = Obj(self.testPerson)
        o.save()
        attr = _Attr(self.testPerson, o)
        self.assertTrue(isinstance(attr, _Change))
        o.remove()

    def test_Person_new(self):
        """ New people are Objs """
        p = Person(name_first="Ryan", name_last="Tester",
                   institution="Test University", country="Testland",
                   email="test@test.com")
        self.assertTrue(isinstance(p, Obj))

    def test_Person_new_without_id_provider(self):
        """ A new Person without an ID must supply their first and last name.
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

    def test_mongodoc_custom_attrs(self):
        """ Custom attributes for mongodoc
        Editing an attribute that is listed will edit the value as if the
        attribute name were the dictionary key.

        """
        # Get
        doc = mongodoc({'a': 1, 'b': 2})
        self.assertEquals(doc.a, 1)
        self.assertEquals(doc.b, 2)
        self.assertRaises(AttributeError, lambda: doc.c)

        # Set
        doc = mongodoc({'a': 1, 'b': 2})
        self.assertEquals(doc.a, 1)
        doc.a = 3
        self.assertEquals(doc.a, 3)

        # Del
        doc = mongodoc({'a': 1, 'b': 2})
        self.assertEquals(doc.a, 1)
        del doc.a
        self.assertRaises(AttributeError, lambda: doc.a)

    def test_collectablemongodoc_find_id_with_invalid_id_gives_None(self):
        """ Attempting to find an invalid collectablemongodoc gives None. """
        self.assertEquals(None, collectablemongodoc.find_id('invalid_object_id'))

    def test_Obj_map_mongo(self):
        """ An Obj mapped from a mongo doc will have the correct _obj_type """
        id = self.testPerson['_id']
        o = Obj.get_id(id)
        self.assertEquals(o['_obj_type'], 'Person')

    def test_Obj_find_id_with_invalid_id_gives_None(self):
        """ Attempting to find an invalid ObjectId gives None. """
        self.assertEquals(None, Obj.find_id('invalid_object_id'))

    def test_Obj_get_id(self):
        """ Getting an Obj by id will return None if not found """
        self.assertEqual(None, Obj.get_id('invalid_object_id'))

    def test_Obj_finders_find_Objs(self):
        """ Obj finders should find Objs based on their class """
        obj = Obj(self.testPerson)
        obj.save()
        self.assertTrue(Obj.find_one({'_id': obj['_id']}) != None)
        self.assertTrue(Person.find_one({'_id': self.testPerson['_id']}) != None)
        # _id is not the best option here. try finding based on creation_stamp or
        # something. That will show the error.
        # TODO(jfields) also make sure that the class retrieved is correct
        # basically make sure that Obj.find_one is called instead of
        # collectablemongodoc.find_one.
        obj.remove()

    def test_Obj_polymorph(self):
        """ An Obj that has been polymorphed regains the type of the Obj's
            _obj_type """

        # TODO(jfields) test that getting an Obj by id gives the type of Obj.
        # After calling obj.polymorph() the returned new obj is of a subclass of
        # Obj.
        pass

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
        self.assertTrue(type(obj.set('a', 'v', self.testPerson)) is _Attr)
        obj.remove()

    def test_Attr_list(self):
        """ Setting a list on an Obj's attrs stores a list """
        obj = Obj(self.testPerson)
        obj.save()

        a = obj.set('a', [], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a['value']) is list)
        a = obj.set('a', ['b'], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a['value']) is list)
        self.assertTrue(a['value'] == ['b'])

        obj.remove()

    def test_Attr_file_suggesting(self):
        """ Setting an _Attr to some binary data adds a _Attr that has file set
        to True. Such an object must be given some data. It may optionally be
        given
            a MIME type.
        """
        obj = Obj(self.testPerson)
        obj.save()

        file_data = StringIO('this is a test file object\nwith two lines')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')

        a = obj.set('a', file, self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a) is _Attr)
        self.assertTrue(a['file'])
        obj.remove()

    def test_Attr_file_creation(self):
        """ Creating a _Attr with a file stores the file in an object store. """
        file_data = StringIO('this is a test file object\nwith two lines')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')
        note = None

        d = _Attr(self.testPerson, 'testid', 'a', file, note)
        d.save()

        file.file.seek(0)
        self.assertEquals(d.file.read(), file.file.read())
        d.remove()

    def test_Attr_track_suggesting(self):
        """ Setting an _Attr to a track saves the value in track.
        """
        obj = Obj(self.testPerson)
        obj.save()

        a = obj.set('track', [[32, -117], [33, 118]], self.testPerson)
        a.accept(self.testPerson)
        self.assertTrue(type(a) is _Attr)
        self.assertTrue(a['track'])
        obj.remove()

    def test_Attr_accept_value(self):
        """ Accepting an _Attr with an accepted value will change the returned
            value of the Attribute """
        obj = Obj(self.testPerson)
        obj.save()

        a = obj.set('a', 1, self.testPerson)
        self.assertEqual(1, a.value)
        a.accept_value(2, self.testPerson)
        self.assertEqual(2, a.value)

        obj.remove()

    def test_Cruise_has_country(self):
        """ Get a Cruise's country """
        c = Cruise(self.testPerson)
        c.save()
        country = Country(self.testPerson)
        country.save()
        c.set('country', country.id, self.testPerson).accept(self.testPerson)
        self.assertTrue(c.country is not None)
        self.assertTrue(c.country.id, country.id)
        country.remove()
        c.remove()

    def test_Cruise_track(self):
        """ Getting a Cruise's track either gives None or a
        shapely.geometry.linestring.LineString
        
        """
        c = Cruise(self.testPerson)
        c.save()
        t = c.track
        self.assertTrue(t is None)
        c.set('track', [[0, 0], [1, 1]], self.testPerson).accept(self.testPerson)
        t = c.track
        self.assertTrue(t is not None)
        self.assertTrue(type(t) is shapely.geometry.linestring.LineString)
        c.remove()

    def test_Cruise_add_participant(self):
        """ Add participants to a cruise """
        c = Cruise(self.testPerson)
        c.save()
        c.participants.add(self.testPerson, 'Chief Scientist', self.testPerson).accept(self.testPerson)
        self.assertEquals([self.testPerson], [pi['person'] for pi in c.chief_scientists])
        c.participants.add(self.testPerson, 'Co-Chief Scientist', self.testPerson).accept(self.testPerson)
        self.assertEquals([(self.testPerson, 'Chief Scientist'),
                           (self.testPerson, 'Co-Chief Scientist')],
                          c.participants.roles)
        c.remove()

    def test_Cruise_remove_participant(self):
        """ Remove participants from a cruise """
        c = Cruise(self.testPerson)
        c.save()
        c.participants.add(self.testPerson, 'Chief Scientist', self.testPerson).accept(self.testPerson)
        self.assertEquals([self.testPerson], [pi['person'] for pi in c.chief_scientists])
        c.participants.remove(self.testPerson, 'Chief Scientist', self.testPerson).accept(self.testPerson)
        self.assertEquals([], c.participants.roles)
        c.remove()

    def test_Cruise_filter_geo(self):
        """ Filter a list of Cruises by a geo function """
        c0 = Cruise(self.testPerson)
        c0.save()
        c0.set('track', [[0, 0], [0, 1]], self.testPerson).accept(self.testPerson)
        c1 = Cruise(self.testPerson)
        c1.save()
        c1.set('track', [[2, 0], [3, 1]], self.testPerson).accept(self.testPerson)

        cs = Cruise.map_mongo(Cruise.all())

        p0 = shapely.geometry.polygon.Polygon([[-1, -1], [-1, 2], [4, 2], [4, -1], [-1, -1]])
        p1 = shapely.geometry.polygon.Polygon([[1, -1], [1, 2], [4, 2], [4, -1], [1, -1]])

        self.assertEquals(Cruise.filter_geo(p0.intersects, cs), cs)
        self.assertEquals(Cruise.filter_geo(p1.intersects, cs), [cs[1]])

        c0.remove()
        c1.remove()

    def test_Cruise_pending_tracked_data(self):
        """ Retrieve a list of files that make up the data suggestion history
            for the cruise. The model has a map of recognized file types which
            is the basis for which Attrs will be selected for.
                
        """
        c = Cruise(self.testPerson)
        c.save()

        self.assertEquals(c.tracked_data(), [])

        f0 = _mock_FieldStorage('f0_hy1.csv', StringIO('mock_botex'), 'text/csv')
        a0 = c.set('bottle_exchange', f0, self.testPerson)
        a0.accept(self.testPerson)
        self.assertEquals(c.tracked_data(), [a0])

        c.remove()


class TestHelper(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def test_helper_data_file_link(self):
        """ Given an _Attr with a file, provide a link to a file next to its description """
        from pycchdo.helpers import data_file_link
        request = testing.DummyRequest()
        file_data = StringIO('')
        file = _mock_FieldStorage('testfile.txt', file_data, 'text/plain')
        data = _Attr(self.testPerson, 'testid', 'a', file)
        data.obj = self.testPerson.id
        data.save()
        id = data['_id']
        answer = ('<tr class="bottle exchange"><th><a href="/data/b/{id}">BOT'
                  '</a></th><td>ASCII .csv bottle data with station '
                  'information</td></tr>').format(id=id)
        self.assertEquals(data_file_link(request, 'bottle_exchange', data), answer)
        answer = ('<tr class="ctdzip exchange"><th><a href="/data/b/{id}">CTD'
                  '</a></th><td>ZIP archive of ASCII .csv CTD data with '
                  'station information</td></tr>').format(id=id)
        self.assertEquals(data_file_link(request, 'ctdzip_exchange', data), answer)
        data.remove()

        data = _Attr(self.testPerson, 'testid', 'a', 'b')
        data.obj = self.testPerson.id
        data.save()
        self.assertEquals('<tr class="ctdzip exchange"><th><a href="/404.html">CTD'
                          '</a></th><td>ZIP archive of ASCII .csv CTD data with '
                          'station information</td></tr>',
                          data_file_link(request, 'ctdzip_exchange', data))
        data.remove()


class _MockSession:
    def get(self, key, default):
        return 'Mock Session value for', key, default

    def __setitem__(self, key, value):
        print 'Mock set', key, value

    def flash(self, queue, msg):
        print 'Mock Flash', queue, msg

    def peek_flash(self, queue):
        return 'Mock Flash peek for', queue

    def pop_flash(self, queue):
        return 'Mock Flash pop for', queue


class TestView(unittest.TestCase):
    def setUp(self):
        global_setUp(self)
        self.config.include('pyramid_jinja2')
        self.config.add_jinja2_search_path('pycchdo:')
        from pyramid.events import BeforeRender
        import pycchdo
        self.config.add_subscriber(pycchdo.add_renderer_globals, BeforeRender)

    tearDown = global_tearDown

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

    def test_cruise_show(self):
        from pycchdo.views.cruise import cruise_show
        request = testing.DummyRequest()
        result = cruise_show(request)
        self.assertEqual(result.status, '400 Bad Request')

        from pycchdo.models import Cruise

        c = Cruise(self.testPerson)
        c.save()

        request.matchdict['cruise_id'] = c.id
        request.user = None
        # TODO
        result = cruise_show(request)

        c.remove()

    def test_cruise_show_suggest_file(self):
        from pycchdo.views.cruise import cruise_show
        from pycchdo.models import Cruise

        from pyramid.renderers import render_to_response

        c = Cruise(self.testPerson)
        c.save()

        mock_data = StringIO('')
        mock_file = _mock_FieldStorage('mockfile.txt', mock_data, 'plain/text')

        request = testing.DummyRequest()
        request.matchdict['cruise_id'] = c.id
        request.user = self.testPerson
        request.method = 'POST'
        request.params['_method'] = 'PUT'
        request.params['action'] = 'suggest_file'
        request.params['type'] = 'invalid_type'
        request.params['file'] = mock_file

        request.session = _MockSession()

        dictionary = cruise_show(request)

        #response = render_to_response('templates/cruise/show.jinja2',
        #                              cruise_show(request), request=request)
        # TODO test response for recognizing bad type

        c.remove()
