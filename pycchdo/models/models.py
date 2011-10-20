import datetime
import re

from warnings import warn

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
    'bottle_woce': 'ASCII bottle data',
    'ctdzip_woce': 'ZIP archive of ASCII CTD data',
    'bottle_exchange': 'ASCII .csv bottle data with station information',
    'ctdzip_exchange': 'ZIP archive of ASCII .csv CTD data with station '
                       'information',
    'ctdzip_netcdf': 'ZIP archive of binary CTD data with station information',
    'bottlezip_netcdf': 'ZIP archive of binary bottle data with station '
                        'information',
    'sum_woce': 'ASCII station/cast information',
    'lvs_woce': 'ASCII large volume samples',
    'lvs_exchange': 'ASCII .csv large volume samples',
    'docs_txt': 'Text documentation',
    'docs_pdf': 'PDF documentation',
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
    """ Provides the root database object """
    if not mongo_conn:
        raise IOError('No database connection. Check that the server .ini file '
                      'contains the correct db_uri.')
    return mongo_conn.cchdo


def fs():
    """ Provides the root file system object """
    global grid_fs
    if not grid_fs:
        grid_fs = gridfs.GridFS(cchdo())
    return grid_fs


def timestamp():
    """ Right now as a datetime """
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
    """ Applies a sort to the mongodb query by the given stamp's timestamp key.

        Valid stamp arguments:
            * creation
            * pending
            * judgment
    
    """
    return query.sort('%s_stamp.timestamp' % stamp, pymongo.DESCENDING)


class mongodoc(dict):
    """ Represents a mongodb document in memory

        Each document has keys and values that need to be mapped and saved. They
        define the document's data.

        A document's data can be accessed using keys as indices and also as
        attributes, e.g.

            d = mongodoc()

            d['key'] = 'foo'
            d['key'] == 'foo'

            d.key == 'foo'

            d.key = 'bar'
            d.key == 'bar'
            del d.key

        Keys, when accessed as attributes, have the additional property of being
        subject to aliasing. By redefining the attribute_map function, different
        names can be given to the same attribute.

            class specialmongodoc(mongodoc):
                def attribute_map(self, name):
                    if name == 'foo':
                        name = 'bar'
                    return name

            d = specialmongodoc()
            d.foo = 'baz'
            d.bar == 'baz'

    """

    def copy_keys_from(self, o, keys):
        """ Used by from_mongo to copy saved keys from mongodb into instances.

        This should be extended by subclasses to add keys to the db to model
        mapping.
        """
        if not o:
            return
        for key in keys:
            try:
                self[key] = o[key]
            except KeyError:
                pass

    def from_mongo(cls, doc):
        """ Used by map_mongo to copy saved data from mongodb into a new
        instances.

        Redefine to provide a better mapping from a mongodb document onto a new
        instance.

        """
        return None

    def mapobj(self, doc, key, cls):
        try:
            v = doc[key]
            if type(v) is not dict:
                self[key] = v
            else:
                self[key] = cls.map_mongo(v)
        except KeyError:
            pass

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
        """ Used by attribute model to Allow for attribute aliases.

        Override to add aliases for attributes.

        The default behavior is for attribute names with trailing '_' to be
        automatically considered aliases. This is useful for defining properties
        on subclasses that need to refer to the same name for the mapping.

            class propertied_mongodoc(mongodoc):
                @property
                def foo(self):
                    return d.foo_ + ' world!'

            d = propertied_mongodoc()
            d.foo_ = 'Hello'
            d.foo_ == 'Hello world!'

        """
        if name.endswith('_'):
            name = name[:-1]
        return name

    @classmethod
    def map_mongo(cls, cursor_or_dict):
        """ Converts lists of or single mongodb documents into class instances.
        
            If the input is a cursor, returns a list of mapped class instances.
            Otherwise, returns the mapped class instance

        """
        # TODO this function needs to be pulled lower in the hierarchy
        if cursor_or_dict is None:
            return None

        def get_person(obj_doc):
            try:
                return obj_doc['creation_stamp']['person']
            except (TypeError, KeyError):
                return None

        def get_instance(d):
            if cls is Person:
                return cls(identifier='placeholder').from_mongo(d)
            elif cls is Stamp:
                p = Person(identifier='placeholder')
                p.id = 'fake'
                return cls(person=p).from_mongo(d)
            elif cls is _Attr:
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
        if type(person) is ObjectId:
            self.person = person
        else:
            if type(person) is not Person:
                raise TypeError('%r (%s != Person)' % (person, type(person)))
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

    def __repr__(self):
        return "Stamp(%s, %r)" % (self.timestamp.strftime('%FT%T'),
                                  self.person)


