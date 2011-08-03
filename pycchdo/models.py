import datetime

import pymongo
from pymongo.objectid import ObjectId
from pymongo.son_manipulator import SONManipulator

import gridfs


mongo_conn = None
grid_fs = None


data_file_descriptions = {
    'bottle_exchange': 'ASCII .csv bottle data with station information',
    'ctdzip_exchange': 'ZIP archive of ASCII .csv CTD data with station information',
    'ctdzip_netcdf': 'ZIP archive of binary CTD data with station information',
    'bottlezip_netcdf': 'ZIP archive of binary bottle data with station information',
    'sum_woce': 'ASCII station/cast information',
}


def init_conn(settings):
    global mongo_conn
    try:
        mongo_conn = pymongo.Connection(settings['db_uri'])
    except pymongo.errors.AutoReconnect:
        raise IOError('Unable to connect to database. Check that the database server is running.')


def cchdo():
    if not mongo_conn:
        raise IOError('No database connection. Check that the server .ini file contains the correct db_uri.')
    return mongo_conn.cchdo


def fs():
    global grid_fs
    if not grid_fs:
        grid_fs = gridfs.GridFS(cchdo())
    return grid_fs


def timestamp():
    return datetime.datetime.utcnow()


def ensure_objectid(idobj):
    if type(idobj) is not ObjectId:
        return ObjectId(idobj)
    return idobj


def _sort_by_creation(query):
    return query.sort('creation_stamp.timestamp', pymongo.DESCENDING)

class mongodoc(dict):
    def copy_keys_from(self, o, keys):
        if not o:
            return
        for key in keys:
            try:
                self[key] = o[key]
            except KeyError:
                pass

    def mapobj(self, doc, key, cls):
        try:
            v = doc[key]
            if type(v) is not dict:
                self[key] = v
            else:
                self[key] = cls.map_mongo(v)
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

        def get_person(obj_doc):
            try:
                return obj_doc['creation_stamp']['person']
            except KeyError:
                return None

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


class Stamp(mongodoc):
    def __init__(self, person):
        self['timestamp'] = timestamp()
        if type(person) is pymongo.objectid.ObjectId:
            self['person'] = person
        else:
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
    def __init__(self, body=None, action=None, data_type=None, subject=None):
        """ A Note that can be attached to any _Change 

            body - the actual note
            action - the action taken
            data_type - the type of data that was changed
            subject - a nice summary
        """
        self['action'] = action
        self['data_type'] = data_type
        self['subject'] = subject
        self['body'] = body


