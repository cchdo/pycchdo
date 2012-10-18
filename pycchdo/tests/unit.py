from datetime import datetime

import transaction

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest

import shapely.geometry.linestring
import shapely.geometry.polygon

import geojson

import pycchdo
import pycchdo.models.models as models
from pycchdo.models.models import (
    Session, DBSession,
    String, Integer, LineString, File, TextList, ID, IDList, DateTime, Unicode, 
    Institution, Stamp, Obj, _Change, _Attr, Note, Participant, Participants,
    Country, Cruise, Person, Collection, Ship,
    ArgoFile,
    FSFile,
    )

from . import *


class TestModelChange(PersonBaseTest):
    def test_new(self):
        """Newly created objects have correct values for stamps and notes."""
        before = datetime.utcnow()

        change = _Change(self.testPerson)
        DBSession.add(change)
        DBSession.flush()

        after = datetime.utcnow()
        self.assertTrue(change.creation_stamp.timestamp >= before)
        self.assertTrue(change.creation_stamp.timestamp <= after)
        self.assertFalse(bool(change.pending_stamp))
        self.assertFalse(bool(change.judgment_stamp))
        self.assertFalse(change.accepted)

        change1 = _Change(
            self.testPerson,
            note=Note(
                self.testPerson, 'body', 'action', 'data_type', 'subject'))

        DBSession.add(change1)
        DBSession.flush()

        note = change1.notes[0]
        self.assertEqual(note.action, 'action')
        self.assertEqual(note.data_type, 'data_type')
        self.assertEqual(note.subject, 'subject')
        self.assertEqual(note.body, 'body')

    def test_accept(self):
        """Acceptance of _Change."""
        change = _Change(self.testPerson)
        change.accept(self.testPerson)
        self.assertTrue(change.is_accepted())

    def test_acknowledge(self):
        """Acknowledgement of _Change."""
        change = _Change(self.testPerson)
        change.acknowledge(self.testPerson)
        self.assertTrue(change.is_acknowledged())

    def test_reject(self):
        """Rejection of _Change."""
        change = _Change(self.testPerson)
        change.reject(self.testPerson)
        self.assertTrue(change.is_rejected())

    def test_stamp_properties(self):
        """The stamps should only be available depending on object state."""
        ccc = _Change(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()
        self.assertTrue(ccc.creation_stamp != None)
        self.assertTrue(ccc.pending_stamp == None)
        self.assertTrue(ccc.judgment_stamp == None)
        ccc.acknowledge(self.testPerson)
        self.assertTrue(ccc.pending_stamp != None)
        ccc.accept(self.testPerson)
        self.assertTrue(ccc.judgment_stamp != None)

    def test_state(self):
        """Test _Change state checkers."""
        ccc = _Change(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()
        self.assertFalse(ccc.is_acknowledged())
        self.assertFalse(ccc.is_judged())
        self.assertFalse(ccc.is_accepted())
        self.assertFalse(ccc.is_rejected())
        ccc.acknowledge(self.testPerson)
        self.assertTrue(ccc.is_acknowledged())
        self.assertFalse(ccc.is_judged())
        ccc.accept(self.testPerson)
        self.assertTrue(ccc.is_accepted())
        self.assertFalse(ccc.is_rejected())
        ccc.reject(self.testPerson)
        self.assertTrue(ccc.is_rejected())
        self.assertFalse(ccc.is_accepted())

    def test_has_notes(self):
        """A _Change can have notes added about it.

        Consider a Cruise gets email or someone would like to make an arbitrary
        note about an Institution but aren't sure of its validity.

        """
        obj = _Change(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()

        self.assertTrue(hasattr(obj, 'notes'))
        note = obj.add_note(Note(self.testPerson, 'test note'))
        self.assertEqual(len(obj.notes), 1)


class TestModelAttrValue(PersonBaseTest):
    def test_attrvalue(self):
        iii = Institution(self.testPerson)
        DBSession.add(iii)
        DBSession.flush()
        iii.set_accept('name', 'hello', self.testPerson)
        self.assertEqual('hello', iii.get('name', None))


class TestModelAttr(PersonBaseTest):
    def test_set_returns_attr(self):
        """Setting a value on an Obj returns an _Attr."""
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key = self._testMethodName
        obj.allow_attr(key, String, 'test')

        self.assertTrue(type(obj.set(key, 'v', self.testPerson)) is _Attr)

    def test_new(self):
        """New Attrs are instances of _Change."""
        key = self._testMethodName
        o = Obj(self.testPerson)
        Obj.allow_attr(key, String)
        DBSession.add(o)
        DBSession.flush()

        attr = o.set(key, 'value', self.testPerson)
        self.assertTrue(isinstance(attr, _Change))

    def test_allow_attrs(self):
        """Only allow _Attrs to be set when the key has been allowed."""
        ooo = Obj(self.testPerson)
        key = self._testMethodName
        with self.assertRaises(ValueError):
            ooo.set(key, 'b', self.testPerson)
        Obj.allow_attr(key, String, 'test')
        ooo.set(key, 'b', self.testPerson)

    def test_allow_attrs_polymorph(self):
        """Only allow _Attrs to be set when the key has been allowed on the
        specific class or its parents.

        """
        # This test is currently moot because there are no inherited classes
        # between Obj and leaf Objs.

        #key = self._testMethodName
        #Obj.allow_attr(key, String)
        #ccc = Collection(self.testPerson)
        #ccc.set(key, 'test', self.testPerson)

        #ooo = Obj(self.testPerson)
        #with self.assertRaises(ValueError):
        #    ooo.set(key, 'test', self.testPerson)
        pass

    def test_accepted_changes(self):
        """Accepted changes."""
        o = Obj(self.testPerson)
        o.allow_attr(self._testMethodName, String, 'test')
        DBSession.add(o)
        DBSession.flush()
        self.assertEquals([], o.accepted_tracked.all())
        aaa = o.set(self._testMethodName, 'b', self.testPerson)
        self.assertEquals([], o.accepted_tracked.all())
        aaa.accept(self.testPerson)
        self.assertEquals([aaa], o.accepted_tracked.all())

    def test_current_attr_keys(self):
        """Current _Attr keys."""
        o = Obj(self.testPerson)
        o.allow_attr(self._testMethodName, String, 'test')
        DBSession.add(o)
        DBSession.flush()
        self.assertEquals([], o.attr_keys)
        aaa = o.set(self._testMethodName, 'b', self.testPerson)
        aaa.accept(self.testPerson)
        self.assertEquals([self._testMethodName], o.attr_keys)

    def test_get_value_by_accept_order(self):
        """Getting a value for key returns the last accepted _Attr's value."""
        key = self._testMethodName
        obj = Obj(self.testPerson)
        obj.allow_attr(key, String, 'test')
        DBSession.add(obj)
        DBSession.flush()

        aaa = obj.set(key, '0', self.testPerson)
        bbb = obj.set(key, '1', self.testPerson)
        ccc = obj.set(key, '2', self.testPerson)

        self.assertEquals(None, obj.get(key))
        bbb.accept(self.testPerson)
        self.assertEquals(obj.get(key), '1')
        ccc.accept(self.testPerson)
        self.assertEquals(obj.get(key), '2')
        aaa.accept(self.testPerson)
        self.assertEquals(obj.get(key), '0')
        obj.delete(key, self.testPerson)
        obj.unacknowledged_tracked.first().accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

    # TOOD test_get_list
    # TOOD test_get_file
    # TOOD test_get_track

    def test_get_default(self):
        """Getting a non-existant value should return default."""
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        self.assertEquals(obj.get('a'), None)
        self.assertEquals(obj.get('a', 'b'), 'b')

    def test_set_multi_type(self):
        """_Attrs may have multiple types."""
        key = self._testMethodName
        Obj.allow_attr(key, [DateTime, Unicode])

        ooo = Obj(self.testPerson)
        DBSession.add(ooo)
        DBSession.flush()

        aaa = ooo.set_accept(key, 'testunicode', self.testPerson)
        self.assertEqual(aaa.value, 'testunicode')

        testdate = datetime.utcnow()
        bbb = ooo.set_accept(key, testdate, self.testPerson)
        self.assertEqual(bbb.value, testdate)

    def test_find_multi_type(self):
        """_Attrs may be searched by multiple types."""
        key = self._testMethodName
        Obj.allow_attr(key, [DateTime, Unicode])
        testdate = datetime.utcnow()

        ooo = Obj(self.testPerson)
        DBSession.add(ooo)
        DBSession.flush()

        ooo.accept(self.testPerson)
        aaa = ooo.set_accept(key, testdate, self.testPerson)
        DBSession.add(ooo)
        DBSession.flush()
        ooo_id = ooo.id

        ppp = Obj.get_one_by_attrs({key: testdate})
        self.assertEquals(ooo_id, ppp.id)

    def test_set_scalar(self):
        """Setting a scalar value for _Attr should create a new _Attr.

        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()

        key = self._testMethodName
        key0 = self._testMethodName + '0'
        obj.allow_attr(key, String)
        obj.allow_attr(key0, ID)

        value = '0'
        aaa = obj.set(key, value, self.testPerson)
        self.assertEquals(None, obj.get(key))

        last_attr = obj.attrsq(key, accepted_only=False).first()
        self.assertEquals(last_attr.value, value)

        last_attr.accept(self.testPerson)
        self.assertEquals(value, obj.get(key))

        value1 = '1'
        obj.set(key, value1, self.testPerson)
        self.assertEquals(obj.get(key), value)

        obj.unacknowledged_tracked.first().accept(self.testPerson)
        self.assertEquals(obj.get(key), value1)

        obj.delete(key, self.testPerson)
        self.assertEquals(obj.get(key), value1)
        obj.unacknowledged_tracked.first().accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

        aaa = obj.set_accept(key0, 1, self.testPerson)
        self.assertEquals(aaa.value, 1)

    def test_set_list(self):
        """Setting a list on an Obj's attrs stores a list."""
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key0 = self._testMethodName + '0'
        key1 = self._testMethodName + '1'
        obj.allow_attr(key0, TextList, 'test')
        Obj.allow_attr(key1, IDList, 'testid')

        aaa = obj.set(key0, [], self.testPerson)
        aaa.accept(self.testPerson)
        self.assertEqual(len(aaa.value), 0)

        bbb = obj.set(key0, ['test0', 'test1'], self.testPerson)
        bbb.accept(self.testPerson)
        self.assertEqual(bbb.value, ['test0', 'test1'])

        bbb.value.remove('test0')
        self.assertEquals(bbb.value, ['test1'])

        ccc = obj.set(key1, [1], self.testPerson)
        ccc.accept(self.testPerson)
        self.assertEquals(ccc.value, [1])

        ccc.value.append(2)
        ccc.value.append(3)
        self.assertEqual(ccc.value, [1, 2, 3])

        # order is important
        ddd = obj.set(key0, ['aaa', 'bbb', 'ccc',], self.testPerson)
        ddd.accept_value(['ccc', 'aaa', 'bbb'], self.testPerson)
        self.assertEqual(ddd.value, ['ccc', 'aaa', 'bbb'])

    def test_set_accept(self):
        """Set accept is syntax sugar for immediately accepting the change."""
        key = self._testMethodName
        value = '0'
        Obj.allow_attr(key, String, 'test')

        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()

        aaa = obj.set_accept(key, value, self.testPerson)
        self.assertEquals(value, obj.get(key))

    def test_delete(self):
        """Deleting an _Attr will write a new _Attr with a deleted bit set.

        It will no longer appear in the current key value pairs.

        This maintains the history of the _Attr and differentiates a None
        value and deletion.

        """
        key = self._testMethodName
        Obj.allow_attr(key, String, 'test')

        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()

        obj.set_accept(key, 'b', self.testPerson)
        self.assertTrue(key in obj.attr_keys)
        obj.delete_accept(key, self.testPerson)
        self.assertFalse(key in obj.attr_keys)

    def test_persistence_delete(self):
        key0 = self._testMethodName + '0'
        key1 = self._testMethodName + '1'
        Person.allow_attr(key0, ID)
        Person.allow_attr(key1, IDList)
        p = Person(identifier=key0)
        DBSession.add(p)
        DBSession.flush()
        aaa = p.set_accept(key0, 1, self.testPerson)

        bbb = p.set_accept(key1, [1, 2], self.testPerson)
        DBSession.flush()

        aaa._set(2)
        DBSession.flush()

        bbb._set([3, 4])
        DBSession.flush()

        DBSession.delete(p)
        DBSession.flush()

    def test_accepted_value(self):
        """Accepting an _Attr with an accepted value will change the returned
        value of the Attribute.

        """
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key = self._testMethodName
        obj.allow_attr(key, Integer, 'test')

        a = obj.set(key, 1, self.testPerson)
        self.assertEqual(1, a.value)
        a.accept_value(2, self.testPerson)
        self.assertEqual(2, a.value)

    def test_file_creation(self):
        """Creating an _Attr with a file stores the file in an object store."""
        key = self._testMethodName
        Obj.allow_attr(key, File)
        mockfs = MockFieldStorage(
            MockFile('this is a mult-line test file\nwith \xe6\xb0\xb4',
                     'testfile.txt'), 'text/plain')

        with transaction.manager:
            testPerson = Person(identifier='testid')
            DBSession.add(testPerson)
            DBSession.flush()

            ooo = Obj(testPerson)
            DBSession.add(ooo)
            DBSession.flush()

            ooo.set_accept(key, mockfs, testPerson)
            ooo_id = ooo.id

        with transaction.manager:
            ooo = Obj.query().get(ooo_id)
            aaa_value = ooo.get(key)
            aaa_value = aaa_value.read()
            # TODO have the copy method seek
            mockfs.file.seek(0)
            mock_value = mockfs.file.read()
            self.assertEquals(aaa_value, mock_value)

            DBSession.delete(ooo)

    def test_file_suggesting(self):
        """Setting an _Attr to some binary data.

        Such an object must be given some data. It may optionally be given a
        MIME type.

        """
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key = self._testMethodName
        obj.allow_attr(key, File, 'testfile')

        mockfs = MockFieldStorage(MockFile(
            'this is a mult-line test file\nwith \xe6\xb0\xb4',
            'testfile.txt'), 'text/plain')

        aaa = obj.set(key, mockfs, self.testPerson)
        aaa.accept(self.testPerson)

    def test_track_suggesting(self):
        """Setting an _Attr to a track saves the value in track.

        Tracks may be specified either as a list of tuples, geojson.LineString,
        or shapely.geometry.linestring.LineString.

        """
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key = self._testMethodName
        obj.allow_attr(key, LineString, 'Test Track')

        aaa = obj.set(key, [[32, -117], [33, 118]], self.testPerson)
        aaa = obj.set(
            key,
            shapely.geometry.linestring.LineString([[32, -117], [33, 118]]),
            self.testPerson)
        aaa = obj.set(
            key,
            geojson.LineString([[32, -117], [33, 118]]),
            self.testPerson)


class TestModelObj(PersonBaseTest):
    def test_new(self):
        """New Objs are instances of _Change."""
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        self.assertTrue(isinstance(obj, _Change))

    def test_remove(self):
        """Removing an Obj also removes all Attrs it is associated with."""
        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        key = self._testMethodName
        obj.allow_attr(key, String, 'test')

        attr = obj.set(key, '0', self.testPerson)
        self.assertEqual(obj.attrsq(key, accepted_only=False).first(), attr)

        DBSession.delete(obj)
        DBSession.flush()
        self.assertEqual(_Attr.query().get(attr.id), None)

    def test_get_by_attrs(self):
        """Retrieve objects whose current values for attrs matches the query.

        """
        objs = []
        ans = None
        num = 4
        Obj.allow_attr('a', Integer, 'testa')
        Obj.allow_attr('b', Integer, 'testb')
        for i in range(0, num + 1):
            obj = Obj(self.testPerson)
            DBSession.add(obj)
            DBSession.flush()
            obj.accept(self.testPerson)
            obj.set_accept('a', i, self.testPerson)
            obj.set_accept('b', num - i, self.testPerson)
            objs.append(obj)
            if i == 3:
                ans = obj

        objs_gotten = Obj.get_all_by_attrs({'a': 3, 'b': 1})
        obj = objs_gotten[0]
        self.assertEquals(len(objs_gotten), 1)
        self.assertEquals(ans.get('a'), obj.get('a'))

        objs_gotten = Obj.get_all_by_attrs({'a': 3, 'b': 0})
        self.assertEquals(len(objs_gotten), 0)

    def test_get_by_attrs_list(self):
        """Retrieve Objs whose current values in a list for attrs matches the
        query.

        Lists may be specified.

        """
        key = self._testMethodName
        key0 = key + '0'
        Obj.allow_attr(key, TextList)
        Obj.allow_attr(key0, IDList)

        obj = Obj(self.testPerson)
        DBSession.add(obj)
        DBSession.flush()
        obj.accept(self.testPerson)
        obj.set_accept(key, ['aaa', 'bbb'], self.testPerson)
        obj.set_accept(key0, [1, 2, 3], self.testPerson)

        objs_gotten = Obj.get_all_by_attrs({key: 'aaa'})
        self.assertEquals(len(objs_gotten), 1)

        objs_gotten = Obj.get_all_by_attrs({key: 'bbb'})
        self.assertEquals(len(objs_gotten), 1)

        objs_gotten = Obj.get_all_by_attrs({key: ['aaa', 'bbb']})
        self.assertEquals(len(objs_gotten), 1)

        objs_gotten = Obj.get_all_by_attrs({key: ['bbb', 'aaa']})
        self.assertEquals(len(objs_gotten), 0)

        objs_gotten = Obj.get_all_by_attrs({key0: 1})
        self.assertEquals(len(objs_gotten), 1)

        objs_gotten = Obj.get_all_by_attrs({key: 'aaa', key0: 3})
        self.assertEquals(len(objs_gotten), 1)

        ccc = Collection(self.testPerson)
        ccc.accept(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        aaa = ccc.set_accept('names', ['aaa'], self.testPerson)
        bbb = ccc.set_accept('type', 'ccc', self.testPerson)
        self.assertEqual(
            ccc, Collection.get_one_by_attrs({'type': 'ccc'}))
        DBSession.flush()
        aaa._set(['bbb'])
        bbb._set('ddd')
        DBSession.flush()
        self.assertEqual(
            ccc, Collection.get_one_by_attrs({'names': 'bbb'}))
        self.assertEqual(
            ccc, Collection.get_one_by_attrs({'names': ['bbb']}))
        self.assertEqual(
            ccc, Collection.get_one_by_attrs(
                {'names': ['bbb'], 'type': 'ddd'}))
        self.assertEqual(
            None,
            Collection.get_one_by_attrs(
                {'names': ['bbb'], 'type': 'ccc'}))

    def test_get_by_attrs_accepted_value_match(self):
        """Retrieve objects whose current values for attrs matches the query.

        Attributes can be accepted either as is or with a new value. Make sure
        no Attrs with value matching but accepted_value not matching are
        returned.

        """
        key = self._testMethodName
        ooo = Obj(self.testPerson)
        Obj.allow_attr(key, String, 'test')
        ooo.accept(self.testPerson)
        DBSession.add(ooo)
        DBSession.flush()

        # _AttrMgr need to be accepted before it can be found
        aaa = ooo.set_accept(key, 'first', self.testPerson)

        found = Obj.get_all_by_attrs({key: 'first'})
        self.assertEquals(len(found), 1)

        aaa.accept_value('second', self.testPerson)

        found = Obj.get_all_by_attrs({key: 'second'})
        self.assertEquals(len(found), 1)

        found = Obj.get_all_by_attrs({key: 'first'})
        self.assertEquals(len(found), 0)

        # Make sure it finds the correct _Attr for the most recent value.
        bbb = ooo.set_accept(key, 'third', self.testPerson)
        self.assertEquals(ooo.get(key), 'third')

        found = Obj.get_all_by_attrs({key: 'first'})
        self.assertEquals(len(found), 0)

        found = Obj.get_all_by_attrs({key: 'third'})
        self.assertEquals(len(found), 1)

    def test_polymorphic(self):
        """Queries will return Objs as the most specific subclass.

        E.g. running a query on Obj when there are Cruises and Ship stored
        will return a list with Objs, Cruises and Persons, not just Objs.

        """
        obj = Obj(self.testPerson)
        DBSession.add(obj)

        c = Cruise(self.testPerson)
        DBSession.add(c)

        s = Ship(self.testPerson)
        DBSession.add(s)

        DBSession.flush()

        objs = Obj.query().all()

        types = map(type, objs)

        self.assertTrue(Obj in types)
        self.assertTrue(Cruise in types)
        self.assertTrue(Ship in types)


class TestModelPerson(PersonBaseTest):
    def test_new(self):
        """New people can be given attributes."""
        p = Person(name="Ryan Tester", email="test@test.com")

    def test_is_own_creator(self):
        """A Person is their own creator."""
        ppp = Person(identifier="testid")
        DBSession.add(ppp)
        DBSession.flush()
        pid = ppp.id
        self.assertEqual(pid, ppp.creation_person_id)

        qqq = Person.query().get(pid)
        self.assertEqual(qqq.id, qqq.creation_person_id)

    def test_new_without_id_provider(self):
        """A new Person without an ID must supply their first and last name.

        """
        # Missing name and identifier
        self.assertRaises(ValueError, lambda: Person(email="test@test.com"))

    def test_new_with_id(self):
        """A Person with an ID can supply their own information."""
        p = Person(
            identifier='testid', name="Ryan Tester", email="test@test.com")
        self.assertTrue(p.is_verified())
        self.assertEquals(p.name, 'Ryan Tester')
        self.assertEquals(p.email, 'test@test.com')

    def test_new_with_names(self):
        """New people with names but no name construct their name."""
        p = Person(name_first="Ryan", name_last="Tester", email="test@test.com")
        self.assertEqual(p.name, 'Ryan Tester')

    def test_is_verified(self):
        """If they are associated with an ID provider then they are verified.

        """
        p = Person(name="Ryan Tester", email="test@test.com")
        self.assertFalse(p.is_verified())
        p.identifier = 'testid'
        self.assertTrue(p.is_verified())

    def test_is_required_for_stamp(self):
        """Stamps must be signed off by a Person when a timestamp is given.
        As a composite, Stamps are generated by the mapper when loading objects
        from the database so this cannot be so restrictive.

        """
        self.assertRaises(ValueError, lambda: Stamp(None, 1))
        Stamp(self.testPerson)

    def test_is_authorized(self):
        """See if a person is authorized for the given permissions.

        The authorization logic is basic. Everything is based on groups.

        1. If no groups are requested, nothing is required.
        2. A person is always authorized if they are in the 'staff' group.
        3. A person is authorized if they are in any of the requested groups.

        """
        p = Person(identifier='person')
        DBSession.add(p)
        DBSession.flush()

        self.assertTrue(p.is_authorized([]))

        perms = ['testgroup', ]

        self.assertFalse(p.is_authorized(perms))

        p.permissions = ['nogoodgroup']
        self.assertFalse(p.is_authorized(perms))

        p.permissions = ['testgroup']
        self.assertTrue(p.is_authorized(perms))
        
        p.permissions = ['nogoodgroup', 'testgroup', ]
        self.assertTrue(p.is_authorized(perms))
        
        # Staff users have super powers!
        p.permissions = ['staff', ]
        self.assertTrue(p.is_authorized(perms))


class TestModelCruise(PersonBaseTest):
    def test_has_country(self):
        """Get a Cruise's country."""
        c = Cruise(self.testPerson)
        DBSession.add(c)
        country = Country(self.testPerson)
        DBSession.add(country)
        DBSession.flush()

        c.set_accept('country', country.id, self.testPerson)
        self.assertTrue(c.country is not None)
        self.assertTrue(c.country.id, country.id)

    def test_add_participant(self):
        """Add participants to a cruise."""
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        c.participants.extend(
            c, self.testPerson,
            Participant('Chief Scientist', self.testPerson)
            ).accept(self.testPerson)

        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        c.participants.extend(c, self.testPerson,
            Participant('Co-Chief Scientist', self.testPerson)
            ).accept(self.testPerson)
        self.assertEquals(
            [(self.testPerson, 'Chief Scientist'),
             (self.testPerson, 'Co-Chief Scientist')], c.participants.roles)

    def test_remove_participant(self):
        """Remove participants from a cruise."""
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        ppp = Participant('Chief Scientist', self.testPerson)

        c.participants.extend(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        c.participants.remove(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals([], c.participants.roles)

    def test_replace_participants(self):
        """Replace participants for a cruise."""
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        ppp = Participant('Chief Scientist', self.testPerson)

        c.participants.extend(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        qqq = Participant('Co-Chief Scientist', self.testPerson)

        c.participants.replace(c, self.testPerson, qqq).accept(self.testPerson)
        self.assertEquals(
            [(self.testPerson, 'Co-Chief Scientist')], c.participants.roles)

    def test_replace_participants_attrvalue(self):
        """Replace the participants directly for an _AttrValue."""
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        ppp = Participant('Chief Scientist', self.testPerson)

        c.participants.extend(c, self.testPerson, ppp).accept(self.testPerson)
        DBSession.flush()

        qqq = Participant('Co-Chief Scientist', self.testPerson)

        aaa = c.get_attr('participants')
        aaa._set(Participants([ppp, qqq]))
        self.assertEquals(
            [(self.testPerson, 'Chief Scientist'),
             (self.testPerson, 'Co-Chief Scientist')], c.participants.roles)
        DBSession.flush()

        self.assertEquals(
            1, DBSession.query(models._AttrValueParticipants).count())

    def test_track(self):
        """Getting a Cruise's track either gives None or a
        shapely.geometry.linestring.LineString.
        
        """
        coords = [(0.0, 0.0), (1.0, 1.0)]
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()
        t = c.track
        self.assertTrue(t is None)
        c.set_accept('track', coords, self.testPerson)
        t = c.track
        self.assertTrue(t is not None)
        self.assertTrue(type(t) is shapely.geometry.linestring.LineString)
        self.assertEquals(coords, list(t.coords))

    def test_filter_geo(self):
        """Filter a list of Cruises by a geo function."""
        c0 = Cruise(self.testPerson)
        DBSession.add(c0)

        c1 = Cruise(self.testPerson)
        DBSession.add(c1)

        DBSession.flush()

        c0.set_accept('track', [[0, 0], [0, 1]], self.testPerson)
        c1.set_accept('track', [[2, 0], [3, 1]], self.testPerson)

        cs = Cruise.query().all()

        p0 = shapely.geometry.polygon.Polygon(
            [[-1, -1], [-1, 2], [4, 2], [4, -1], [-1, -1]])
        p1 = shapely.geometry.polygon.Polygon(
            [[1, -1], [1, 2], [4, 2], [4, -1], [1, -1]])

        self.assertEquals(Cruise.filter_geo(p0.intersects, cs), cs)

        self.assertEquals(
            Cruise.filter_geo(
                lambda t: p1.intersects(t) or p1.contains(t), cs),
            [c1])

    def test_pending_tracked_data(self):
        """Retrieve a list of files that make up the data suggestion history for
        the cruise. The model has a map of recognized file types which is the
        basis for which Attrs will be selected for.
                
        """
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        self.assertEquals(c.tracked_data.all(), [])

        f0 = MockFieldStorage(MockFile('mock_botex', 'f0_hy1.csv'), 'text/csv')
        a0 = c.set_accept('bottle_exchange', f0, self.testPerson)

        self.assertEquals(c.tracked_data.all(), [a0])

    def test_files(self):
        """cruise.files should be a dict mapping data_file_human_names to the
        actual value for that cruise.

        """
        c = Cruise(self.testPerson)
        DBSession.add(c)
        DBSession.flush()

        mockbotex = MockFieldStorage(MockFile('botex', 'botex_hy1.csv'))
        mockctdzipnc = MockFieldStorage(
            MockFile('ctdzipnc', 'ctdzip_nc_ctd.zip'))
        mockdocpdf = MockFieldStorage(MockFile('docpdf', 'do.pdf'))

        c.set_accept('bottle_exchange', mockbotex, self.testPerson)
        c.set_accept('ctdzip_netcdf', mockctdzipnc, self.testPerson)
        c.set_accept('doc_pdf', mockdocpdf, self.testPerson)

        files = c.files
        self.assertEquals(set(files.keys()), set([
            'bottle_exchange', 'ctdzip_netcdf', 'doc_pdf', ]))

        # TODO why does this need to happen? copies? something
        botexdata = files['bottle_exchange'].file.read()
        mockbotex.file.seek(0)
        mockbotexdata = mockbotex.file.read()
        ctdzipncdata = files['ctdzip_netcdf'].file.read()
        mockctdzipnc.file.seek(0)
        mockctdzipncdata = mockctdzipnc.file.read()
        docpdfdata = files['doc_pdf'].file.read()
        mockdocpdf.file.seek(0)
        mockdocpdfdata = mockdocpdf.file.read()

        self.assertEquals(
            botexdata, mockbotexdata)
        self.assertEquals(
            ctdzipncdata, mockctdzipncdata)
        self.assertEquals(
            docpdfdata, mockdocpdfdata)

    def test_collections(self):
        """Collections should return all the collections associated with
        cruise.

        """
        c0 = Collection(self.testPerson)
        DBSession.add(c0)
        cr0 = Cruise(self.testPerson)
        DBSession.add(cr0)
        DBSession.flush()

        cr0.set_accept('collections', [c0.id], self.testPerson)

        self.assertEquals(cr0.collections, [c0])


class TestModelCruiseAssociate(PersonBaseTest):
    def test_cruises(self):
        """CruiseAssociates provide a way to get the associated cruises."""
        sss = Ship(self.testPerson)
        ccc = Cruise(self.testPerson)
        ccc.accept(self.testPerson)
        DBSession.add(sss)
        DBSession.add(ccc)
        DBSession.flush()
        ccc.set_accept('ship', sss.id, self.testPerson)
        self.assertEqual(sss.cruises(), [ccc])

        ooo = Collection(self.testPerson)
        ddd = Cruise(self.testPerson)
        DBSession.add(ooo)
        DBSession.add(ddd)
        DBSession.flush()
        ddd.set_accept('collections', [ooo.id], self.testPerson)
        ccc.set_accept('collections', [ooo.id], self.testPerson)
        self.assertEqual(ooo.cruises(), [ccc])

        ddd.accept(self.testPerson)
        self.assertEqual(ooo.cruises(), [ccc, ddd])


class TestModelCollection(PersonBaseTest):
    def test_names(self):
        """Collections may have multiple names.

        The first name takes precedence.

        """
        ccc = Collection(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        n0 = 'collnameA'
        n1 = 'collnameB'
        names = [n0, n1]

        ccc.set_accept('names', names, self.testPerson)

        self.assertEqual(ccc.names, names)
        self.assertEqual(ccc.name, n0)

    def test_names_order(self):
        """Collections may have multiple names with which order matters."""
        ccc = Collection(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        n0 = u'collnameA'
        n1 = u'collnameB'
        n2 = u'collnameC'
        names = [n2, n0, n1]

        ccc.set_accept('names', names, self.testPerson)

        self.assertEqual(ccc.names, names)
        self.assertEqual(ccc.name, n2)

    def test_merge(self):
        """Collections can be merged.
        Collections that are merged together should have:

        * names from both Collections, retained in the same order with
          preference given to the original.
        * the type from the original Collection unless it doesn't have one and
          the mergee does.
        * the cruises from both collections. The cruises will also have their
          collections updated to reflect the deletion of the old collection.

        The mergee is deleted.

        """
        c0 = Collection(self.testPerson)
        c1 = Collection(self.testPerson)
        DBSession.add(c0)
        DBSession.add(c1)
        DBSession.flush()

        c0.set_accept('names', [u'collnameA', u'collnameB'], self.testPerson)
        c1.set_accept('names', [u'collnameC', u'collnameB'], self.testPerson)
        c0.set_accept('type', u'group', self.testPerson)
        c1.set_accept('type', u'WOCE line', self.testPerson)
        c0.set_accept('basins', [u'basinA', u'basinB'], self.testPerson)
        c1.set_accept('basins', [u'basinC', u'basinB'], self.testPerson)

        cr0 = Cruise(self.testPerson)
        cr1 = Cruise(self.testPerson)
        DBSession.add(cr0)
        DBSession.add(cr1)
        DBSession.flush()

        cr0.set_accept('collections', [c1.id], self.testPerson)
        cr1.set_accept('collections', [c0.id, c1.id], self.testPerson)

        c0.merge(self.testPerson, c1)

        self.assertEquals(
            c0.get('names'), ['collnameA', 'collnameB', 'collnameC'])
        self.assertEquals(c0.get('type'), 'group')
        self.assertEquals(cr0.get('collections'), [c0.id])
        self.assertEquals(cr1.get('collections'), [c0.id])
        self.assertEquals(Collection.query().get(c1.id), None)
        self.assertEquals(
            c0.get('basins'), ['basinA', 'basinB', 'basinC'])

        c2 = Collection(self.testPerson)
        DBSession.add(c2)
        DBSession.flush()

        c2.set_accept('names', ['collnameC'], self.testPerson)

        # Order of names is important
        c2.merge(self.testPerson, c0)
        self.assertEquals(
            c2.get('names'), ['collnameC', 'collnameA', 'collnameB'])
        self.assertEquals(c2.get('type'), 'group')
        self.assertEquals(cr0.get('collections'), [c2.id])
        self.assertEquals(cr1.get('collections'), [c2.id])
        self.assertEquals(Collection.query().get(c0.id), None)


class TestModelFSFile(PersonBaseTest):
    def test_put(self):
        """Putting a file-like object with attributes into the fs returns an id
        to refer to the data.

        """
        file = MockFile('Hello World!', 'filename.txt')
        fsfile = FSFile(file, 'filename.txt', 'text/plain')
        DBSession.add(fsfile)
        DBSession.flush()
        self.assertNotEqual(fsfile.fsid, None)

    def test_multiple_files(self):
        """Multiple files in the same transaction.

        Ensure files that are already saved do not try to save again (file may
        be closed already).

        """
        ccc = Cruise(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        key = 'data_suggestion'

        file0 = MockFieldStorage(MockFile('f0', 'f0.txt'))
        attr0 = ccc.attrsq(key, accepted_only=False).\
            order_by(_Attr.creation_timestamp).first()
        if attr0:
            attr0._set(file0)
        else:
            attr0 = ccc.set_accept(key, file0, self.testPerson)
        attr0.attr_value.value.import_id = '0'
        DBSession.flush()
        file0.file.close()
    
        file1 = MockFieldStorage(MockFile('f1', 'f1.txt'))
        attr1 = ccc.attrsq(key, accepted_only=False).\
            order_by(_Attr.creation_timestamp).first()
        if attr1:
            attr1._set(file1)
        else:
            attr1 = ccc.set_accept(key, file1, self.testPerson)
        attr1.attr_value.value.import_id = '1'
        DBSession.flush()
        file1.file.close()

        self.assertEqual(attr0, attr1)
        self.assertEqual(attr1.attr_value.value.file.name, 'f1.txt')
    
    def test_get(self):
        """Get a file-like object with attributes from the fs."""
        file = MockFile('Hello World!', 'filename.txt')
        filename = 'filename.txt'
        content_type = 'text/plain'
        fsfile = FSFile(file, filename, content_type)
        DBSession.add(fsfile)
        DBSession.flush()

        outfile = FSFile.query().get(fsfile.id)
        outfile.seek(0)
        file.seek(0)
        file.read()
        self.assertEqual(outfile.name, filename)
        self.assertEqual(outfile.read(), file.read())

    def test_delete(self):
        """Delete a file-like object with attributes from the fs."""
        file = MockFile('Hello World!', 'filename.txt')
        fsfile = FSFile(file, 'filename.txt', 'text/plain')
        DBSession.add(fsfile)
        DBSession.flush()

        DBSession.delete(fsfile)
        DBSession.flush()

    def test_replace(self):
        """Replace a file-like object."""
        data = self._testMethodName
        fsfile = FSFile.from_fieldstorage(
            MockFieldStorage(
                MockFile(data + '0', 'filename0.txt'), 'text/plain'))
        DBSession.add(fsfile)
        DBSession.flush()
        self.assertNotEqual(fsfile.fsid, None)
        fsid0 = fsfile.fsid

        fsfile.file = MockFile(data + '1', 'filename1.txt')
        DBSession.flush()
        fsfile2 = DBSession.query(FSFile).get(fsfile.id)
        self.assertEqual(data + '1', fsfile2.file.read())

        # Make sure the previous file got deleted
        self.assertNotEqual(fsid0, fsfile2.fsid)


class TestModelArgoFile(PersonBaseTest):
    def test_file(self):
        """ArgoFiles may be given a file to store."""
        data = self._testMethodName
        fff = MockFile(data, 'test_hy1.csv')
        argo = ArgoFile(self.testPerson)
        argo.file = FSFile(fff, 'test_hy1.csv', 'text/csv')
        DBSession.add(argo)
        DBSession.flush()
        argodata = argo.file.read()
        # TODO make argo.file a copy of fff rather than leaving it the same
        fff.seek(0)
        fffdata = fff.read()
        self.assertEqual(argodata, fffdata)
        

    def test_link(self):
        """ArgoFiles may be set to return the most current file holding.

        """
        data = self._testMethodName
        mockfs = MockFieldStorage(MockFile(data, 'test_hy1.csv'), 'text/csv')

        ccc = Cruise(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        ccc.set_accept('bottle_exchange', mockfs, self.testPerson)

        argo = ArgoFile(self.testPerson)
        DBSession.add(argo)
        DBSession.flush()

        argo.link(ccc, 'bottle_exchange')

        # TODO figure out why this needs a seek
        mockfs.file.seek(0)

        argo_str = argo.file.read()
        self.assertEqual(argo_str, data)


class TestHelper(PersonBaseTest):
    def test_helper_data_file_link(self):
        """Given an _Attr with a file, provide a link to a file next to its
        description.

        """
        from pycchdo.helpers import data_file_link
        request = testing.DummyRequest()

        key = self._testMethodName
        Person.allow_attr(key, File)

        file = MockFieldStorage(MockFile('', 'testfile.txt'), 'text/plain')
        data = self.testPerson.set_accept(key, file, self.testPerson)
        DBSession.flush()

        answer = (
            '<tr class="bottle exchange"><th><abbr title="ASCII .csv bottle '
            'data with station information"><a href="/data/b/{id}">Bottle</a>'
            '</abbr></th></tr>').format(id=data.id)
        self.assertEquals(
            data_file_link(request, 'bottle_exchange', data), answer)
        answer = (
            '<tr class="ctdzip exchange"><th><abbr title="ZIP archive of '
            'ASCII .csv CTD data with station information"><a '
            'href="/data/b/{id}">CTD</a></abbr></th></tr>').format(id=data.id)
        self.assertEquals(
            data_file_link(request, 'ctdzip_exchange', data), answer)


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

    def test_cruise_show(self):
        # XXX HACK because route_url doesn't work without route config
        self.config.add_route('cruise_new', 'test')
        from pycchdo.views.cruise import cruise_show
        request = testing.DummyRequest()
        with self.assertRaises(HTTPBadRequest):
            cruise_show(request)

        ccc = Cruise(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        request.matchdict['cruise_id'] = ccc.id
        request.user = None

        result = cruise_show(request)
        # TODO

    def test_cruise_show_suggest_file(self):
        # XXX HACK because route_url doesn't work without route config
        self.config.add_route('cruise_new', 'test')

        from pycchdo.views.cruise import cruise_show
        from pyramid.renderers import render_to_response

        ccc = Cruise(self.testPerson)
        DBSession.add(ccc)
        DBSession.flush()

        mock_file = MockFieldStorage(
            MockFile('', 'mockfile.txt'), 'text/plain')

        request = testing.DummyRequest()
        request.matchdict['cruise_id'] = ccc.id
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