class idablemongodoc(mongodoc):
    """ These documents have _ids versus non-idable ones which should only
        ever be stored inside these.

    """
    def attribute_map(self, attr):
        if attr == 'id':
            attr = '_id'
        return super(idablemongodoc, self).attribute_map(attr)

    def from_mongo(self, doc):
        super(idablemongodoc, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_id', ))
        return self

    def __eq__(self, o):
        return self.id == o.id

    def __hash__(self):
        return int(str(self.id), 16)


class collectablemongodoc(idablemongodoc):
    """ A top level mongodb document in mongodb collections.
    
        These documents are stored directly in the collection and may have other
        documents inside themselves.

    """
    @classmethod
    def _mongo_collection(cls):
        """ Defines the mongodb collection that instances of this class will be
        put in. This affects where the documents will be searched for, saved,
        and removed.

        """
        return cchdo().collectables

    def save(self):
        self.id = self._mongo_collection().save(self)
        return self

    def remove(self):
        self._mongo_collection().remove(self.id)
        return self

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
    def get_all(cls, *args, **kwargs):
        return cls.map_mongo(cls.find(*args, **kwargs))

    @classmethod
    def get_one(cls, *args, **kwargs):
        return cls.map_mongo(cls.find_one(*args, **kwargs))

    @classmethod
    def get_id(cls, idobj):
        return cls.map_mongo(cls.find_id(idobj))


class Note(collectablemongodoc):
    """ A Note that can be attached to any _Change 

        Attrs:
        creation_stamp - creation stamp
        body - the actual note
        action - the action taken
        data_type - the type of data that was changed
        subject - a nice summary
        discussion - Setting this True makes the note only visible
                     for mergers.
                     
    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().notes

    def __init__(self, person, body=None, action=None, data_type=None,
                 subject=None, discussion=False):
        self.creation_stamp_ = Stamp(person)
        self.body = body
        self.action = action
        self.data_type = data_type
        self.subject = subject
        self.discussion = discussion

    @property
    def creation_stamp(self):
        v = self.creation_stamp_
        if type(v) is Stamp:
            return v
        return Stamp.map_mongo(v)

    def from_mongo(self, doc):
        super(Note, self).from_mongo(doc)
        self.copy_keys_from(doc, ('creation_stamp', 'body', 'action',
                                  'data_type', 'subject', 'discussion'))
        return self


class _Change(collectablemongodoc):
    """ A Change to the dataset that should be recorded along with the time and
    person who changed it.

    Changes may be accepted or rejected. Changes may also have attached notes
    which may themselves be public or for dicussion purposes only.

    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().changes

    def __init__(self, person, note=None, *args, **kwargs):
        super(_Change, self).__init__(*args, **kwargs)
        self.creation_stamp_ = Stamp(person)
        self.pending_stamp_ = None
        self.judgment_stamp_ = None
        self.accepted = False
        self.notes_ = []
        try:
            self.add_note(note)
        except TypeError:
            pass

    def from_mongo(self, doc):
        super(_Change, self).from_mongo(doc)
        self.copy_keys_from(doc, (
            'creation_stamp', 'pending_stamp', 'judgment_stamp', 'accepted',
            'notes', ))
        return self

    @property
    def creation_stamp(self):
        v = self.creation_stamp_
        if type(v) is Stamp:
            return v
        return Stamp.map_mongo(v)

    @property
    def pending_stamp(self):
        v = self.pending_stamp_
        if type(v) is Stamp:
            return v
        return Stamp.map_mongo(v)

    @property
    def judgment_stamp(self):
        v = self.judgment_stamp_
        if type(v) is Stamp:
            return v
        return Stamp.map_mongo(v)

    @property
    def notes(self):
        return sorted(filter(None, [Note.get_id(nid) for nid in self.notes_]),
                      key=lambda n: n.creation_stamp.timestamp)

    @property
    def notes_public(self):
        return filter(lambda n: not n.discussion, self.notes)

    @property
    def notes_discussion(self):
        return filter(lambda n: n.discussion, self.notes)

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

    @property
    def mtime(self):
        # TODO correct misnomer, should be ctime
        return self.creation_stamp.timestamp

    def add_note(self, note):
        if note is None:
            raise TypeError()
        try:
            note.id
        except AttributeError:
            note.save()
        if note.id not in self.notes_:
            self.notes_.append(note.id)
            self.save()
            triggers.saved_note(note)

    def remove_note(self, note):
        if note is None:
            raise TypeError()
        if note.id in self.notes_:
            self.notes_.remove(note.id)
            self.save()
            triggers.removed_note(note)


class _Attr(_Change):
    """ Not for general use. Please defer to Obj's get, set, and delete
    methods for interacting with Attrs.

    """
    @classmethod
    def _mongo_collection(cls):
        return cchdo().attrs

    def __init__(self, person, obj, key=None, value=None,
                 note=None, deleted=False):
        super(_Attr, self).__init__(person)
        self.obj_ = obj
        self.deleted = deleted
        if note is not None:
            self.add_note(note)
        self.set(key, value)

    def from_mongo(self, doc):
        super(_Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, ('key', 'value', 'file', 'track', 'obj',
                                  'deleted', ))
        return self

    def set(self, key, value):
        """ Sets the key and value.
        
            Special cases:
            
            * value is a cgi.FieldStorage-like object
              Attempts to store the file in the filesystem and stores the id in
              the 'file' attribute.
            * key is track
              Stores the value (which must be a GeoJSON linestring coordinate
              list) in the 'track' attribute.

        """
        self.key = key
        self.file = None
        self.track = None
        self.value = None
        self.accepted_value = None

        if key == 'track':
            if type(value) is LineString:
                value = value.coordinates
            elif type(value) is linestring.LineString:
                value = list(value.coords)
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

    # TODO just check for presence of file_
    def is_data(self):
        warn('deprecated', DeprecationWarning)
        return self.file_

    def is_track(self):
        warn('deprecated', DeprecationWarning)
        return self.track

    def _get_file(self, file):
        if not file:
            return None
        try:
            return fs().get(file)
        except gridfs.NoFile:
            raise IOError('File not found')

    @property
    def file(self):
        if self.file_ and self.accepted_value:
            return self._get_file(self.accepted_value)
        return self.file_original

    @property
    def file_original(self):
        try:
            return self._get_file(self.file_)
        except IOError:
            return None

    @property
    def value_original(self):
        if self.deleted:
            raise KeyError(self.key)
        if self.file_:
            return self.file_original
        if self.track_:
            return self.track_
        return self.value_

    @property
    def value(self):
        if self.deleted:
            raise KeyError(self.key)
        if self.accepted_value:
            if self.file_:
                return self.file
            if self.track_:
                return self.accepted_value
            return self.accepted_value
        return self.value_original

    @property
    def obj(self):
        """ The object that the _Attr is attached to """
        return Obj.get_id_polymorphic(self.obj_)

    def accept_value(self, value, person):
        """ Changes the accepted value of the _Attr to 'value'. This should be
            used when the original value of _Attr was a suggestion from a human
            and the new value is a moderated known good value.

        """
        if self.file_:
            try:
                value.file
            except AttributeError:
                raise ValueError("Tried to accept value (%r) that did not match "
                                 "_Attr type" % value)
        if self.track_:
            pass
            # TODO check to make sure it is a track-like object

        self.accepted_value = value
        self.accept(person)

    def delete_file(self):
       if not self.file_:
           return
       fs().delete(self.file_)

    def remove(self):
        self.delete_file()
        super(_Attr, self).remove()

    def __repr__(self):
        try:
            mapping = '%r: %r' % (self.key, self.value)
        except KeyError:
            mapping = 'DEL'
        except IOError:
            mapping = 'FILE NOT FOUND'

        # If object hasn't been saved yet, there is no id.
        if hasattr(self, 'id'):
            return "_Attr({mapping}, {accepted}|{id})".format(
                mapping=mapping, accepted=self.accepted, id=self.id)
        else:
            return "_Attr({mapping}, {accepted}|UNSAVED)".format(
                mapping=mapping, accepted=self.accepted)

    @classmethod
    def all_data(cls):
        return cls.find({'file': {'$ne': None}})

    @classmethod
    def all_track(cls):
        return cls.find({'track': {'$ne': None}})

    @classmethod
    def pending(cls):
        return cls.get_all({'judgment_stamp': None})


class Obj(_Change):
    """ Base object for all tracked objects in the system.

        Objs may have two types of attributes:
        1. system attributes (Keys) - written directly into the object
        2. tracked attributes (Attributes) - written as Attrs which are
            _Changes themselves. These can only be edited using the get, set,
            delete.

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

    def find_attrs(self, query={}, **kwargs):
        q = {'obj': self.id}
        if query:
            q.update(query)
            return _Attr.find(q, **kwargs)
        else:
            q.update(**kwargs)
            return _Attr.find(q)

    def find_attr(self, query={}, **kwargs):
        q = {'obj': self.id}
        if query:
            q.update(query)
            return _Attr.find_one(q, **kwargs)
        else:
            q.update(**kwargs)
            return _Attr.find_one(q)

    def history(self, key=None, **kwargs):
        if key:
            kwargs['key'] = key
        return _sort_by_stamp(self.find_attrs(**kwargs))

    def tracked(self, *args, **kwargs):
        return _Attr.map_mongo(_sort_by_stamp(self.find_attrs(*args, **kwargs)))

    def tracked_data(self):
        return self.tracked({'file': {'$ne': None}})

    def unacknowledged_tracked(self):
        return self.tracked({'judgment_stamp': None, 'pending_stamp': None})

    def pending_tracked(self):
        return self.tracked({'judgment_stamp': None, 'accepted': False})

    def pending_tracked_data(self):
        return self.tracked({'judgment_stamp': None, 'accepted': False,
                             'file': {'$ne': None}})

    def accepted_tracked(self):
        return self.tracked({'accepted': True})

    def accepted_tracked_data(self):
        return self.tracked({'accepted': True, 'file': {'$ne': None}})

    def accepted_tracked_merged_data(self):
        return self.tracked({'accepted': True, 'file': {'$ne': None},
                             'accepted_value': {'$ne': None}})

    def get_attr(self, key):
        """ Returns the most recent _Attr document for the given key """
        attr = self.find_attr({'key': key, 'accepted': True},
            sort=[('judgment_stamp.timestamp', pymongo.DESCENDING)])
        if attr:
            return _Attr.map_mongo(attr)
        raise KeyError(key)

    def current_attrs(self):
        curr = {}
        deleted = set()
        for attr in _Attr.map_mongo(
            self.find_attrs({'accepted': True},
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
        attr = _Attr(person, self.id, key, value, note)
        attr.save()
        return attr

    def set_accept(self, key, value, person, note=None):
        attr = self.set(key, value, person, note)
        attr.accept(person)
        return attr

    def delete(self, key, person, note=None):
        attr = _Attr(person, self.id, key, None, note, deleted=True)
        attr.save()
        return attr

    def delete_accept(self, key, person, note=None):
        attr = self.delete(key, person, note)
        attr.accept(person)
        return attr

    @property
    def mtime(self):
        creation_time = super(Obj, self).mtime
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
        for attr in _Attr.map_mongo(self.find_attrs()):
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
        objs_attrs = _Attr._mongo_collection().group(
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
                obj_v = obj.get(k)
                if type(obj_v) is list and type(v) is not list:
                    if v not in obj_v:
                        return False
                elif obj_v != v:
                    return False
            return True
        return filter(true_match, objs)

    @classmethod
    def subclass_map(cls):
        return dict([(k.__name__, k) for k in cls.__subclasses__()])

    @classmethod
    def get_all_polymorphic(cls, *args, **kwargs):
        objs = cls.find(*args, **kwargs)
        subclass_map = cls.subclass_map()
        mapped = []
        for obj in objs:
            try:
                klass = subclass_map.get(obj['_obj_type'], cls)
                mapped.append(klass.map_mongo(obj))
            except (TypeError, KeyError):
                mapped.append(cls.map_mongo(obj))
        return mapped

    @classmethod
    def get_one_polymorphic(cls, *args, **kwargs):
        obj = cls.find_one(*args, **kwargs)
        try:
            klass = cls.subclass_map().get(obj['_obj_type'], cls)
            return klass.map_mongo(obj)
        except (TypeError, KeyError):
            return cls.map_mongo(obj)

    @classmethod
    def get_id_polymorphic(cls, idobj):
        obj = cls.find_id(idobj)
        try:
            klass = cls.subclass_map().get(obj['_obj_type'], cls)
            return klass.map_mongo(obj)
        except (TypeError, KeyError):
            return cls.map_mongo(obj)

    def __repr__(self):
        copy = {}
        for key, value in self.items():
            if key in ('creation_stamp', 'pending_stamp', 'judgment_stamp',
                       '_obj_type', 'notes'):
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
        self.institution_ = institution
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

    @property
    def institution(self):
        return Institution.get_id(self.institution_)


    def save(self):
        super(Person, self).save()
        self['creation_stamp']['person'] = self.id
        super(Person, self).save()

    def __repr__(self):
        try:
            return u'Person ({last}, {first})'.format(last=self.name_last,
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
            # Order is important
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
    """ The basic unit of metadata storage for the CCHDO

        Attributes:
        basin - imported from "internal"
        parameter_informations - list of documents containing
            status - the status of the parameter; one of the following:
                 online, reformatted, submitted, not_measured, proposed,
                 no_information
            pi - the principal investigator for the parameter on the cruise
            inst - the institution that the pi was operating for
            ts - some date attached to the status and PI of the parameter

    """
    def expocode(self):
        return self.get('expocode')

    def statuses(self):
        return self.get('statuses', [])

    def preliminary(self):
        """ Tells whether the cruise is preliminary for the purposes of
        displaying a warning.

        A cruise may either be completely marked preliminary or preliminary
        attributes may cause it to be considered preliminary as well.

        """
        if self.find_attrs({'key': re.compile('_status$'),
                            'value': 'preliminary'}).count() > 0:
            return True
        return 'preliminary' in self.get('statuses', []) 

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

    @property
    def track(self):
        track = self.get('track', None)
        if not track:
            return track
        return linestring.LineString(track)

    @classmethod
    def filter_geo(cls, fn, cruises):
        return filter(lambda x: fn(x.track), cruises)

    @classmethod
    def get_by_expocode(cls, expocode):
        attrs = _sort_by_stamp(_Attr.find({'key': 'expocode'}))
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
    def __repr__(self):
        try:
            return u'Institution ({name})'.format(name=self.get('name'))
        except AttributeError:
            return u'Institution ()'


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

        Attributes:
        names - names associated with the collection. The first name in the
            list is the canonical name.
        type - identifier of WOCE line, group, program, spatial_group, basin
        basins - a list of any combination of atlantic, arctic, pacific,
            indian, southern
    
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
        attr_obj_ids = [x['obj'] for x in _Attr.find({'key': 'collections',
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

        THESE ARE NOT PUBLIC DATA and are only to be shown in the Argo Secure
        File Repository.

        There are two types of ArgoFile:

        1. Provided files
           These are given to us to be put online and appear nowhere else.
        2. Linked files
           These are actually part of the CCHDO holdings and need to exist as a
           link to the most recent version of the data.

    """

    def from_mongo(self, doc):
        super(ArgoFile, self).from_mongo(doc)
        self.copy_keys_from(doc, ('text_identifier', 'file', 'description',
                                  'display', ))
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


class OldSubmission(Obj):
    """ An old submission imported for record keeping.

        Other information stored:
        The creation timestamp is the create time for the submission record.
        The judgment timestamp is the update time for the submission record.

        Since it appears that the submissions were created using a script, only
        the first encountered time is recorded.
    
        Attributes:
        date - the date of the submission
        stamp - unknown
        submitter - the name of the submitter. Format varies.
        line - the WOCE line number of the submission. May be other things.
        folder - the original folder name of the submission. This is mainly
                 used to group the submission files together during import.
        files - a list of fs ids that store the actual files of the submission.
                Each file will have the original filename stored along with
                an attribute "old_submission" marked True.

    """
    def remove(self):
        for file in self.get('files'):
            fs().delete(file)
        super(OldSubmission, self).remove()


class Submission(Obj):
    """ A Submission to the CCHDO. These interface with humans so they need
        intervention to make everything behave nicely before going into the
        system.

        Keys:
        expocode
        ship_name
        line
        action
        public - whether the submission is of public or non-public data
        assigned - whether the submission has been assigned
        cruise_date - the date of the cruise being submitted
        suggested - an _Attr. When this is set, the submission has been
                    looked at by a human and the _Attr represents verified
                    information

    """
    def attach(self, attr):
        """ Attaches the submission to a new _Attr. The submission will be also
            be accepted.

        """
        if not data_type in data_file_descriptions.keys():
            pass # TODO

    @classmethod
    def unacknowledged(cls):
        """ Gives Submissions that have not yet been reviewed """
        return [] # TODO


class Parameter(Obj):
    """ A parameter

        Attributes:
        name - the WOCE mnemonic
        full_name - the full name of the parameter
        name_netcdf - the accepted name for the parameter in WOCE NetCDF format
        format - a C format string. This should actually be the number of
            significant figures but this is how the data was stored.
        unit - the unit for the parameter
        bounds - a tuple marking the generally acceptable range for the
            parameter for its primary unit
        in_groups_but_did_not_exist - marks the parameter as existing in the
            table parameter_groups but no where else in the database. Import
            use only.

    """
    @property
    def unit(self):
        return Unit.get_id(self.get('unit'))

    def display_order(self):
        # TODO
        return 0


class Unit(Obj):
    """ A unit for parameters

    Attributes:
    name - The name for a unit
    mnemnoic - the WOCE mnemonic for the unit

    """
    pass


class ParameterOrder(Obj):
    """ Defines the class that a Parameter of which it is a member.

    Attributes:
    name - the class
    order - the list of parameters in the order they should appear

    """
    pass
