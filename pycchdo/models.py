import datetime

import pymongo
from pymongo.objectid import ObjectId
from pymongo.son_manipulator import SONManipulator

mongo_conn = pymongo.Connection()

def init_conn(settings):
    mongo_conn = pymongo.Connection(settings['db_uri'])

def cchdo():
    return mongo_conn.cchdo


def timestamp():
    return datetime.datetime.utcnow()


class mongodoc(dict):
    def copy_keys_from(self, o, keys):
        if not o:
            return
        for key in keys:
            try:
                self[key] = o[key]
            except KeyError:
                pass

    def from_mongo(cls, doc):
        return None

    @classmethod
    def map_mongo(cls, cursor_or_dict):
        """ If the input is a cursor, returns a list. Else returns the mapped
        class instance

        """
        if cursor_or_dict is None:
            return None

        print 'mapping _mongo for', cls, cursor_or_dict

        def get_person(obj_doc):
            try:
                return Stamp.map_mongo(obj_doc['creation_stamp']).person
            except KeyError:
                return cls(None)

        def get_instance(d):
            if cls is Person:
                return cls(identifier='placeholder').from_mongo(d)
            elif cls is Stamp:
                p = Person(identifier='placeholder')
                p['_id'] = 'fake'
                return cls(person=p).from_mongo(d)
            else:
                return cls(get_person(d)).from_mongo(d)

        if type(cursor_or_dict) is dict:
            return get_instance(cursor_or_dict)
        return map(get_instance, cursor_or_dict)


class collectablemongodoc(mongodoc):
    _mongo_collection = cchdo().collectables

    def save(self):
        self['_id'] = self._mongo_collection.save(self)

    def remove(self):
        self._mongo_collection.remove(self['_id'])

    @classmethod
    def all(cls):
        return cls._mongo_collection.find()

    @classmethod
    def find(cls, *args, **kwargs):
        return cls._mongo_collection.find(*args, **kwargs)

    @classmethod
    def find_one(cls, *args, **kwargs):
        return cls._mongo_collection.find_one(*args, **kwargs)

    @classmethod
    def get_id(cls, id):
        if type(id) is not ObjectId:
            id = ObjectId(id)
        return cls.map_mongo(cls._mongo_collection.find_one({'_id': id}))


class Stamp(mongodoc):
    def __init__(self, person):
        self['timestamp'] = timestamp()
        if type(person) is not Person:
            raise TypeError('%r (%s) is not a Person object' % \
                            (person, type(person)))
        try:
            self['person'] = person['_id']
        except KeyError:
            raise ValueError('Person object must be saved first')

    def from_mongo(self, doc):
        super(Stamp, self).from_mongo(doc)
        self.copy_keys_from(doc, ('timestamp', 'person', ))
        return self

    @property
    def person(self):
        return Person.get_id(self['person'])


class Note(mongodoc):
    def __init__(self, action=None, data_type=None, subject=None, body=None):
        self['action'] = action
        self['data_type'] = data_type
        self['subject'] = subject
        self['body'] = body


class _Change(collectablemongodoc):
    _mongo_collection = cchdo().changes

    def __init__(self, person, note=None):
        self['creation_stamp'] = Stamp(person)
        self['pending_stamp'] = None
        self['judgment_stamp'] = None
        self['accepted'] = False
        self['note'] = note

    def from_mongo(self, doc):
        super(_Change, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_id', 'creation_stamp',
                                  'pending_stamp', 'judgment_stamp',
                                  'accepted', 'note', ))
        return self

    def is_judged(self):
        return self['judgment_stamp'] is not None

    def is_acknowledged(self):
        return self['pending_stamp'] is not None

    def is_accepted(self):
        return self.is_judged() and self['accepted']

    def is_rejected(self):
        return self.is_judged() and not self['accepted']

    def accept(self, person):
        self['judgment_stamp'] = Stamp(person)
        self['accepted'] = True
        self.save()

    def acknowledge(self, person):
        if not self['pending_stamp']:
            self['pending_stamp'] = Stamp(person)
            self.save()
            return True
        else:
            return False

    def reject(self, person):
        self['judgment_stamp'] = Stamp(person)
        self['accepted'] = False
        self.save()


