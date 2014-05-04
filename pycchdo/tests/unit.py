from datetime import datetime, timedelta
from StringIO import StringIO
from cgi import FieldStorage

from nose.tools import nottest

import transaction

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest

import shapely.geometry.linestring
import shapely.geometry.polygon

import geojson

import pycchdo
from pycchdo.models.types import (
    String, Integer, File, TextList, ID, IDList, DateTime, Unicode, 
)
from pycchdo.models.serial import (
    DBSession, store_context,
    LineString, 
    Change, Obj,
    Institution, Note, Participant, Participants,
    Country, Cruise, Person, Collection, Ship, Parameter, ParameterGroup,
    Unit,
    ParameterInformation,
    ArgoFile,
    FSFile,
    Serializer, SerializerFSFile, SerializerDateTime
    )

from . import *


class TestModelChange(PersonBaseTest):
    def test_new_ts(self):
        """Newly created objects have correct values for timestamps."""
        before = datetime.now() - timedelta(seconds=1)
        after = datetime.now() + timedelta(seconds=1)
        change = Obj.propose(self.testPerson)

        self.assertTrue(change.ts_c >= before)
        self.assertTrue(change.ts_c <= after)
        self.assertFalse(change.is_acknowledged())
        self.assertFalse(change.is_judged())
        self.assertFalse(change.accepted)

    def test_accept(self):
        """Acceptance of Change."""
        change = Obj.propose(self.testPerson)
        change.accept(self.testPerson)
        self.assertTrue(change.is_judged())
        self.assertTrue(change.is_accepted())

    def test_acknowledge(self):
        """Acknowledgement of Change."""
        change = Obj.propose(self.testPerson)
        change.acknowledge(self.testPerson)
        self.assertTrue(change.is_acknowledged())
        self.assertFalse(change.is_judged())

    def test_reject(self):
        """Rejection of Change."""
        change = Obj.propose(self.testPerson)
        change.reject(self.testPerson)
        self.assertTrue(change.is_rejected())

    def test_stamp_properties(self):
        """The stamps should only be available depending on object state."""
        ccc = Obj.propose(self.testPerson)
        self.assertTrue(ccc.ts_c != None)
        self.assertTrue(ccc.ts_ack == None)
        self.assertTrue(ccc.ts_j == None)

        ccc.acknowledge(self.testPerson)
        self.assertIsNotNone(ccc.ts_ack)

        ccc.accept(self.testPerson)
        self.assertIsNotNone(ccc.ts_j)

    def test_state(self):
        """Test Change state checkers."""
        ccc = Obj.propose(self.testPerson)
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

    def test_delete(self):
        """Test delete Obj removes the associated Change as well."""
        obj = Obj.propose(self.testPerson).obj
        change = obj.change
        obj.remove()
        self.assertTrue(change not in Change.query().all())

    def test_caching(self):
        """Cached attr values are saved on the Obj."""
        suggcr = Cruise.propose(self.testPerson)
        self.assertEqual(DBSession.query(Cruise).filter(Obj.accepted).all(), [])
        cruise = suggcr.obj
        suggcr.accept(self.testPerson)
        self.assertEqual(DBSession.query(Cruise).filter(Obj.accepted).all(), [cruise])

        correctexpo = 'correctexpo'
        cruise.set(self.testPerson, 'expocode', correctexpo)
        suggexp = cruise.sugg(self.testPerson, 'expocode', 'incorrect')
        suggexp.reject(self.testPerson)
        self.assertEqual(cruise.expocode, correctexpo)

    def test_get_attr_changes(self):
        """Objs have changes, the creation and attr changes."""
        obj = Unit.propose(self.testPerson).obj

        obj.set(self.testPerson, 'name', 'CTDPRS')
        obj.sugg(self.testPerson, 'name', 'CTDOXY')

        self.assertEqual(len(obj.changes()), 2)
        self.assertEqual(len(obj.changes('accepted')), 1)

    def test_has_notes(self):
        """A Change can have notes added about it.

        Use case: a Cruise gets email or someone would like to make an arbitrary
        note about an Institution but aren't sure of its validity.

        """
        obj = Obj.propose(self.testPerson).obj
        note = Note(self.testPerson, 'test note')
        obj.change._notes.append(note)
        # TODO improve notes interface
        self.assertEqual(obj.notes, [note])

    def test_new_note(self):
        """Newly created objects have correct values for notes."""
        change1 = Obj.create(self.testPerson)
        change1._notes.append(Note(
                self.testPerson, 'body', 'action', 'data_type', 'subject'))

        note = change1.obj.notes[0]
        self.assertEqual(note.action, 'action')
        self.assertEqual(note.data_type, 'data_type')
        self.assertEqual(note.subject, 'subject')
        self.assertEqual(note.body, 'body')

    def test_note_discussion(self):
        """Notes can be for discussion only."""
        change1 = Obj.create(self.testPerson)

        note0 = Note(self.testPerson, 'note0', subject='note0s')
        note1 = Note(self.testPerson, 'note1', subject='note1s', discussion=True)
        change1._notes.append(note0)
        change1._notes.append(note1)

        obj = change1.obj

        self.assertEqual(obj.notes, [note0, note1])
        self.assertEqual(obj.notes_public, [note0])
        self.assertEqual(obj.notes_discussion, [note1])


class TestModelAttrValue(PersonBaseTest):
    def test_attrvalue(self):
        iii = Institution.create(self.testPerson).obj
        iii.set(self.testPerson, 'name', 'hello')
        self.assertEqual('hello', iii.get('name', None))


