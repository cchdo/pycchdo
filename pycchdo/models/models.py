import datetime

import pymongo
from pymongo.objectid import ObjectId

from shapely.geometry import linestring
from geojson import LineString

import gridfs

import libcchdo.fns

import triggers


mongo_conn = None
grid_fs = None


data_file_descriptions = {
    'bottle_exchange': 'ASCII .csv bottle data with station information',
    'ctdzip_exchange': 'ZIP archive of ASCII .csv CTD data with station '
                       'information',
    'ctdzip_netcdf': 'ZIP archive of binary CTD data with station information',
    'bottlezip_netcdf': 'ZIP archive of binary bottle data with station '
                        'information',
    'sum_woce': 'ASCII station/cast information',
}


def init_conn(settings, **kwargs):
    global mongo_conn
    try:
        mongo_conn = pymongo.Connection(settings['db_uri'], **kwargs)
    except pymongo.errors.AutoReconnect:
        raise IOError('Unable to connect to database (%s). Check that the '
                      'database server is running.' % settings['db_uri'])

    # TODO This requires MongoDB 1.9+
    #cchdo().attrs.ensure_index([('track', pymongo.GEO2D)])


def cchdo():
    if not mongo_conn:
        raise IOError('No database connection. Check that the server .ini file '
                      'contains the correct db_uri.')
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


def _str2unicode(x):
    if type(x) is str:
        return unicode(x)
    return x


def _sort_by_stamp(query, stamp='creation'):
    return query.sort('%s_stamp.timestamp' % stamp, pymongo.DESCENDING)


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

    # Allow referring to attributes of the mongodoc rather than accessing as
    # keys.

    def __getattr__(self, name):
        try:
            return self[self.attribute_map(name)]
        except KeyError:
            raise AttributeError(
                '%r has no attribute %s' % (self, self.attribute_map(name)))

    def __setattr__(self, name, value):
        self[self.attribute_map(name)] = value

    def __delattr__(self, name):
        try:
            del self[self.attribute_map(name)]
        except KeyError:
            pass

    def attribute_map(self, name):
        """ Allow for aliases of attributes.
        Override to add aliases.

        """
        return name

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
                p.id = 'fake'
                return cls(person=p).from_mongo(d)
            elif cls is Attr:
                obj_id = d.get('obj', None)
                return cls(get_person(d), obj_id).from_mongo(d)
            else:
                return cls(get_person(d)).from_mongo(d)

        if type(cursor_or_dict) is dict:
            return get_instance(cursor_or_dict)
        return map(get_instance, cursor_or_dict)


class Stamp(mongodoc):
    def __init__(self, person):
        self.timestamp = timestamp()
        if type(person) is pymongo.objectid.ObjectId:
            self.person = person
        else:
            if type(person) is not Person:
                raise TypeError('%r (%s) is not a Person object' % \
                                (person, type(person)))
            try:
                self.person = person.id
            except AttributeError:
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
        self.body = body
        self.action = action
        self.data_type = data_type
        self.subject = subject