class collectablemongodoc(mongodoc):
    """ A top level document in collections.

    These documents have _ids versus noncollectable ones which should only be
    stored inside these.
    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().collectables

    def save(self):
        self['_id'] = self._mongo_collection().save(self)

    def remove(self):
        self._mongo_collection().remove(self['_id'])

    @classmethod
    def all(cls):
        return cls._mongo_collection().find()

    @classmethod
    def find(cls, *args, **kwargs):
        return cls._mongo_collection().find(*args, **kwargs)

    @classmethod
    def find_one(cls, *args, **kwargs):
        return cls._mongo_collection().find_one(*args, **kwargs)

    @classmethod
    def find_id(cls, idobj):
        try:
            idobj = ensure_objectid(idobj)
        except pymongo.objectid.InvalidId:
            raise ValueError()
        return cls.find_one({'_id': idobj})

    @classmethod
    def get_id(cls, idobj):
        return cls.map_mongo(cls.find_id(idobj))


class _Change(collectablemongodoc):
    @classmethod
    def _mongo_collection(cls):
        return cchdo().changes

    def __init__(self, person, note=None):
        self['creation_stamp'] = Stamp(person)
        self['pending_stamp'] = None
        self['judgment_stamp'] = None
        self['accepted'] = False
        self['note'] = note

    def from_mongo(self, doc):
        super(_Change, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_id', 'creation_stamp', 'pending_stamp',
                                  'judgment_stamp', 'accepted', 'note', ))
        return self

    @property
    def creation_stamp(self):
        v = self['creation_stamp']
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def pending_stamp(self):
        v = self['pending_stamp']
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def judgment_stamp(self):
        v = self['judgment_stamp']
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def note(self):
        v = self['note']
        if type(v) is dict:
            return Note.map_mongo(v)
        return v

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


class Attr(_Change):
    @classmethod
    def _mongo_collection(cls):
        return cchdo().attrs

    def __init__(self, person, key=None, value=None, obj=None, note=None,
                 deleted=False):
        super(Attr, self).__init__(person)
        self.set(key, value)
        self['deleted'] = deleted
        self['obj'] = obj
        self['note'] = note

    def from_mongo(self, doc):
        super(Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, ('key', 'value', 'file', 'obj', 'note', 'deleted', ))
        return self

    def set(self, key, value):
        """ Sets the key and value. Special case when value is a file-like
        object.

        Attempts to store the file in the filesystem and stores the id in the
        'file' attribute
        """
        self['key'] = key
        self['file'] = False
        self['value'] = None
        try:
            value.filename
            try:
                gridfile = fs().put(value.file, filename=value.filename, contentType=value.type)
            except Exception, e:
                raise e
            self['value'] = gridfile
            self['file'] = True
        except AttributeError:
            self['value'] = value

    def is_data(self):
        return self['file']

    def is_note(self):
        return self['key'] is None and self['value'] is None and self['note'] is not None

    @property
    def file(self):
        if not self.is_data():
            return None
        return fs().get(self['value'])

    def delete_file(self):
        if not self.is_data():
            return
        fs().delete(self['value'])

    def remove(self):
        self.delete_file()
        super(Attr, self).remove()


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
        return Attr.map_mongo(_sort_by_creation(Attr.find({
            'obj': self._obj['_id'], 'pending_stamp': None,
            'judgment_stamp': None})))

    @property
    def pending_changes(self):
        return Attr.map_mongo(Attr.find({
            'obj': self._obj['_id'], 'judgment_stamp': None,
            'accepted': False}))

    @property
    def accepted_changes(self):
        return Attr.map_mongo(_sort_by_creation(Attr.find(
            {'obj': self._obj['_id'], 'accepted': True})))

    def notes(self):
        return [x for x in self.accepted_changes if x.is_note()]

    @property
    def current_pairs(self):
        curr = {}
        deleted = []
        for change in self.accepted_changes:
            k = change['key']
            if k not in curr and k not in deleted:
                if change['deleted']:
                    deleted.append(k)
                else:
                    curr[k] = change['value']
        return curr

    def keys(self):
        return self.current_pairs.keys()

    def __getitem__(self, key):
        attrs = _sort_by_creation(self.history(key, accepted=True))
        if attrs.count(True) > 0:
            attr = Attr.map_mongo(attrs.limit(1))[0]
            if attr['deleted']:
                raise KeyError(key)
            return attr['value']
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def set(self, key, value, person, note=None):
        attr = Attr(person, key, value, self._obj['_id'], note)
        attr.save()
        return attr

    def add_note(self, note, person):
        return self.set(None, None, person, note)

    def __delitem__(self, key):
        raise NotImplementedError()

    def delete(self, key, person, note=None):
        attr = Attr(person, key, None, self._obj['_id'], note, deleted=True)
        attr.save()
        return attr

    def remove(self):
        for attr in Attr.map_mongo(self.history()):
            attr.remove()


class Obj(_Change):
    @classmethod
    def _mongo_collection(cls):
        return cchdo().objs

    def __init__(self, person, doc=None):
        super(Obj, self).__init__(person, doc)
        self['_obj_type'] = type(self).__name__
        self.copy_keys_from(doc, ('_obj_type', ))

    def from_mongo(self, doc):
        super(Obj, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_obj_type', '_attrs',))
        return self

    @property
    def attrs(self):
        try:
            return self['_attrs']
        except KeyError:
            self['_attrs'] = _Attrs(self)
            return self['_attrs']

    def notes(self):
        return self.attrs.notes()

    def add_note(self, note, person):
        return self.attrs.add_note(note, person)

    def remove(self):
        super(Obj, self).remove()
        self.attrs.remove()

    @classmethod
    def all(cls):
        if cls is Obj:
            return cls._mongo_collection().find()
        return cls._mongo_collection().find({'_obj_type': cls.__name__})

    @classmethod
    def find(cls, *args, **kwargs):
        try:
            query = args[0]
        except IndexError:
            query = {}
            args = (query, )
        try:
            query['_obj_type']
        except KeyError:
            if cls is not Obj:
                query['_obj_type'] = cls.__name__
        return cls._mongo_collection().find(*args, **kwargs)

    @classmethod
    def find_one(cls, *args, **kwargs):
        try:
            query = args[0]
        except IndexError:
            query = {}
            args = (query, )
        try:
            query['_obj_type']
        except KeyError:
            if cls is not Obj:
                query['_obj_type'] = cls.__name__
        return cls._mongo_collection().find_one(*args, **kwargs)

    @classmethod
    def find_id(cls, idobj):
        if type(idobj) is not ObjectId:
            try:
                idobj = ObjectId(idobj)
            except pymongo.objectid.InvalidId:
                return None
        if cls is Obj:
            return cls.find_one({'_id': idobj})
        return cls.find_one({'_id': idobj, '_obj_type': cls.__name__})

    def __str__(self):
        copy = {}
        for key, value in self.items():
            if key in ('creation_stamp', 'pending_stamp', 'judgment_stamp', ):
                continue
            copy[key] = value
        return str(copy)


class Person(Obj):
    """ People may be either verified or not.
    If they are associated with an ID provider then they are verified.
    """
    def __init__(self, identifier=None, name_first=None, name_last=None,
                 institution=None, country=None, email=None):
        self['_id'] = 'self'
        super(Person, self).__init__(self)
        del self['_id']

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
        super(Person, self).from_mongo(doc)
        self.copy_keys_from(doc, ('identifier', 'name_first', 'name_last',
                                  'institution', 'country', 'email', ))
        return self

    def full_name(self):
        return ' '.join((self['name_first'], self['name_last']))

    def is_verified(self):
        return self['identifier'] is not None

    def save(self):
        super(Person, self).save()
        self['creation_stamp']['person'] = self['_id']
        super(Person, self).save()

    def __repr__(self):
        return 'Person ({last}, {first})'.format(last=self['name_last'],
                                                 first=self['name_first'])


class Cruise(Obj):
    def __init__(self, person):
        super(Cruise, self).__init__(person)

    def expocode(self):
        try:
            return self.attrs['expocode']
        except KeyError:
            return None

    def statuses(self):
        try:
            return self.attrs['statuses']
        except KeyError:
            return []

    def date_start(self):
        try:
            return self.attrs['date_start']
        except KeyError:
            return None

    def date_end(self):
        try:
            return self.attrs['date_end']
        except KeyError:
            return None

    def collections(self):
        # TODO
        return []

    def ship(self):
        ship = self.attrs.get('ship', None)
        if ship:
            return Ship.get_id(ship)
        return None

    def country(self):
        country = self.attrs.get('country', None)
        if country:
            return Country.get_id(country)
        return None

    def participants(self, role=None):
        # TODO
        participant = (Person, 'role')
        participants = []
        if role:
            return [p for p, role in participants if role == role]
        else:
            return participants

    def chief_scientists(self):
        return self.participants('chief_scientist')

    @classmethod
    def get_by_expocode(cls, expocode):
        attrs = _sort_by_creation(Attr.find({'key': 'expocode'}))
        # Get Attrs that represent most current key value for objs
        obj_expocodes = {}
        for attr in attrs:
            obj_id = attr['obj']
            if obj_id not in obj_expocodes:
                obj_expocodes[obj_id] = attr['value']
        # Don't return a cruise if the current value of expocode isn't
        obj_ids = [o for o, e in obj_expocodes.items() if e == expocode]

        # 1. Multiple cruises might have the same expocode
        return Cruise.map_mongo(Cruise.find({'_id': {'$in': obj_ids}}))


class Institution(Obj):
    pass


class Ship(Obj):
    def name(self):
        try:
            return self.attrs['name']
        except KeyError:
            return None


class Country(Obj):
    def name(self):
        try:
            return self.attrs['iso_3166-1']
        except KeyError:
            return None

    def iso_code(self):
        try:
            return self.attrs['iso_3166-1_alpha-2']
        except KeyError:
            return None


class Collection(Obj):
    def names(self):
        try:
            return self.attrs['names']
        except KeyError:
            return []

    def name(self):
        try:
            return self.names()[0]
        except IndexError:
            return None

    def cruises(self):
        attr_obj_ids = [x['obj'] for x in Attr.find({'key': 'collections',
                                                     'value': str(self['_id'])})]
        objs = [Obj._mongo_collection().find_one(id) for id in attr_obj_ids]
        return Cruise.map_mongo(
            filter(lambda x: x['_obj_type'] == Cruise.__name__, objs))