class TestModelParameter(PersonBaseTest):
    def test_creation(self):
        param0 = Parameter.create(self.testPerson).obj
        unit0 = Unit.create(self.testPerson).obj
        unit0.set(self.testPerson, 'name', 'decibars')
        unit0.set(self.testPerson, 'mnemonic', 'DBAR')
        param0.set(self.testPerson, 'name', 'CTDPRS')
        param0.set(self.testPerson, 'full_name', 'CTDPRS')
        param0.set(self.testPerson, 'units', unit0)

    def test_parameter_group(self):
        param0 = Parameter.create(self.testPerson).obj
        pg0 = ParameterGroup.create(self.testPerson).obj
        pg0.set(self.testPerson, 'name', 'Primary')
        pg0.set(self.testPerson, 'order', [param0])
        self.assertEqual(pg0.order, [param0])


class TestModelParameterInformation(PersonBaseTest):
    def test_delete(self):
        engine_loglevel(DEBUG)
        cruise = Cruise.create(self.testPerson).obj
        param = Parameter.create(self.testPerson).obj
        inst = Institution.create(self.testPerson).obj
        pis = [ParameterInformation(param, 'online', self.testPerson, inst, datetime.utcnow())]
        attr = cruise.set(self.testPerson, 'parameter_informations', pis)
        DBSession.flush()
        DBSession.delete(attr)
        DBSession.flush()