class collectablemongodoc(mongodoc):
    """ A top level document in collections.

    These documents have _ids versus noncollectable ones which should only be
    stored inside these.
    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().collectables

    def attribute_map(self, attr):
        # Attribute names with trailing '_' considered aliases.
        # This is useful for properties that need to refer to themselves.
        if attr.endswith('_'):
            attr = attr[:-1]
        if attr == 'id':
            attr = '_id'
        return super(collectablemongodoc, self).attribute_map(attr)

    def from_mongo(self, doc):
        super(collectablemongodoc, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_id', ))
        return self

    def save(self):
        self.id = self._mongo_collection().save(self)

    def remove(self):
        self._mongo_collection().remove(self.id)

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

    def __eq__(self, o):
        return self.id == o.id

    def __hash__(self):
        return int(str(self.id), 16)


class _Change(collectablemongodoc):
    @classmethod
    def _mongo_collection(cls):
        return cchdo().changes

    def __init__(self, person, note=None, *args, **kwargs):
        super(_Change, self).__init__(*args, **kwargs)
        self.creation_stamp = Stamp(person)
        self.pending_stamp = None
        self.judgment_stamp = None
        self.accepted = False
        self.note = note

    def from_mongo(self, doc):
        super(_Change, self).from_mongo(doc)
        self.copy_keys_from(doc, (
            'creation_stamp', 'pending_stamp', 'judgment_stamp', 'accepted',
            'note', ))
        return self

    @property
    def creation_stamp(self):
        v = self.creation_stamp_
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def pending_stamp(self):
        v = self.pending_stamp_
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def judgment_stamp(self):
        v = self.judgment_stamp_
        if type(v) is dict:
            return Stamp.map_mongo(v)
        return v

    @property
    def note(self):
        v = self.note_
        if type(v) is dict:
            return Note.map_mongo(v)
        return v

    def is_judged(self):
        return self.judgment_stamp_ is not None

    def is_acknowledged(self):
        return self.pending_stamp_ is not None

    def is_accepted(self):
        return self.is_judged() and self.accepted

    def is_rejected(self):
        return self.is_judged() and not self.accepted

    def accept(self, person):
        self.judgment_stamp = Stamp(person)
        self.accepted = True
        self.save()

    def acknowledge(self, person):
        if not self.pending_stamp_:
            self.pending_stamp = Stamp(person)
            self.save()
            return True
        else:
            return False

    def reject(self, person):
        self.judgment_stamp = Stamp(person)
        self.accepted = False
        self.save()

    def mtime(self):
        return self.creation_stamp.timestamp


class Attr(_Change):
    @classmethod
    def _mongo_collection(cls):
        return cchdo().attrs

    def __init__(self, person, obj, key=None, value=None,
                 note=None, deleted=False):
        super(Attr, self).__init__(person)
        self.obj = obj
        self.deleted = deleted
        self.note = note
        self.set(key, value)

    def from_mongo(self, doc):
        super(Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, ('key', 'value', 'file', 'track', 'obj',
                                  'note', 'deleted', ))
        return self

    def set(self, key, value):
        """ Sets the key and value.
        
        Special cases:
        
        * value is a file-like object
          Attempts to store the file in the filesystem and stores the id in the
          'file' attribute.
        * key is track
          Stores the value (which must be a GeoJSON linestring coordinate list)
          in the 'track' attribute.

        """
        self.key = key
        self.file = None
        self.track = None
        self.value = None

        if key == 'track':
            if type(value) is LineString:
                value = value.coordinates
            else:
                assert not isinstance(value, str)
                for i, c in enumerate(value):
                    assert not isinstance(c, str)
                    assert len(c) is 2
                    try:
                        float(c[0])
                        float(c[1])
                    except ValueError:
                        raise TypeError('Coordinate list must contain numbers.'
                                        ' Element %d does not' % i)
            self.track = value
            return
        try:
            try:
                gridfile = fs().put(value.file, filename=value.filename,
                                    contentType=value.type)
            except Exception, e:
                raise e
            self.file = gridfile
        except AttributeError:
            self.value = value

    # TODO instead of is_data just check for presence of data
    def is_data(self):
        return self.file_

    def is_track(self):
        return self.track

    def is_note(self):
        return self.key is None and self.value_ is None and \
               self.note_ is not None

    @classmethod
    def all_data(cls):
        return cls.find({'file': {'$exists': True}})

    @classmethod
    def all_track(cls):
        return cls.find({'track': {'$exists': True}})

    @classmethod
    def all_notes(cls):
        return cls.find({'key': None, 'value': None, 'note': {'$exists': True}})

    @property
    def file(self):
        if not self.is_data():
            return None
        return fs().get(self.file_)

    @property
    def value(self):
        if self.deleted:
            raise KeyError(self.key)
        if self.is_data():
            return self.file
        elif self.is_track():
            return self.track
        else:
            return self.value_

    def delete_file(self):
       if not self.is_data():
           return
       fs().delete(self.file_)

    def save(self):
        super(Attr, self).save()
        if self.is_note():
            triggers.saved_note(self)

    def remove(self):
        self.delete_file()
        super(Attr, self).remove()
        if self.is_note():
            triggers.saved_note(self)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        mapping = '%r: %r' % (self.key, self.value)
        if self.deleted:
            mapping = 'DEL'
        return "Attr({mapping}, {accepted}|{id})".format(
            mapping=mapping, accepted=self.accepted, id=self.id)


class Obj(_Change):
    """ Base object for all tracked objects in the system.

    Objs may have two types of attributes:
    1. system attributes - written directly into the object
    2. tracked attributes - written as Attrs which are _Changes themselves.
       These can only be edited using the get, set, delete.

    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().objs

    def __init__(self, person, doc=None):
        super(Obj, self).__init__(person, doc)
        self._obj_type = type(self).__name__
        self.from_mongo(doc)

    def from_mongo(self, doc):
        super(Obj, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_obj_type', '_attrs',))
        return self

    def attribute_map(self, attr):
        if attr == 'type':
            attr = '_obj_type'
        if attr == 'attrs':
            attr = '_attrs'
        return super(Obj, self).attribute_map(attr)

    def _find_attrs(self, query={}, **kwargs):
        q = {'obj': self.id}
        if query:
            q.update(query)
            return Attr.find(q, **kwargs)
        else:
            q.update(**kwargs)
            return Attr.find(q)

    def _find_attr(self, query={}, **kwargs):
        q = {'obj': self.id}
        if query:
            q.update(query)
            return Attr.find_one(q, **kwargs)
        else:
            q.update(**kwargs)
            return Attr.find_one(q)

    def history(self, key=None, **kwargs):
        if key:
            kwargs['key'] = key
        return _sort_by_stamp(self._find_attrs(**kwargs))

    def unacknowledged_tracked(self):
        return Attr.map_mongo(_sort_by_stamp(self._find_attrs(
            {'judgment_stamp': None, 'pending_stamp': None})))

    def pending_tracked(self):
        return Attr.map_mongo(_sort_by_stamp(self._find_attrs(
            {'judgment_stamp': None, 'accepted': False})))

    def accepted_tracked(self):
        return Attr.map_mongo(_sort_by_stamp(self._find_attrs(
            {'accepted': True})))

    def get_attr(self, key):
        """ Returns the most recent Attr document for the given key """
        attr = self._find_attr({'key': key, 'accepted': True},
            sort=[('judgment_stamp.timestamp', pymongo.DESCENDING)])
        if attr:
            return Attr.map_mongo(attr)
        raise KeyError(key)

    def current_attrs(self):
        curr = {}
        deleted = set()
        for attr in Attr.map_mongo(
            self._find_attrs({'accepted': True},
                             sort=[('judgment_stamp.timestamp',
                                    pymongo.DESCENDING)])):
            k = attr.key
            if k not in curr and k not in deleted:
                if attr.deleted:
                    deleted.add(k)
                else:
                    curr[k] = attr
        return curr

    def attr_keys(self):
        """ List of the tracked attributes present for this Obj

            This list does not include attributes that previously existed but
            are now deleted.

        """
        return self.current_attrs().keys()

    def get(self, key, default=None):
        try:
            return super(Obj, self).__getitem__(key)
        except KeyError:
            try:
                return self.get_attr(key).value
            except KeyError:
                return default

    def set(self, key, value, person, note=None):
        attr = Attr(person, self.id, key, value, note)
        attr.save()
        return attr

    def set_accept(self, key, value, person, note=None):
        attr = self.set(key, value, person, note)
        attr.accept(person)
        return attr

    def delete(self, key, person, note=None):
        attr = Attr(person, self.id, key, None, note, deleted=True)
        attr.save()
        return attr

    def delete_accept(self, key, person, note=None):
        attr = self.delete(key, person, note)
        attr.accept(person)
        return attr

    @property
    def notes(self):
        return Attr.map_mongo(self._find_attrs({
            'accepted': True,
            'note': {'$exists': True}, 
            'key': None,
            'value': None,
            'file': None,
            'track': None,
            }))

    def add_note(self, note, person):
        return self.set(None, None, person, note)

    def mtime(self):
        creation_time = super(Obj, self).mtime()
        accepted = self.accepted_tracked()
        if not accepted:
            return creation_time
        last_attr_creation_time = accepted[0].creation_stamp.timestamp
        return max(creation_time, last_attr_creation_time)

    def save(self):
        super(Obj, self).save()
        triggers.saved_obj(self)

    def remove(self):
        super(Obj, self).remove()
        for attr in Attr.map_mongo(self._find_attrs()):
            attr.remove()
        triggers.removed_obj(self)

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
    def get_all(cls, *args, **kwargs):
        return cls.map_mongo(cls.find(*args, **kwargs))

    @classmethod
    def get_one(cls, *args, **kwargs):
        return cls.map_mongo(cls.find_one(*args, **kwargs))

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

    @classmethod
    def get_by_attrs(cls, **kwargs):
        query = [{'key': unicode(k),
                  'value': _str2unicode(v),
                  'accepted': True} for k, v in kwargs.items()]
        objs_attrs = Attr._mongo_collection().group(
            ['obj'],
            {'$or': query},
            {'a': 0}, 
            'function (x, o) { o.a++; }')

        # Filter the matched objs for the correct number of matched attrs
        objs = filter(None, [cls.get_id(oa['obj']) for oa in objs_attrs \
                             if oa['a'] == len(query)])
        # Make sure the most current values match by filtering resulting objs
        def true_match(obj):
            for k, v in kwargs.items():
                if obj.get(k) != v:
                    return False
            return True
        return filter(true_match, objs)

    def __repr__(self):
        copy = {}
        for key, value in self.items():
            if key in ('creation_stamp', 'pending_stamp', 'judgment_stamp', ):
                continue
            copy[key] = value
        return '%s(%s)' % (type(self).__name__, copy)


class Person(Obj):
    """ People may be either verified or not.
    If they are associated with an ID provider then they are verified.
    """
    def __init__(self, identifier=None, name_first=None, name_last=None,
                 institution=None, country=None, email=None):
        # Pretend Person is already saved so Stamp can be set
        self.id = 'self'
        super(Person, self).__init__(self)
        del self.id

        self.identifier = identifier
        self.name_first = name_first
        self.name_last = name_last
        self.institution = institution
        self.country = country
        self.email = email

        if identifier is None and None in (
                name_first, name_last):
            raise ValueError(
                'Person must be initialized either with identifier '
                'or names.')

    def from_mongo(self, doc):
        super(Person, self).from_mongo(doc)
        self.copy_keys_from(doc, (
            'identifier', 'name_first', 'name_last', 'institution', 'country',
            'email', ))
        return self

    def full_name(self):
        return ' '.join((self.name_first, self.name_last))

    def is_verified(self):
        return self.identifier is not None

    def save(self):
        super(Person, self).save()
        self['creation_stamp']['person'] = self.id
        super(Person, self).save()

    def __repr__(self):
        try:
            return 'Person ({last}, {first})'.format(last=self.name_last,
                                                     first=self.name_first)
        except AttributeError:
            return 'Person ()'


class _Participants(dict):
    """ A map of roles to sets of Persons. """
    def __init__(self, cruise, *args, **kwargs):
        super(_Participants, self).__init__(*args, **kwargs)
        self._cruise = cruise

    def __getitem__(self, key):
        try:
            return [Person.get_id(id) for id in \
                    super(_Participants, self).__getitem__(key)]
        except KeyError:
            return []
    
    def add(self, person, role, signer):
        """ Adds a participant to the map under the given role. """
        assert type(person) is Person
        pid = person.id

        try:
            l = self[role]
            l.append(pid)
            self[role] = libcchdo.fns.uniquify(l)
        except KeyError:
            self[role] = [pid]
        return self._cruise.set('participants', self, signer)
    
    def remove(self, person, role, signer):
        """ Removes a participant from the map under the given role. """
        assert type(person) is Person
        pid = person.id

        try:
            l = super(_Participants, self).__getitem__(role)
            l.remove(pid)
        except (KeyError, ValueError):
            pass
        return self._cruise.set('participants', self, signer)

    @property
    def roles(self, role=None):
        """ Pairs of Persons and roles present in the map """
        if role is None:
            map = self
        else:
            map = self[role]

        participants = []
        for role, persons in map.items():
            for person in persons:
                participants.append((Person.get_id(person), role, ))
        return participants


class Cruise(Obj):
    def expocode(self):
        return self.get('expocode')

    def statuses(self):
        return self.get('statuses', [])

    def date_start(self):
        return self.get('date_start')

    def date_end(self):
        return self.get('date_end')

    def collections(self):
        collection_ids = self.get('collections', [])
        return filter(
            None, [Collection.get_id(x) for x in collection_ids])

    def ship(self):
        ship = self.get('ship', None)
        if ship:
            return Ship.get_id(ship)
        return None

    def country(self):
        country = self.get('country', None)
        if country:
            return Country.get_id(country)
        return None

    @property
    def participants(self):
        participants = self.get('participants', None)
        if participants:
            return _Participants(self, participants)
        else:
            return _Participants(self)

    @property
    def chief_scientists(self):
        return self.participants['Chief Scientist']

    def track(self):
        track = self.get('track', None)
        if not track:
            return track
        return linestring.LineString(track)

    @classmethod
    def filter_geo(cls, fn, cruises):
        return filter(lambda x: fn(x.track()), cruises)

    @classmethod
    def get_by_expocode(cls, expocode):
        attrs = _sort_by_stamp(Attr.find({'key': 'expocode'}))
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
        return self.get('name')


class Country(Obj):
    def name(self):
        return self.get('iso_3166-1')

    def iso_code(self, length=2):
        if length != 2:
            length = 3
        try:
            return self.get('iso_3166-1_alpha-' + str(length))
        except KeyError:
            return None


class Collection(Obj):
    """ Essentially tags for Cruises.
    
    A Cruise may belong to Basin Collection, WOCE line Collection, etc.
    
    A Collection will also include a type as part of its identifier to
    differentiate between the fields it came from in the original database.
    
    """

    @property
    def names(self):
        try:
            return self.get('names')
        except KeyError:
            return []

    @property
    def name(self):
        try:
            return self.names[0]
        except IndexError:
            return None

    def cruises(self):
        attr_obj_ids = [x['obj'] for x in Attr.find({'key': 'collections',
                                                     'value': str(self.id)})]
        objs = [Obj._mongo_collection().find_one(id) for id in attr_obj_ids]
        return Cruise.map_mongo(
            filter(lambda x: x['_obj_type'] == Cruise.__name__, objs))


class AutoAcceptingObj(Obj):
    def save(self):
        super(AutoAcceptingObj, self).save()
        if not self.judgment_stamp:
            self.accept(self.creation_stamp.person)


class ArgoFile(AutoAcceptingObj):
    """ Files that are given to the CCHDO for Argo calibration only.

    THESE ARE NOT PUBLIC DATA and are only to be shown in the Argo Secure File
    Repository.

    """

    def from_mongo(self, doc):
        super(ArgoFile, self).from_mongo(doc)
        self.copy_keys_from(doc, ('text_identifier', 'file', 'description', 'display', ))
        return self

    @property
    def text_identifier(self):
        return self.get('text_identifier', None)

    @property
    def file(self):
        return self.get('file', None)

    @property
    def description(self):
        return self.get('description', None)

    @property
    def display(self):
        return self.get('display', False)