class _AttrList(list):
    def __init__(self, L=None):
        if L:
            # TODO
            pass


class Attr(_Change):
    _mongo_collection = cchdo().attrs
    accepted_value = None

    def __init__(self, person, key=None, value=None, obj=None, note=None,
                 deleted=False):
        super(Attr, self).__init__(person)
        self['key'] = key
        self['value'] = value
        self['deleted'] = deleted
        self['obj'] = obj
        self['note'] = note

    def from_mongo(self, doc):
        super(Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, ('key', 'value', 'obj', 'note', 'deleted', ))
        return self


class _Attrs(dict):
    def __init__(self, obj):
        self._obj = obj

    def history(self, key=None, **kwargs):
        query = {'obj': self._obj['_id']}
        query.update(**kwargs)
        if key:
            query['key'] = key
        return Attr.find(query)

    @property
    def unacknowledged_changes(self):
        return Attr.map_mongo(Attr.find({
            'obj': self._obj['_id'], 'pending_stamp': None,
            'judgment_stamp': None}).sort(
            'creation_stamp.timestamp', pymongo.DESCENDING))

    @property
    def pending_changes(self):
        return Attr.map_mongo(Attr.find({
            'obj': self._obj['_id'], 'judgment_stamp': None,
            'accepted': False}))

    @property
    def accepted_changes(self):
        return Attr.map_mongo(Attr.find(
            {'obj': self._obj['_id'], 'accepted': True}).sort(
            'judgment_stamp.timestamp', pymongo.DESCENDING))

    def __getitem__(self, key):
        attrs = self.history(key, accepted=True).sort(
            'judgment_stamp.timestamp', pymongo.DESCENDING)
        if attrs.count(True) > 0:
            attr = Attr.map_mongo(attrs.limit(1))[0]
            if attr['deleted']:
                raise KeyError(key)
            return attr['value']
        raise KeyError(key)

    get = __getitem__

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def set(self, key, value, person, note=None):
        if type(value) == _AttrList:
            pass
        elif type(value) == list:
            value = _AttrList(value)

        attr = Attr(person, key, value, self._obj['_id'], note)
        attr.save()

    def __delitem__(self, key):
        raise NotImplementedError()

    def delete(self, key, person, note=None):
        attr = Attr(person, key, None, self._obj['_id'], note, deleted=True)
        attr.save()


class Obj(_Change):
    _mongo_collection = cchdo().objs
    from pyramid.security import Authenticated, Allow, Deny
    __acl__ = [
        (Allow, Authenticated, 'create'),
    ]

    def __init__(self, person, doc=None):
        super(Obj, self).__init__(person, doc)
        self['_obj_type'] = type(self).__name__
        self.copy_keys_from(doc, ('_obj_type', ))

    @property
    def attrs(self):
        try:
            return self['_attrs']
        except KeyError:
            self['_attrs'] = _Attrs(self)
            return self['_attrs']

    def remove(self):
        super(Obj, self).remove()
        for attr in Attr.map_mongo(self.attrs.history()):
            attr.remove()


class Person(Obj):
    """ People may be either verified or not.
    If they are associated with an ID provider then they are verified.
    """
    def __init__(self, identifier=None, name_first=None, name_last=None,
                 institution=None, country=None, email=None):
        self['_id'] = 'self'
        super(Person, self).__init__(self)
        del self['_id']

        self['obj_type'] = 'person'

        self['identifier'] = identifier
        self['name_first'] = name_first
        self['name_last'] = name_last
        self['institution'] = institution
        self['country'] = country
        self['email'] = email

        if identifier is None and None in (name_first, name_last, institution,
                                           country, email):
            raise ValueError('Person must be initialized either with '
                             'identifier or attributes.')
    def from_mongo(self, doc):
        super(Obj, self).from_mongo(doc)
        self.copy_keys_from(doc, ('identifier', 'name_first', 'name_last',
                                  'institution', 'country', 'email', ))
        return self

    def is_verified(self):
        return self['identifier'] is not None

    def save(self):
        super(Person, self).save()
        self['creation_stamp']['person'] = self['_id']
        super(Person, self).save()


class Data(Attr):
    """ Specific type of attribute that stores large amounts of data """
    pass