class TestModelAttr(PersonBaseTest):
    def test_set_returns_attr(self):
        """Setting a value on an Obj returns an _Attr."""
        obj = Obj.create(self.testPerson).obj
        key = self._testMethodName
        obj.allow_attr(key, String, 'test')

        self.assertTrue(type(obj.set(self.testPerson, key, 'v')) == Change)

    def test_new(self):
        """New Attrs are instances of Change."""
        key = self._testMethodName
        o = Obj.create(self.testPerson).obj
        Obj.allow_attr(key, String)

        attr = o.set(self.testPerson, key, 'value')
        self.assertTrue(isinstance(attr, Change))

    def test_allow_attrs(self):
        """Only allow _Attrs to be set when the key has been allowed."""
        ooo = Obj.create(self.testPerson).obj
        key = self._testMethodName
        with self.assertRaises(ValueError):
            ooo.set(self.testPerson, key, 'b')
        Obj.allow_attr(key, String, 'test')
        Obj.register_serializer_pair(key, Serializer)
        ooo.set(self.testPerson, key, 'b')

    def test_allow_attrs_polymorph(self):
        """Only allow _Attrs to be set when the key has been allowed on the
        specific class or its parents.

        """
        # This test is currently moot because there are no inherited classes
        # between Obj and leaf Objs.

        #key = self._testMethodName
        #Obj.allow_attr(key, String)
        #ccc = Collection.create(self.testPerson).obj
        #ccc.set(key, 'test', self.testPerson)

        #ooo = Obj(self.testPerson)
        #with self.assertRaises(ValueError):
        #    ooo.set(key, 'test', self.testPerson)
        pass

    def test_accepted_changes(self):
        """Accepted changes."""
        o = Obj.create(self.testPerson).obj
        o.allow_attr(self._testMethodName, String, 'test')
        self.assertEquals([], o.changes('accepted'))
        aaa = o.sugg(self.testPerson, self._testMethodName, 'b')
        self.assertEquals([], o.changes('accepted'))
        aaa.accept(self.testPerson)
        self.assertEquals([aaa], o.changes('accepted'))

    def test_current_attr_keys(self):
        """Current _Attr keys."""
        o = Obj.create(self.testPerson).obj
        o.allow_attr(self._testMethodName, String, 'test')
        self.assertEquals([], o.attr_keys)
        aaa = o.set(self.testPerson, self._testMethodName, 'b')
        self.assertEquals([self._testMethodName], o.attr_keys)

    def test_get_value_by_accept_order(self):
        """Getting a value for key returns the last accepted _Attr's value."""
        key = self._testMethodName
        obj = Obj.create(self.testPerson).obj
        obj.allow_attr(key, String, 'test')
        obj.register_serializer_pair(key, Serializer)

        aaa = obj.sugg(self.testPerson, key, '0')
        bbb = obj.sugg(self.testPerson, key, '1')
        ccc = obj.sugg(self.testPerson, key, '2')

        self.assertEquals(None, obj.get(key))
        bbb.accept(self.testPerson)
        self.assertEquals(obj.get(key), '1')
        ccc.accept(self.testPerson)
        self.assertEquals(obj.get(key), '2')
        aaa.accept(self.testPerson)
        self.assertEquals(obj.get(key), '0')
        obj.delete(self.testPerson, key)
        obj.changes_query('unjudged').first().accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

    # TODO test_get_list
    # TODO test_get_file
    # TODO test_get_track

    def test_get_default(self):
        """Getting a non-existant value should return default."""
        obj = Obj.create(self.testPerson).obj
        self.assertEquals(obj.get('a'), None)
        self.assertEquals(obj.get('a', 'b'), 'b')

    # TODO
    @nottest
    def test_set_multi_type(self):
        """_Attrs may have multiple types."""
        key = self._testMethodName
        Obj.allow_attr(key, [DateTime, Unicode])
        Obj.register_serializer_pair(key, SerializerDateTime)

        ooo = Obj.create(self.testPerson).obj

        aaa = ooo.set(self.testPerson, key, 'testunicode')
        self.assertEqual(aaa.value, 'testunicode')

        testdate = datetime.utcnow()
        bbb = ooo.set(self.testPerson, key, testdate)
        self.assertEqual(bbb.value, testdate)

    # TODO test that attrs with multiple types such as date_start can be queried
    # correctly.

    def test_set_scalar(self):
        """Setting a scalar value for _Attr should create a new _Attr.

        The key value pair should not appear in _Attr until accepted.
        The latest accepted key value pair should be the value.
        
        """
        obj = Obj.create(self.testPerson).obj

        key = self._testMethodName
        key0 = self._testMethodName + '0'
        obj.allow_attr(key, String)
        obj.allow_attr(key0, ID)
        obj.register_serializer_pair(key, Serializer)
        obj.register_serializer_pair(key0, Serializer)

        value = '0'
        aaa = obj.sugg(self.testPerson, key, value)
        self.assertEquals(None, obj.get(key))

        last_attr = obj.get_attr_change(key)
        self.assertEquals(last_attr.value, value)

        last_attr.accept(self.testPerson)
        self.assertEquals(value, obj.get(key))

        value1 = '1'
        obj.sugg(self.testPerson, key, value1)
        self.assertEquals(value, obj.get(key))

        obj.changes_query('unjudged').first().accept(self.testPerson)
        self.assertEquals(obj.get(key), value1)

        obj.delete(self.testPerson, key)
        self.assertEquals(obj.get(key), value1)
        obj.changes_query('unjudged').first().accept(self.testPerson)
        self.assertEquals(None, obj.get(key))

        aaa = obj.set(self.testPerson, key0, 1)
        self.assertEquals(aaa.value, 1)

    def test_set_list(self):
        """Setting a list on an Obj's attrs stores a list."""
        obj = Obj.create(self.testPerson).obj
        key0 = self._testMethodName + '0'
        key1 = self._testMethodName + '1'
        obj.allow_attr(key0, TextList, 'test')
        obj.allow_attr(key1, IDList, 'testid')
        obj.register_serializer_pair(key0, Serializer)
        obj.register_serializer_pair(key1, Serializer)

        aaa = obj.set(self.testPerson, key0, [])
        aaa.accept(self.testPerson)
        self.assertEqual(len(aaa.value), 0)

        bbb = obj.set(self.testPerson, key0, ['test0', 'test1'])
        bbb.accept(self.testPerson)
        self.assertEqual(bbb.value, ['test0', 'test1'])

        ccc = obj.set(self.testPerson, key1, [1])
        ccc.accept(self.testPerson)
        self.assertEquals(ccc.value, [1])

        # order is important
        ddd = obj.set(self.testPerson, key0, ['aaa', 'bbb', 'ccc',])
        ddd.accept(self.testPerson, ['ccc', 'aaa', 'bbb'])
        self.assertEqual(ddd.value, ['ccc', 'aaa', 'bbb'])

    def test_set_accept(self):
        """Set accept is syntax sugar for immediately accepting the change."""
        key = self._testMethodName
        value = '0'
        Obj.allow_attr(key, String, 'test')

        obj = Obj.create(self.testPerson).obj

        aaa = obj.set(self.testPerson, key, value)
        self.assertEquals(value, obj.get(key))

    def test_persistence_delete(self):
        """Changing the value for an _Attr causes persistence delete."""
        key0 = self._testMethodName + '0'
        key1 = self._testMethodName + '1'
        Person.allow_attr(key0, ID)
        Person.register_serializer_pair(key0, Serializer)
        Person.allow_attr(key1, IDList)
        Person.register_serializer_pair(key1, Serializer)
        p = Person.create().obj
        p.set_id_names(identifier=key0)

        aaa = p.set(self.testPerson, key0, 1)
        bbb = p.set(self.testPerson, key1, [1, 2])

        # TODO test that database will delete orphaned list elements

        DBSession.delete(p)

    def test_accepted_value(self):
        """Accepting an _Attr with an accepted value will change the returned
        value of the Attribute.

        """
        obj = Obj.create(self.testPerson).obj
        key = self._testMethodName
        obj.allow_attr(key, Integer, 'test')
        obj.register_serializer_pair(key, Serializer)

        a = obj.set(self.testPerson, key, 1)
        self.assertEqual(1, a.value)
        a.accept(self.testPerson, 2)
        self.assertEqual(2, a.value)

    def test_file_creation(self):
        """Creating an _Attr with a file stores the file in an object store."""
        key = self._testMethodName
        Obj.allow_attr(key, File)
        Obj.register_serializer_pair(key, SerializerFSFile)
        data = 'this is a mult-line test file\nwith \xe6\xb0\xb4'
        mockfs = MockFieldStorage(
            MockFile(data, 'testfile.txt'), contentType='text/plain')

        with transaction.manager:
            testPerson = Person.create().obj
            testPerson.set_id_names(identifier='testid')

            ooo = Obj.create(testPerson).obj
            ooo.set(testPerson, key, mockfs)
            ooo_id = ooo.id

        with transaction.manager:
            ooo = Obj.query().get(ooo_id)
            aaa_value = ooo.get(key)
            aaa_value = aaa_value.open_file().read()
            self.assertEquals(aaa_value, data)

            DBSession.delete(ooo)

    def test_file_suggesting(self):
        """Setting an _Attr to some binary data.

        Such an object must be given some data. It may optionally be given a
        MIME type.

        """
        obj = Obj.create(self.testPerson).obj
        key = self._testMethodName
        obj.allow_attr(key, File, 'testfile')
        obj.register_serializer_pair(key, SerializerFSFile)

        mockfs = MockFieldStorage(MockFile(
            'this is a mult-line test file\nwith \xe6\xb0\xb4',
            'testfile.txt'), contentType='text/plain')

        aaa = obj.set(self.testPerson, key, mockfs)

    # FIXME
    @nottest
    def test_track_suggesting(self):
        """Setting an _Attr to a track saves the value in track.

        Tracks may be specified either as a list of tuples, geojson.LineString,
        or shapely.geometry.linestring.LineString.

        """
        obj = Obj.create(self.testPerson).obj
        key = self._testMethodName
        obj.allow_attr(key, LineString, 'Test Track')

        aaa = obj.set(self.testPerson, key, [[32, -117], [33, 118]])
        aaa = obj.set(
            self.testPerson, key,
            shapely.geometry.linestring.LineString([[32, -117], [33, 118]]))
        aaa = obj.set(
            self.testPerson, key,
            geojson.LineString([[32, -117], [33, 118]]))


class TestModelObj(PersonBaseTest):
    def test_new(self):
        """New Objs have a Change."""
        obj = Obj.create(self.testPerson).obj
        self.assertTrue(isinstance(obj.change, Change))

    def test_remove(self):
        """Removing an Obj also removes all Attrs it is associated with."""
        obj = Obj.create(self.testPerson).obj
        key = self._testMethodName
        obj.allow_attr(key, String, 'test')

        attr = obj.set(self.testPerson, key, '0')
        self.assertEqual(obj.get_attr_change(key), attr)

        DBSession.delete(obj)
        DBSession.flush()
        self.assertEqual(Change.query().get(attr.id), None)

    @nottest
    def test_get_all_by_attrs(self):
        """Retrieve objects whose current values for attrs matches the query.

        """
        objs = []
        ans = None
        num = 4
        Obj.allow_attr('a', Integer, 'testa')
        Obj.register_serializer_pair('a', Serializer)
        Obj.allow_attr('b', Integer, 'testb')
        Obj.register_serializer_pair('b', Serializer)
        for i in range(0, num + 1):
            obj = Obj.create(self.testPerson).obj
            obj.set(self.testPerson, 'a', i)
            obj.set(self.testPerson, 'b', num - i)
            objs.append(obj)
            if i == 3:
                ans = obj

        objs_gotten = Obj.get_all_by_attrs({'a': 3, 'b': 1})
        obj = objs_gotten[0]
        self.assertEquals(len(objs_gotten), 1)
        self.assertEquals(ans.get('a'), obj.get('a'))

        objs_gotten = Obj.get_all_by_attrs({'a': 3, 'b': 0})
        self.assertEquals(len(objs_gotten), 0)

    @nottest
    def test_get_all_by_attrs_list(self):
        """Retrieve Objs whose current values in a list for attrs matches the
        query.

        Lists may be specified.

        """
        key = self._testMethodName
        key0 = key + '0'
        Obj.allow_attr(key, TextList)
        Obj.register_serializer_pair(key, Serializer)
        Obj.allow_attr(key0, IDList)
        Obj.register_serializer_pair(key0, Serializer)

        obj = Obj.create(self.testPerson).obj
        obj.set(self.testPerson, key, ['aaa', 'bbb'])
        obj.set(self.testPerson, key0, [1, 2, 3])

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

        ccc = Collection.create(self.testPerson).obj

        aaa = ccc.set(self.testPerson, 'names', ['aaa'])
        bbb = ccc.set(self.testPerson, 'type', 'ccc')
        self.assertEqual(
            ccc, Collection.get_one_by_attrs({'type': 'ccc'}))
        aaa._set(['bbb'])
        bbb._set('ddd')

        DBSession.flush()

        log.warn([c.key for c in CacheObjAttrs.query().all()])

        ccc._clear_cache_attrs_current()
        CacheObjAttrs.cache(ccc)
        DBSession.flush()

        log.warn([c.key for c in CacheObjAttrs.query().all()])

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

    @nottest
    def test_all_get_by_attrs_accepted_value_match(self):
        """Retrieve objects whose current values for attrs matches the query.

        Attributes can be accepted either as is or with a new value. Make sure
        no Attrs with value matching but accepted_value not matching are
        returned.

        """
        key = self._testMethodName
        ooo = Obj.create(self.testPerson).obj
        Obj.allow_attr(key, String, 'test')

        # _AttrMgr need to be accepted before it can be found
        aaa = ooo.set(self.testPerson, key, 'first')

        ound = Obj.get_all_by_attrs({key: 'first'})
        self.assertEquals(len(found), 1)

        aaa.accept_value('second', self.testPerson)

        found = Obj.get_all_by_attrs({key: 'second'})
        self.assertEquals(len(found), 1)

        found = Obj.get_all_by_attrs({key: 'first'})
        self.assertEquals(len(found), 0)

        # Make sure it finds the correct _Attr for the most recent value.
        bbb = ooo.set(self.testPerson, key, 'third')
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
        obj = Obj.create(self.testPerson).obj
        c = Cruise.create(self.testPerson).obj
        s = Ship.create(self.testPerson).obj

        objs = Obj.query().all()

        types = map(type, objs)

        self.assertTrue(Obj in types)
        self.assertTrue(Cruise in types)
        self.assertTrue(Ship in types)

    def test_mtime(self):
        cruise = Cruise.create(self.testPerson).obj
        cruise.mtime


# TODO decide whether get_all_by_attrs is needed or not. If handling all queries
# with cache attributes, then probably not needed. Check whether seahunt queries
# will need it?

class TestModelPerson(PersonBaseTest):
    def test_new(self):
        """New people can be given attributes."""
        p = Person(name="Ryan Tester", email="test@test.com")

    def test_is_own_creator(self):
        """A Person is their own creator."""
        ppp = Person.create().obj
        ppp.set_id_names(identifier="testid")
        self.assertEqual(ppp, ppp.change.p_c)

        qqq = Person.query().get(ppp.id)
        self.assertEqual(qqq, qqq.change.p_c)

    def test_new_without_id_provider(self):
        """A new Person without an ID must supply their first and last name.

        """
        # Missing name and identifier
        with self.assertRaises(ValueError):
            ppp = Person()
            ppp.set_id_names()

    def test_new_with_id(self):
        """A Person with an ID can supply their own information."""
        p = Person(
            identifier='testid', name="Ryan Tester", email="test@test.com")
        self.assertTrue(p.is_verified())
        self.assertEquals(p.name, 'Ryan Tester')
        self.assertEquals(p.email, 'test@test.com')

    def test_new_with_names(self):
        """New people with names but no name construct their name."""
        ppp = Person.create().obj
        ppp.set_id_names(name_first="Ryan", name_last="Tester")
        ppp.email = "test@test.com"
        self.assertEqual(ppp.name, 'Ryan Tester')

    def test_is_verified(self):
        """If they are associated with an ID provider then they are verified.

        """
        p = Person(name="Ryan Tester", email="test@test.com")
        self.assertFalse(p.is_verified())
        p.identifier = 'testid'
        self.assertTrue(p.is_verified())

    def test_is_authorized(self):
        """See if a person is authorized for the given permissions.

        The authorization logic is basic. Everything is based on groups.

        1. If no groups are requested, nothing is required.
        2. A person is always authorized if they are in the 'staff' group.
        3. A person is authorized if they are in any of the requested groups.

        """
        ppp = Person.create().obj

        self.assertTrue(ppp.is_authorized([]))

        perms = ['testgroup', ]

        self.assertFalse(ppp.is_authorized(perms))

        ppp.permissions = ['nogoodgroup']
        self.assertFalse(ppp.is_authorized(perms))

        ppp.permissions = ['testgroup']
        self.assertTrue(ppp.is_authorized(perms))
        
        ppp.permissions = ['nogoodgroup', 'testgroup', ]
        self.assertTrue(ppp.is_authorized(perms))
        
        # Staff users have super powers!
        ppp.permissions = ['staff', ]
        self.assertTrue(ppp.is_authorized(perms))

    def test_attr_permissions(self):
        """Attributes may have read/write permissions restrictions.

        """
        ccc = Cruise.create(self.testPerson).obj

        fst = MockFieldStorage(
            MockFile('asdf_hy1.csv', 'BOTTLE,12345'))
        attr = ccc.set(self.testPerson, 'archive', fst)
        attr.permissions_read = ['argo']

        argo = Person.create().obj
        argo.permissions = ['argo']

        staff = Person.create().obj
        staff.permissions = ['staff']

        self.assertFalse(self.testPerson.is_authorized(attr.permissions_read))
        self.assertTrue(argo.is_authorized(attr.permissions_read))

        # Staff has superpowers and can read anything
        self.assertTrue(staff.is_authorized(attr.permissions_read))


class TestModelCruise(PersonBaseTest):
    def test_cache_files(self):
        ccc = Cruise.create(self.testPerson).obj

        fst = FieldStorage()
        fst.filename = 'testfile'
        contents = 'contents'
        fst.file = StringIO(contents)
        fsf = FSFile.from_fieldstorage(fst)
        ccc.set(self.testPerson, 'bottle_exchange', fsf)
        self.assertEqual(ccc.get('bottle_exchange'), fsf)

    def test_date(self):
        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'date_start', datetime.now())

    def test_track(self):
        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'track', geojson.LineString([(0, 1), (2, 3)]))

    def test_file_store(self):
        ccc = Cruise.create(self.testPerson).obj

        fst = FieldStorage()
        fst.filename = 'testfile'
        contents = 'contents'
        fst.file = StringIO(contents)
        ccc.set(self.testPerson, 'data_suggestion', fst)

        self.assertEqual(contents, ccc.get('data_suggestion').make_blob())

    def test_file_store2(self):
        ccc = Cruise.create(self.testPerson).obj

        fst = FieldStorage()
        fst.filename = 'asdf_hy1.csv'
        contents = 'BOTTLE,123456'
        fst.file = StringIO(contents)
        ccc.set(self.testPerson, 'bottle_exchange', fst)
        self.assertEqual(contents, ccc.get('bottle_exchange').make_blob())
        # TODO test that files get deleted if transaction is rolled back

    def test_accept_replacement(self):
        """It is possible to accept an attr with a replacement value"""
        unit = Unit.create(self.testPerson).obj
        sugg = unit.sugg(self.testPerson, 'name', 'badname')
        sugg.accept(self.testPerson, 'goodname')
        self.assertEqual(sugg.value, sugg.value_accepted)
        self.assertEqual('badname', sugg.value_original)
        self.assertEqual('goodname', sugg.obj.name)

    def test_accept_replacement_file(self):
        """It is possible to accept an attr with a replacement value"""
        data0 = 'BOTTLE,12345'
        mock0 = MockFieldStorage(MockFile(data0, 'asdf_hy1.csv'))
        data1 = 'BOTTLE,98765'
        mock1 = MockFieldStorage(MockFile(data1, 'qwer_hy1.csv'))

        ccc = Cruise.create(self.testPerson).obj

        suggfff = ccc.sugg(self.testPerson, 'bottle_exchange', mock0)
        suggfff.accept(self.testPerson, mock1)

        self.assertEqual(data1, ccc.get('bottle_exchange').make_blob())
        self.assertEqual(data0, ccc.get('bottle_exchange', force_original=True).make_blob())

    def test_file_attrs(self):
        """Get a Cruise's file Changes."""
        ccc = Cruise.create(self.testPerson).obj
        mockctdzipnc = MockFieldStorage(
            MockFile('ctdzipnc', 'ctd_zip_nc_ctd.zip'))
        sugg = ccc.set(self.testPerson, 'ctd_zip_netcdf', mockctdzipnc)
        self.assertEqual(ccc.file_attrs['ctd_zip_netcdf'], sugg)

    def test_has_country(self):
        """Get a Cruise's country."""
        ccc = Cruise.create(self.testPerson).obj
        country = Country.create(self.testPerson).obj

        country.name = 'United States of America'
        country.alpha2 = 'US'
        country.alpha3 = 'USA'

        ccc.set(self.testPerson, 'country', country)
        self.assertTrue(ccc.country is not None)
        self.assertTrue(ccc.country.id, country.id)
        self.assertTrue(ccc.country.name, country.name)
        self.assertTrue(ccc.country.alpha2, country.alpha2)
        self.assertTrue(ccc.country.alpha3, country.alpha3)

        self.assertEqual(
            country, Country.query().filter(Country.alpha3 == 'USA').first())

    def test_country_has_people(self):
        country = Country.create(self.testPerson).obj
        ppp = Person.create().obj
        ppp.set(self.testPerson, 'country', country)
        self.assertEqual(country.people, [ppp])

    @nottest
    def test_track(self):
        """Getting a Cruise's track either gives None or a
        shapely.geometry.linestring.LineString.
        
        """
        coords = [(0.0, 0.0), (1.0, 1.0)]
        c = Cruise.create(self.testPerson).obj
        t = c.track
        self.assertTrue(t is None)
        c.set(self.testPerson, 'track', coords)
        t = c.track
        self.assertTrue(t is not None)
        self.assertTrue(type(t) is shapely.geometry.linestring.LineString)
        self.assertEquals(coords, list(t.coords))

    @nottest
    def test_filter_geo(self):
        """Filter a list of Cruises by a geo function."""
        c0 = Cruise.create(self.testPerson).obj
        c1 = Cruise.create(self.testPerson).obj

        c0.set(self.testPerson, 'track', [[0, 0], [0, 1]])
        c1.set(self.testPerson, 'track', [[2, 0], [3, 1]])

        cs = [c0, c1]

        p0 = shapely.geometry.polygon.Polygon(
            [[-1, -1], [-1, 2], [4, 2], [4, -1], [-1, -1]])
        p1 = shapely.geometry.polygon.Polygon(
            [[1, -1], [1, 2], [4, 2], [4, -1], [1, -1]])

        self.assertEquals(Cruise.filter_geo(p0.intersects, cs), cs)

        self.assertEquals(
            Cruise.filter_geo(
                lambda t: p1.intersects(t) or p1.contains(t), cs),
            [c1])

    def test_replaced_data(self):
        """Retrieve a list of data that has been accepted with a replacement
        value.  

        """
        c = Cruise.create(self.testPerson).obj

        self.assertEquals(c.changes_data(), [])

        f0 = MockFieldStorage(
            MockFile('mock_btlex', 'f0_hy1.csv'), contentType='text/csv')
        a0 = c.sugg(self.testPerson, 'bottle_exchange', f0)
        f1 = MockFieldStorage(
            MockFile('mock_btlex', 'f1_hy1.csv'), contentType='text/csv')
        a0.accept(self.testPerson, f1)

        f2 = MockFieldStorage(
            MockFile('mock_ctdex', 'f2_ct1.csv'), contentType='text/csv')
        a1 = c.sugg(self.testPerson, 'ctd_exchange', f2)

        self.assertEquals(c.changes_data('pending'), [])
        self.assertEquals(c.changes_data('accepted'), [a0])
        self.assertEquals(c.changes_data('accepted', replaced=True), [a0])

    def test_pending_data(self):
        """Retrieve a list of files that make up the data suggestion history for
        the cruise. The model has a map of recognized file types which is the
        basis for which attr Changes will be selected for.
                
        """
        c = Cruise.create(self.testPerson).obj

        self.assertEquals(c.changes_data(), [])

        f0 = MockFieldStorage(
            MockFile('mock_botex', 'f0_hy1.csv'), contentType='text/csv')
        a0 = c.sugg(self.testPerson, 'bottle_exchange', f0)
        a0.acknowledge(self.testPerson)

        self.assertEquals(c.changes_data('pending'), [a0])
        self.assertEquals(c.changes_data('accepted'), [])

    def test_files(self):
        """cruise.files should be a dict mapping data_file_human_names to the
        actual value for that cruise.

        """
        c = Cruise.create(self.testPerson).obj

        mockbotex = MockFieldStorage(MockFile('btlex', 'btlex_hy1.csv'))
        mockctdzipnc = MockFieldStorage(
            MockFile('ctdzipnc', 'ctdzip_nc_ctd.zip'))
        mockdocpdf = MockFieldStorage(MockFile('docpdf', 'do.pdf'))

        c.set(self.testPerson, 'bottle_exchange', mockbotex)
        c.set(self.testPerson, 'ctd_zip_netcdf', mockctdzipnc)
        c.set(self.testPerson, 'doc_pdf', mockdocpdf)

        files = c.files
        self.assertEquals(set(files.keys()), set([
            'bottle_exchange', 'ctd_zip_netcdf', 'doc_pdf', ]))

        botexdata = files['bottle_exchange'].file.open_file().read()
        ctdzipncdata = files['ctd_zip_netcdf'].file.open_file().read()
        docpdfdata = files['doc_pdf'].file.open_file().read()

        self.assertEquals(botexdata, 'btlex')
        self.assertEquals(ctdzipncdata, 'ctdzipnc')
        self.assertEquals(docpdfdata, 'docpdf')

    def test_collections(self):
        """Collections should return all the collections associated with
        cruise.

        """
        col0 = Collection.create(self.testPerson).obj
        col1 = Collection.create(self.testPerson).obj
        cr0 = Cruise.create(self.testPerson).obj

        cr0.set(self.testPerson, 'collections', [col1, col0])

        self.assertEquals(cr0.collections, [col1, col0])


class TestParticipant(PersonBaseTest):
    def test_set(self):
        """Setting participants."""
        cruise = Cruise.create(self.testPerson).obj
        part0 = Participant.create('chief_scientist', self.testPerson)
        part1 = Participant.create('cochief_scientist', self.testPerson)

        participants = Participants(part0, part1)
        part = cruise.sugg(self.testPerson, 'participants', participants)
        self.assertEqual([], cruise.participants)
        part.accept(self.testPerson)
        self.assertEqual(participants, cruise.participants)

    # TODO figure out how best to do this interface
    @nottest
    def test_add_participant(self):
        """Add participants to a cruise."""
        c = Cruise.create(self.testPerson).obj

        c.participants.extend_(
            c, self.testPerson,
            Participant('Chief Scientist', self.testPerson)
            ).accept(self.testPerson)

        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        c.participants.extend_(c, self.testPerson,
            Participant('Co-Chief Scientist', self.testPerson)
            ).accept(self.testPerson)
        self.assertEquals(
            [(self.testPerson, 'Chief Scientist'),
             (self.testPerson, 'Co-Chief Scientist')], c.participants.roles)

    @nottest
    def test_remove_participant(self):
        """Remove participants from a cruise."""
        c = Cruise.create(self.testPerson).obj

        ppp = Participant('Chief Scientist', self.testPerson)

        c.participants.extend_(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        c.participants.remove_(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals([], c.participants.roles)

    @nottest
    def test_replace_participants(self):
        """Replace participants for a cruise."""
        c = Cruise.create(self.testPerson).obj

        ppp = Participant('Chief Scientist', self.testPerson)

        c.participants.extend_(c, self.testPerson, ppp).accept(self.testPerson)
        self.assertEquals(
            [self.testPerson], [pi.person for pi in c.chief_scientists])

        qqq = Participant('Co-Chief Scientist', self.testPerson)

        c.participants.replace_(c, self.testPerson, qqq).accept(self.testPerson)
        self.assertEquals(
            [(self.testPerson, 'Co-Chief Scientist')], c.participants.roles)

    @nottest
    def test_replace_participants_attrvalue(self):
        """Replace the participants directly for an _AttrValue."""
        c = Cruise.create(self.testPerson).obj

        count_pre = DBSession.query(models._AttrValueParticipants).count()

        ppp = Participant('Chief Scientist', self.testPerson)

        a = c.participants.extend_(c, self.testPerson, ppp)
        a.accept(self.testPerson)
        DBSession.flush()

        qqq = Participant('Co-Chief Scientist', self.testPerson)

        aaa = c.get_attr('participants')
        aaa._set(Participants([ppp, qqq]))
        self.assertEquals(
            [(self.testPerson, 'Chief Scientist'),
             (self.testPerson, 'Co-Chief Scientist')], c.participants.roles)
        DBSession.flush()

        # Make sure only one participants object was added.
        # TODO
        #self.assertEquals(
        #    count_pre + 1,
        #    DBSession.query(models._AttrValueParticipants).count())



class TestModelCruiseAssociate(PersonBaseTest):
    def test_cruises(self):
        """CruiseAssociates provide a way to get the associated cruises."""
        sss = Ship.create(self.testPerson).obj
        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'ship', sss)
        self.assertEqual(sss.cruises, [ccc])

        ooo = Collection.create(self.testPerson).obj
        ddd = Cruise.create(self.testPerson).obj
        dddsugg = ddd.sugg(self.testPerson, 'collections', [ooo])
        ccc.set(self.testPerson, 'collections', [ooo])
        self.assertEqual(ooo.cruises, [ccc])

        dddsugg.accept(self.testPerson)
        self.assertEqual(ooo.cruises, [ccc, ddd])


class TestModelCollection(PersonBaseTest):
    def test_names(self):
        """Collections may have multiple names.

        The first name takes precedence.

        """
        ccc = Collection.create(self.testPerson).obj

        n0 = 'collnameA'
        n1 = 'collnameB'
        names = [n0, n1]

        ccc.set(self.testPerson, 'names', names)

        self.assertEqual(ccc.names, names)
        self.assertEqual(ccc.name, n0)

    def test_names_order(self):
        """Collections may have multiple names with which order matters."""
        ccc = Collection.create(self.testPerson).obj

        n0 = u'collnameA'
        n1 = u'collnameB'
        n2 = u'collnameC'
        names = [n2, n0, n1]

        ccc.set(self.testPerson, 'names', names)

        self.assertEqual(ccc.names, names)
        self.assertEqual(ccc.name, n2)

    def test_basins(self):
        coll1 = Collection.create(self.testPerson).obj
        coll1.set(self.testPerson, 'names', ['000'])
        colbassug = coll1.sugg(self.testPerson, 'basins', [u'southern'])
        self.assertEqual(coll1, Collection.query().filter(
            Collection.names.contains('000')).first())
        self.assertEqual(Collection.query().filter(
            Collection.basins.contains('southern')).count(), 0)
        colbassug.accept(self.testPerson)
        self.assertEqual(coll1, Collection.query().filter(
            Collection.basins.contains('southern')).first())

    @nottest
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
        c0 = Collection.create(self.testPerson).obj
        c1 = Collection.create(self.testPerson).obj

        c0.set(self.testPerson, 'names', [u'collnameA', u'collnameB'])
        c1.set(self.testPerson, 'names', [u'collnameC', u'collnameB'])
        c0.set(self.testPerson, 'type', u'group')
        c1.set(self.testPerson, 'type', u'WOCE line')
        c0.set(self.testPerson, 'basins', [u'basinA', u'basinB'])
        c1.set(self.testPerson, 'basins', [u'basinC', u'basinB'])

        cr0 = Cruise.create(self.testPerson).obj
        cr1 = Cruise.create(self.testPerson).obj

        cr0.set(self.testPerson, 'collections', [c1])
        cr1.set(self.testPerson, 'collections', [c0, c1])

        c0.merge(self.testPerson, c1)

        self.assertEquals(
            c0.get('names'), ['collnameA', 'collnameB', 'collnameC'])
        self.assertEquals(c0.get('type'), 'group')
        self.assertEquals(cr0.get('collections'), [c0])
        self.assertEquals(cr1.get('collections'), [c0])
        DBSession.flush()
        self.assertEquals(Collection.query().get(c1.id), None)
        self.assertEquals(
            c0.get('basins'), ['basinA', 'basinB', 'basinC'])

        c2 = Collection.create(self.testPerson).obj
        c2.set(self.testPerson, 'names', ['collnameC'])

        # Order of names is important
        c2.merge(self.testPerson, c0)
        self.assertEquals(
            c2.get('names'), ['collnameC', 'collnameA', 'collnameB'])
        self.assertEquals(c2.get('type'), 'group')
        self.assertEquals(cr0.get('collections'), [c2])
        self.assertEquals(cr1.get('collections'), [c2])
        DBSession.flush()
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
        self.assertNotEqual(fsfile.id, None)

    @nottest
    def test_multiple_files(self):
        """Multiple files in the same transaction.

        Ensure files that are already saved do not try to save again (file may
        be closed already).

        """
        ccc = Cruise.create(self.testPerson).obj

        key = 'data_suggestion'

        file0 = MockFieldStorage(MockFile('f0', 'f0.txt'))
        attr0 = ccc._filter_changes_attr(ccc._changes, key).\
            order_by(Change.ts_c).first()
        if attr0:
            attr0._set(file0)
        else:
            attr0 = ccc.set(self.testPerson, key, file0)
        attr0.attr_value.value.import_id = '0'
        DBSession.flush()
        file0.file.close()
    
        file1 = MockFieldStorage(MockFile('f1', 'f1.txt'))
        attr1 = ccc._filter_changes_attr(ccc._changes, key).\
            order_by(Change.ts_c).first()
        if attr1:
            attr1._set(file1)
        else:
            attr1 = ccc.set(self.testPerson, key, file1)
        attr1.attr_value.value.import_id = '1'
        DBSession.flush()
        file1.file.close()

        self.assertEqual(attr0, attr1)
        self.assertEqual(attr1.attr_value.value.name, 'f1.txt')
    
    def test_get(self):
        """Get a file-like object with attributes from the fs."""
        content = 'Hello World!'
        file = MockFile(content, 'filename.txt')
        filename = 'filename.txt'
        content_type = 'text/plain'
        fsfile = FSFile(file, filename, content_type)
        DBSession.add(fsfile)
        DBSession.flush()

        outfile = FSFile.query().get(fsfile.id)
        self.assertEqual(outfile.name, filename)
        self.assertEqual(outfile.open_file().read(), content)

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
        # TODO Create a file for a Change. Reassign a different file to the same
        # change. Make sure the original file was deleted from the file store.


class TestModelArgoFile(PersonBaseTest):
    def test_file(self):
        """ArgoFiles may be given a file to store."""
        data = self._testMethodName
        fff = MockFile(data, 'test_hy1.csv')
        argo = ArgoFile.create(self.testPerson).obj
        argo.file = FSFile(fff, 'test_hy1.csv', 'text/csv')
        DBSession.add(argo.file)
        DBSession.flush()
        argodata = argo.value.open_file().read()
        self.assertEqual(argodata, data)
        

    def test_link(self):
        """ArgoFiles may be set to return the most current file holding.

        """
        data = self._testMethodName
        mockfs = MockFieldStorage(
            MockFile(data, 'test_hy1.csv'), 
            contentType='text/csv')

        ccc = Cruise.create(self.testPerson).obj
        ccc.set(self.testPerson, 'bottle_exchange', mockfs)

        argo = ArgoFile.create(self.testPerson).obj
        argo.link(ccc, 'bottle_exchange')
        argo_str = argo.value.open_file().read()
        self.assertEqual(argo_str, data)


class TestHelper(PersonBaseTest):
    def test_helper_data_file_link(self):
        """Given an Change with a file, provide a link to a file next to its
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
        self.config.add_route('cruise_show', 'test')
        from pycchdo.views.cruise import cruise_show
        request = testing.DummyRequest()
        with self.assertRaises(HTTPBadRequest):
            cruise_show(request)

        ccc = Cruise.create(self.testPerson).obj

        request.matchdict['cruise_id'] = ccc.uid
        request.user = None

        result = cruise_show(request)

    def test_cruise_show_suggest_file(self):
        # XXX HACK because route_url doesn't work without route config
        self.config.add_route('cruise_new', 'test')
        self.config.add_route('cruise_show', 'test')

        from pycchdo.views.cruise import cruise_show
        from pyramid.renderers import render_to_response

        ccc = Cruise.create(self.testPerson).obj

        mock_file = MockFieldStorage(
            MockFile('', 'mockfile.txt'), contentType='text/plain')

        request = testing.DummyRequest()
        request.matchdict['cruise_id'] = ccc.uid
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
