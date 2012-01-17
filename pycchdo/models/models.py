import datetime
import re
import socket

from warnings import warn

from webob.multidict import MultiDict

import pymongo
from pymongo import DESCENDING
from pymongo.objectid import ObjectId, InvalidId

from shapely.geometry import linestring
from geojson import LineString

import gridfs

import libcchdo.fns

import triggers


mongo_conn = None
grid_fs = None


data_file_human_names = {
    'bottle_exchange': 'Bottle Exchange',
    'bottlezip_exchange': 'Bottle ZIP Exchange',
    'ctdzip_exchange': 'CTD ZIP Exchange',
    'bottlezip_netcdf': 'Bottle ZIP NetCDF',
    'ctdzip_netcdf': 'CTD ZIP NetCDF',
    'bottle_woce': 'Bottle WOCE',
    'ctdzip_woce': 'CTD ZIP WOCE',
    'sum_woce': 'Summary WOCE',
    'map_thumb': 'Map Thumbnail',
    'map_full': 'Map Fullsize',
    'doc_txt': 'Documentation Text',
    'doc_pdf': 'Documentation PDF',
}


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
    'large_volume_samples_woce': 'ASCII large volume samples',
    'large_volume_samples_exchange': 'ASCII .csv large volume samples',
    'trace_metals_woce': 'ASCII trace metal samples',
    'trace_metals_exchange': 'ASCII .csv trace metal samples',
    'map_thumb': 'Map thumbnail',
    'map_full': 'Map full size',
    'doc_txt': 'ASCII cruise and data documentation',
    'doc_pdf': 'Portable Document Format cruise and data documentation',
}


def flatten(l):
    return [item for sublist in l for item in sublist]


def init_conn(settings, **kwargs):
    """Set up a connection to the PyMongo database.

    Arguments:
      settings: settings dictionary containing, among other
                configuration options, the database URI
      **kwargs: required for miscellaneous options to the
                pymongo.Connection constructor
    """
    global mongo_conn
    try:
        mongo_conn = pymongo.Connection(settings['db_uri'], **kwargs)
    except pymongo.errors.AutoReconnect:
        raise IOError('Unable to connect to database (%s). Check that the '
                      'database server is running.' % settings['db_uri'])


def ensure_indices():
    cchdo().attrs.ensure_index([('obj', 1), ('value', 1)])
    cchdo().attrs.ensure_index([('key', 1), ('value', 1), ('accepted', 1)])
    cchdo().attrs.ensure_index([('key', 1), ('accepted_value', 1), ('accepted', 1)])
    # This requires MongoDB >=1.3.3
    cchdo().attrs.ensure_index([('track', pymongo.GEO2D)])
    # Indexing by polygon requires MongoDB >=1.9


def cchdo():
    """Yield the root database object.
    
    This is a connection to the PyMongo database.

    This operation will fail if init_conn() [see above] has
    not been invoked, or if init_conn() has failed to
    establish the database connection.

    Return:
      The pymongo.Connection object representing the
      connection to the PyCCHDO PyMongo database, iff
      it exists.
    """
    if not mongo_conn:
        raise IOError('No database connection. Check that the server .ini file '
                      'contains the correct db_uri.')
    return mongo_conn.cchdo


def fs():
    """ Provides the root file system object
        Ensure and return a GridFS wrapper for the database connection.
    """
    global grid_fs
    if not grid_fs:
        grid_fs = gridfs.GridFS(cchdo())
    return grid_fs


def timestamp():
    """Create a datetime.datetime representing Now."""
    # FIXME This needs to make a datetime that is timezone aware
    return datetime.datetime.utcnow()


def ensure_objectid(idobj):
    """Ensure that an object ID is an ObjectId.

    Argument:
      idobj: an object ID.

    Returns:
      idobj if type(idobj) is ObjectId else ObjectId(idobj)

    """
    if type(idobj) is not ObjectId:
        try:
            return ObjectId(idobj)
        except TypeError:
            return None
        except InvalidId:
            raise ValueError()
    return idobj


def _str2unicode(x):
    if type(x) is str:
        return unicode(x)
    return x


def is_valid_ip(ip):
    """ Validates IP Addresses """
    return is_valid_ipv4(ip) or is_valid_ipv6(ip)


def is_valid_ipv4(ip):
    try:
        return socket.inet_pton(socket.AF_INET, ip)
    except AttributeError: # no inet_pton here, sorry
        try:
            return socket.inet_aton(ip)
        except socket.error:
            return False
    except socket.error:
        return False


def is_valid_ipv6(ip):
    try:
        return socket.inet_pton(socket.AF_INET6, ip)
    except socket.error:
        return False


def sort_by_stamp(query, stamp='creation', direction=DESCENDING):
    """ Applies a sort to the mongodb query by the given stamp's timestamp key.

        Valid stamp arguments:
            * creation
            * pending
            * judgment
    
    """
    return query.sort('%s_stamp.timestamp' % stamp, direction)


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
        subject to aliasing. By redefining the _key_alias_resolve function, different
        names can be given to the same attribute.

            class specialmongodoc(mongodoc):
                def _key_alias_resolve(self, name):
                    if name == 'foo':
                        name = 'bar'
                    return name

            d = specialmongodoc()
            d.foo = 'baz'
            d.bar == 'baz'

    """
    __allowed_keys = []

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

    def from_mongo(self, doc):
        """ Used by map_mongo to copy saved data from mongodb into a new
        instances.

        Redefine to provide a better mapping from a mongodb document onto a new
        instance.

        """
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    @property
    def allowed_untracked_keys(self):
        return self.__allowed_keys

    def mapobj(self, doc, key, cls):
        """Project a key-value pair from a document onto oneself.

        Arguments:
          doc: The document from which the key-value pair will be obtained.
          key: The key for the pair to project from the document.
          cls: The class that will perform the mapping operation if the
               value is a dictionary.
        """
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
            return self[self._key_alias_resolve(name)]
        except KeyError:
            raise AttributeError(
                '%r has no attribute %s' % (self, self._key_alias_resolve(name)))

    def __setattr__(self, name, value):
        self[self._key_alias_resolve(name)] = value

    def __delattr__(self, name):
        try:
            del self[self._key_alias_resolve(name)]
        except KeyError:
            pass

    def _key_alias_resolve(self, name):
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

        if issubclass(type(cursor_or_dict), dict):
            return get_instance(cursor_or_dict)
        return map(get_instance, cursor_or_dict)


class Stamp(mongodoc):
    __allowed_keys = ['timestamp', 'person', ]

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
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    @property
    def person(self):
        return Person.get_id(self['person'])

    def __unicode__(self):
        return u"Stamp(%s, %r)" % (self.timestamp.strftime('%FT%T'),
                                  self.person)


class idablemongodoc(mongodoc):
    """ These documents have _ids versus non-idable ones which should only
        ever be stored inside these.

    """
    __allowed_keys = ['_id', ]

    def _key_alias_resolve(self, attr):
        if attr == 'id':
            attr = '_id'
        return super(idablemongodoc, self)._key_alias_resolve(attr)

    def from_mongo(self, doc):
        super(idablemongodoc, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
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

    def __str__(self):
        return unicode(self).encode('ascii', 'replace')

    def __unicode__(self):
        return unicode(idablemongodoc.__repr__(self))

    def __repr__(self):
        klass = self.__class__.__name__
        try:
            return u"%s(%s)" % (klass, self['_id'])
        except KeyError:
            return u'%s(unsaved)' % klass


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
    __allowed_keys = ['creation_stamp', 'body', 'action', 'data_type',
                      'subject', 'discussion']

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
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    @property
    def mtime(self):
        # TODO correct misnomer, should be ctime
        return self.creation_stamp.timestamp

    def __unicode__(self):
        try:
            return u'Note(%s, %s)' % (self.subject, self.id)
        except AttributeError:
            try:
                return u'Note(%s)' % self.id
            except AttributeError:
                return u'Note'


class _Change(collectablemongodoc):
    """ A Change to the dataset that should be recorded along with the time and
    person who changed it.

    Changes may be accepted or rejected. Changes may also have attached notes
    which may themselves be public or for dicussion purposes only.

    """
    __allowed_keys = ['creation_stamp', 'pending_stamp', 'judgment_stamp',
                      'accepted', 'notes', ]

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
        self.copy_keys_from(doc, self.__allowed_keys)
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


class _RequestTracker(mongodoc):
    """ Adds methods to a mongodoc to allow it to track requests

        This class serves as a function grouping and should not be instantiated.
        Remember to add "_requests" to subclasses copy_keys_from

    """
    def add_request(self, request):
        """ Takes a webob request and stores relevant information related to
        tracking.

        Parameters:
            request - the webob.Request

        """
        req = {}
        try:
            req['date'] = request.date
            req['ip'] = request.remote_addr
            if not type(req['date']) is datetime.datetime:
                raise ValueError()
            if not is_valid_ip(req['ip']):
                raise ValueError()
        except (AttributeError, ValueError):
            # Don't store request if either of these are invalid or missing
            return False
        try:
            req['date'] = request.date
        except AttributeError:
            pass
        self.requests.append(req)

    @property
    def requests(self):
        try:
            return self._requests_
        except AttributeError:
            self._requests_ = []
            return self._requests_

    def clear_requests(self):
        try:
            del self._requests_
        except AttributeError:
            pass


class _FileHolder(_RequestTracker):
    """ Adds methods to a mongodoc to allow it to hold a reference to a file in
        the filesystem.

        This class serves as a function grouping and should not be instantiated.
        Remember to add "file" to subclasses copy_keys_from

    """

    def store_file(self, field_or_gridout):
        """ Stores the file described by field_or_gridout in the filesystem and keeps a
            reference.

            The reference will be stored in the object's file attribute.

            If field_or_gridout is a gridfs.grid_file.GridOut object then the
            reference is stored and no new file is created.

            Raises: AttributeError when field does not have file, filename, and
                    type
        """
        self.file_ = None
        if type(field_or_gridout) is gridfs.grid_file.GridOut:
            self.file_ = field_or_gridout._id
        else:
            field = field_or_gridout
            try:
                self.file_ = fs().put(field.file, filename=field.filename,
                                      contentType=field.type)
            except Exception, e:
                raise e

    def _get_file(self, fileid):
        """ Retrieves the file from the filesystem using the given reference """
        if not fileid:
            return None
        try:
            return fs().get(fileid)
        except gridfs.NoFile:
            raise IOError('File not found')

    @property
    def file(self):
        try:
            return self._get_file(self.file_)
        except IOError:
            return None

    def delete_file(self):
       if not self.file_:
           return
       fs().delete(self.file_)


class _Attr(_Change, _FileHolder):
    """ An Attr of an Obj

        Not for general use. Please defer to Obj's get, set, and delete methods

    """
    __allowed_keys = ['key', 'value', '_requests', 'file', 'track', 'obj',
                      'deleted', 'accepted_value', ]

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
        self.accepted_value = None
        self.set(key, value)

    def from_mongo(self, doc):
        super(_Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
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
        self.track = None
        self.value = None

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
            self.store_file(value)
        except AttributeError:
            self.value = value

    # TODO just check for presence of file_
    def is_data(self):
        warn('deprecated', DeprecationWarning)
        return self.file_

    # TODO just check for presence of track
    def is_track(self):
        warn('deprecated', DeprecationWarning)
        return self.track

    @property
    def file(self):
        if self.file_ and self.accepted_value:
            return self._get_file(self.accepted_value)
        return self.file_original

    @property
    def file_original(self):
        # Let _FileHolder handle this
        return super(_Attr, self).file

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

        # TODO what if value is a FieldStorage?
        self.accepted_value = value
        self.accept(person)

    def remove(self):
        self.delete_file()
        super(_Attr, self).remove()

    def __unicode__(self):
        try:
            mapping = u'%r: %r' % (self.key, self.value)
        except KeyError:
            mapping = u'DEL'
        except IOError:
            mapping = u'FILE NOT FOUND'

        # If object hasn't been saved yet, there is no id.
        if hasattr(self, 'id'):
            return u"_Attr({mapping}, {accepted}|{id})".format(
                mapping=mapping, accepted=self.accepted, id=self.id)
        else:
            return u"_Attr({mapping}, {accepted}|UNSAVED)".format(
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
    __allowed_keys = ['_obj_type', '_attrs', ]
    allowed_attrs = MultiDict()

    @classmethod
    def _mongo_collection(cls):
        return cchdo().objs

    def __init__(self, person, doc=None):
        super(Obj, self).__init__(person, doc)
        self._obj_type = type(self).__name__
        self.from_mongo(doc)

    def from_mongo(self, doc):
        super(Obj, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    def _key_alias_resolve(self, attr):
        if attr == 'type':
            attr = '_obj_type'
        if attr == 'attrs':
            attr = '_attrs'
        return super(Obj, self)._key_alias_resolve(attr)

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
        return sort_by_stamp(self.find_attrs(**kwargs))

    def tracked(self, *args, **kwargs):
        return _Attr.map_mongo(
            sort_by_stamp(self.find_attrs(*args, **kwargs), 'judgment'))

    def tracked_data(self):
        return self.tracked({'file': {'$ne': None}})

    def unjudged_tracked(self):
        return self.tracked({'judgment_stamp': None})

    def unjudged_tracked_data(self):
        return self.tracked({'judgment_stamp': None, 'file': {'$ne': None}})

    def unacknowledged_tracked(self):
        return self.tracked({'judgment_stamp': None, 'pending_stamp': None})

    def pending_tracked(self):
        return self.tracked({'judgment_stamp': None,
                             'pending_stamp': {'$ne': None}})

    def pending_tracked_data(self):
        return self.tracked({
            'judgment_stamp': None, 'pending_stamp': {'$ne': None},
            'file': {'$ne': None}})

    def accepted_tracked(self):
        return self.tracked({'accepted': True})

    def accepted_tracked_data(self):
        return self.tracked({'accepted': True, 'file': {'$ne': None}})

    def accepted_tracked_changed_data(self):
        return self.tracked({'accepted': True, 'file': {'$ne': None},
                             'accepted_value': {'$ne': None}})

    def get_attr(self, key):
        """ Returns the most recent _Attr document for the given key """
        attr = self.find_attr({'key': key, 'accepted': True},
            sort=[('judgment_stamp.timestamp', DESCENDING)])
        if attr:
            return _Attr.map_mongo(attr)
        raise KeyError(key)

    def current_attrs(self):
        curr = {}
        deleted = set()
        for attr in _Attr.map_mongo(sort_by_stamp(
                                        self.find_attrs({'accepted': True}),
                                        'judgment')):
            k = attr.key
            if k not in curr and k not in deleted:
                if attr.deleted:
                    deleted.add(k)
                else:
                    curr[k] = attr
        return curr

    @property
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

    def polymorph(self):
        """ Gives back a subclass instance based on _obj_type. All the data
            loaded in the class is transferred.

            Useful for transforming an Obj into a Cruise or Person, etc.

            Returns:
                an new instance of a subclass of Obj containing all the current
                data.

        """
        try:
            klass = Obj.subclass_map().get(self._obj_type, self.__class__)
            return klass.map_mongo(self)
        except (TypeError, KeyError) as e:
            return self

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
            query = args[0].copy()
        except IndexError:
            query = {}
        try:
            query['_obj_type']
        except KeyError:
            if cls is not Obj:
                query['_obj_type'] = cls.__name__
        args = (query, )
        return cls._mongo_collection().find(*args, **kwargs)

    @classmethod
    def find_one(cls, *args, **kwargs):
        try:
            query = args[0].copy()
        except IndexError:
            query = {}
        try:
            query['_obj_type']
        except KeyError:
            if cls is not Obj:
                query['_obj_type'] = cls.__name__
        args = (query, )
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
    def _get_by_attrs_true_match(cls, obj, **kwargs):
        """ Make sure the most current values match by filtering resulting objs
        """
        if obj is None:
            return False
        for k, v in kwargs.items():
            obj_v = obj.get(k)

            if type(obj_v) is list and type(v) is not list:
                try:
                    if not any(v.match(x) for x in obj_v):
                        return False
                except AttributeError:
                    if v not in obj_v:
                        return False
            else:
                try:
                    if not v.match(obj_v):
                        return False
                except AttributeError:
                    if obj_v != v:
                        return False
        return True

    @classmethod
    def get_by_attrs(cls, d={}, **kwargs):
        """ Gets all objects that have _Attrs that match all the requested
            key-value pairs.

            Values may be regular expression objects as compiled by `re`.

        """
        map = d
        if not map:
            map = kwargs

        if not map:
            raise ValueError("No filters specified. Did you mean get_all()?")

        def querygen(k, v):
            value_query = _str2unicode(v)
            return {
                'key': unicode(k),
                'accepted': True,
                '$or': [
                     {'$and': [
                         {'accepted_value': {'$ne': None}},
                         {'accepted_value': value_query},
                     ]}, 
                     {'$and': [
                         {'accepted_value': None},
                         {'value': value_query},
                     ]}, 
                ]
            }

        query = [querygen(k, v) for k, v in map.items()]

        len_query = len(query)
        objs_attrs = _Attr._mongo_collection().group(
            ['obj'],
            {'$or': query},
            {'a': 0}, 
            'function (x, o) { o.a++; }')

        # Filter the matched objs for the correct number of matched attrs
        objs = [cls.get_id(oa['obj']) for oa in objs_attrs \
                                       if oa['a'] == len_query]
        return filter(lambda o: cls._get_by_attrs_true_match(o, **kwargs),
                      objs)

    @classmethod
    def descendant_classes(cls):
        classes = cls.__subclasses__()
        descendants = []
        for klass in classes:
            subclasses = klass.descendant_classes()
            descendants.append(klass)
            descendants.extend(subclasses)
        return descendants

    @classmethod
    def subclass_map(cls):
        return dict([(k.__name__, k) for k in cls.descendant_classes()])

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
        except (TypeError, KeyError) as e:
            return cls.map_mongo(obj)

    def __unicode__(self):
        copy = {}
        for key, value in self.items():
            if key in ('creation_stamp', 'pending_stamp', 'judgment_stamp',
                       '_obj_type', 'notes'):
                continue
            copy[key] = value
        return u'%s(%s)' % (type(self).__name__, copy)


class _Participants(dict):
    """ A map of roles to sets of Persons.

        Participants masquerades as a dictionary of roles but is actually stored
        by mongodb like so: [{'role': r, 'person': p_id, 'institution': i_id}, ... ]
    
    """
    def __init__(self, cruise, participants=[]):
        self._cruise = cruise

        for p in participants:
            role = p['role']
            doc = {'person': Person.get_id(p['person']),
                   'institution': Institution.get_id(p['institution'])}
            try:
                self[role].append(doc)
            except KeyError:
                self[role] = [doc]
        
    def __getitem__(self, key):
        """ Gives pairs of Person, Institutions for the specified role """
        return dict.__getitem__(self, key)

    def _add(self, person, role, institution=None):
        """ Adds a participant to the map under the given role. """
        pid = {'person': person, 'institution': institution}
        if pid['person'] is None:
            raise AttributeError("Only institution can be none")

        try:
            l = dict.__getitem__(self, role)
            if pid not in l:
                l.append(pid)
                dict.__setitem__(self, role, l)
                return True
        except KeyError:
            dict.__setitem__(self, role, [pid])
            return True
        return False

    def _remove(self, person, role, institution=None):
        """ Removes a participant from the map under the given role. """
        pid = {'person': person, 'institution': institution}

        try:
            l = dict.__getitem__(self, role)
            l.remove(pid)
        except (KeyError, ValueError):
            return False
        return True

    def _clear(self):
        for key in self.keys():
            del key
    
    def add(self, person, role, signer, institution=None):
        if self._add(person, role, institution):
            return self.save(signer)
    
    def remove(self, person, role, signer, institution=None):
        if self._remove(person, role, institution):
            return self.save(signer)

    def clear(self, signer):
        self._clear()
        return self.save(signer)

    def batch_add(self, role_person_institutions, signer):
        for role, person, institution in role_person_institutions:
            self._add(person, role, institution)
        self.save(signer)

    def batch_remove(self, role_person_institutions, signer):
        for role, person, institution in role_person_institutions:
            self._remove(person, role, institution)
        self.save(signer)

    @property
    def roles(self, role=None):
        """ Pairs of Persons and roles present in the map """
        participants = []
        if role is None:
            for role, pis in self.items():
                for pi in pis:
                    participants.append((pi['person'], role, ))
        else:
            pis = dict.__getitem__(self, role)
            for pi in pis:
                participants.append((pi['person'], role, ))
        return participants

    def save(self, signer):
        list = []
        for role, pis in self.items():
            for pi in pis:
                pid = pi['person'].id
                try:
                    iid = pi['institution'].id
                except AttributeError:
                    iid = None
                list.append({'role': role, 'person': pid, 'institution': iid})
        return self._cruise.set_accept('participants', list, signer)


class Cruise(Obj):
    """ The basic unit of metadata storage for the CCHDO

        Adding files
        ============
        Files are acquired by PIs submitting their data.

        There are two cases for adding files to a Cruise:
          1. Through the submit form and then through moderator intervention
          2. Added directly to the cruise as a suggested update to a file type

        Submit form
        -----------
        Each file stored with a copy of the submission information in the
        form of a Submission object.

        Submission objects can then be connected to a particular attribute on a
        cruise as is done for direct suggestions. A human must provide the type
        of file being suggested. In this manner, they are similar to imported
        legacy Queue files.

        NOTE: A difference exists between imported legacy submissions and
        created submissions. Imported submissions that have already been queued
        have their _Attr attachment set to True instead of being linked to a
        direct suggestion. This is because there is no easy inferred link from
        legacy submission to legacy queue file.

        Imported legacy Queue files
        ---------------------------
        Imported Queue files are direct suggestions but are abnormal in that
        their keys are "data_suggestion". This is because there is no guaranteed
        way to determine the type of file being suggested. This is left to a
        human and will require the imported queue files to be updated
        accordingly.

        Direct suggestion
        -----------------
        A direct suggestion involves an attribute attached to a particular
        Cruise that has a key associated with a file type. This state is similar
        to the legacy queue state of "as-received", but is not visible anywhere
        until the attribute has been acknowledged.
        
        Once the attribute has been acknowledged, it becomes visible to the
        public along with any visible notes. This is synonymous with the legacy
        queue state of "as-received". Public or discussion notes may be made on
        these attributes. The acknowledger becomes the equivalent of the legacy
        queue file CCHDO contact.

        An acknowledged file attribute may be rejected, accepted, or even
        accepted with a different value. Accepting a file attribute results in
        the legacy queue state of "merged". The accepted value becomes the most
        recent version of the value for the given file.

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
    allowed_attrs = MultiDict([
        ['Text', ['expocode', 'link']], 
        ['Datetime', ['date_start', 'date_end']], 
        ['Text List', ['aliases']],
        ['ID', ['ship', 'country']],
        ['ID List', ['collections']],
    ])

    allowed_attrs_list = flatten(allowed_attrs.values())

    allowed_attrs_human_names = {
        'expocode': 'ExpoCode',
        'link': 'Expedition Link',
        'aliases': 'Aliases',
        'ship': 'Ship',
        'country': 'Country',
        'collections': 'Collections',
        'date_start': 'Start Date',
        'date_end': 'End Date',
    }

    @classmethod
    def attr_type(cls, key):
        types = [k for k, v in cls.allowed_attrs.items() if key in v]
        if len(types) > 0:
            return types[0].lower().replace(' ', '_')
        return 'text'

    @property
    def expocode(self):
        return self.get('expocode')

    @property
    def statuses(self):
        return self.get('statuses', [])

    @property
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

    @property
    def date_start(self):
        return self.get('date_start')

    @property
    def date_end(self):
        return self.get('date_end')

    @property
    def collections(self):
        collection_ids = self.get('collections', [])
        return filter(
            None, [Collection.get_id(x) for x in collection_ids])

    @property
    def collections_woce_line(self):
        cs = self.collections
        colls = []
        for c in cs:
            if c.get('type') == 'WOCE line':
                colls.append(c)
        return colls

    @property
    def woce_line(self):
        coll = self.collections_woce_line
        if coll:
            return coll[0].name
        return None

    @property
    def ship(self):
        ship = self.get('ship', None)
        if ship:
            return Ship.get_id(ship)
        return None

    @property
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
        try:
            return self.participants['Chief Scientist']
        except KeyError:
            return []

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
        attrs = sort_by_stamp(_Attr.find({'key': 'expocode'}))
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


class CruiseAssociate(Obj):
    """ Provide a way to get the cruises that an Obj is associated to

    """
    cruise_associate_key = ''

    def _assoc_key(self, key, value_key=None):
        if value_key:
            return '%s.%s' % (key, value_key)
        return key

    def cruises(self, value_key=None, limit=0):
        query = {
            'key': self.cruise_associate_key,
            '$or': [
                {'$and': [
                    {'accepted_value': {'$ne': None}},
                    {self._assoc_key('accepted_value', value_key): self.id},
                ]},
                {'$and': [
                    {'accepted_value': None},
                    {self._assoc_key('value', value_key): self.id},
                ]},
            ],
        }
        attrs = _Attr.find(query, fields=['obj'], limit=limit)
        attr_obj_ids = set(x['obj'] for x in attrs)
        obj_coll = Obj._mongo_collection()
        objs = [obj_coll.find_one(
            {'_id': id, '_obj_type': Cruise.__name__}) for id in attr_obj_ids]
        objs = filter(None, objs)
        # TODO filter rejected cruises
        return Cruise.map_mongo(objs)


class CruiseParticipantAssociate(CruiseAssociate):
    """ Provide a way to get the cruises that an Participant attribute is
        associated to

        These are people or institutions.

    """
    cruise_associate_key = 'participants'
    cruise_participant_associate_key = None

    def cruises(self):
        return super(CruiseParticipantAssociate, self).cruises(
            self.cruise_participant_associate_key)


class Country(CruiseAssociate):
    cruise_associate_key = 'country'

    @property
    def name(self):
        return self.get('iso_3166-1', None)

    def iso_code(self, length=2):
        if length != 2:
            length = 3
        return self.get('iso_3166-1_alpha-' + str(length), None)

    def people(self):
        return Person.get_all({'country': self.id})

    def __unicode__(self):
        try:
            return u'Country ("{name}", {id})'.format(
                name=self.name, id=self.id)
        except AttributeError:
            return u'Country ()'


class Person(CruiseParticipantAssociate):
    """ People may be either verified or not.
        If they are associated with an ID provider then they are verified.

    """
    cruise_participant_associate_key = 'person'
    __allowed_keys = ['identifier', 'name_first', 'name_last', 'institution',
                      'country', 'email', ]

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
        self.country_ = country
        self.email = email

        if identifier is None and None in (
                name_first, name_last):
            raise ValueError(
                'Person must be initialized either with identifier '
                'or names.')

    def from_mongo(self, doc):
        super(Person, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    def full_name(self):
        return ' '.join((self.name_first or '', self.name_last or ''))

    def is_verified(self):
        return self.identifier is not None

    @property
    def institution(self):
        return Institution.get_id(self.institution_)

    @property
    def country(self):
        return Country.get_id(self.country_)

    def save(self):
        super(Person, self).save()
        self['creation_stamp']['person'] = self.id
        super(Person, self).save()

    def __unicode__(self):
        try:
            return u'Person ({last}, {first})'.format(last=self.name_last,
                                                      first=self.name_first)
        except AttributeError:
            return u'Person ()'


class MultiNameObj(Obj):
    """ MultiNameObjs have multiple possible names

        The first stored name is taken as the default.

        TODO perhaps Institutions and Ships may also have multiple names. For
        now let them have just one canonical name.

    """

    @property
    def names(self):
        return self.get('names', [])

    @property
    def name(self):
        try:
            return self.names[0]
        except IndexError:
            return None

    def __unicode__(self):
        try:
            return u'{klass} ("{names}", {id})'.format(
                klass=self.__class__.__name__,
                names=', '.join(self.names), id=self.id)
        except AttributeError:
            return u'{klass} ()'.format(klass=self.__class__.__name__)
    

class Institution(CruiseParticipantAssociate):
    cruise_participant_associate_key = 'institution'

    @property
    def name(self):
        return self.get('name', None)

    def people(self):
        return Person.get_all({'institution': self.id})

    def __unicode__(self):
        try:
            return u'Institution ({name})'.format(name=self.name)
        except AttributeError:
            return u'Institution ()'


class Ship(CruiseAssociate):
    cruise_associate_key = 'ship'

    @property
    def name(self):
        return self.get('name', None)

    def __unicode__(self):
        return u'Ship(%s)' % self.name


class Collection(CruiseAssociate, MultiNameObj):
    """ Essentially tags for Cruises.
    
        A Cruise may belong to Basin Collection, WOCE line Collection, etc.
        
        A Collection will also include a type as part of its identifier to
        differentiate between the fields it came from in the original database.

        Attributes:
        names - names associated with the collection. The first name in the
            list is the canonical name.
        type - identifier of WOCE line, group, program, spatial_group, basin
        basins - a list of any combination of atlantic, arctic, pacific,
            indian, southern. This is only attached to spatial_group typed
            collections.
    
    """
    cruise_associate_key = 'collections'

    #@classmethod
    #def _get_all_by_name_true_match(cls, obj, name):
    #    """ Make sure the name actually matches
    #    """
    #    if obj is None:
    #        return False
    #    try:
    #        return any(name.match(n) for n in obj.names)
    #    except AttributeError:
    #        return name in obj.names


    @classmethod
    def get_all_by_name(cls, name):
        """ Returns all collections that match the given name

            Parameters:
                name - either a string or a regular expression object
        
        """

        return self.get_by_attrs(names=name)

        #try:
        #    name.match
        #    name.search
        #    value_query = {'$regex': name}
        #except AttributeError:
        #    value_query = name

        #query = {'key': 'names',
        #         'accepted': True,
        #         '$or': [
        #             {'$and': [
        #                 {'accepted_value': {'$ne': None}},
        #                 {'accepted_value': value_query},
        #             ]}, 
        #             {'$and': [
        #                 {'accepted_value': None},
        #                 {'value': value_query},
        #             ]}, 
        #         ],
        #        }

        #objs_attrs = _Attr._mongo_collection().group(
        #    ['obj'], query, {'a': 0}, 
        #    'function (x, o) { o.a++; }')

        ## Filter the matched objs for the correct number of matched attrs
        #objs = [cls.get_id(oa['obj']) for oa in objs_attrs if oa['a'] == 1.0]
        #return filter(lambda o: cls._get_all_by_name_true_match(o, name), objs)

    @property
    def type(self):
        return self.get('type', None)


class AutoAcceptingObj(Obj):
    """ When AutoAcceptingObjs are saved, they are also accepted using the
    creator as the signer, obviating the step of accepting known good changes.

    """
    def save(self):
        super(AutoAcceptingObj, self).save()
        if not self.judgment_stamp:
            self.accept(self.creation_stamp.person)


class ArgoFile(AutoAcceptingObj, _FileHolder):
    """ Files that are given to the CCHDO for Argo calibration only.

        THESE ARE NOT PUBLIC DATA and are only to be shown in the Argo Secure
        File Repository.

        There are two types of ArgoFile:

        1. Provided files
           These are given to us to be put online and appear nowhere else.
        2. Linked files
           These are actually part of the CCHDO holdings and need to exist as a
           link to the most recent version of the data.

        Attributes:
        text_identifier - some text that makes the file quickly identifiable to
                          a human
        file - either an ObjectId that is the file in the filesystem or a tuple
               like (ObjectId, attribute) that describes which attr of which obj
               holds the file.
        description
        display - whether or not the file is meant to be visible

    """
    __allowed_keys = ['text_identifier', '_requests', 'file', 'description',
                      'display', ]

    def __init__(self, person):
        super(ArgoFile, self).__init__(person)
        self.text_identifier = None
        self.file = None
        self.description = None
        self.display = None

    def from_mongo(self, doc):
        super(ArgoFile, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    @property
    def file(self):
        """ Gives the filesystem file that the ArgoFile refers to """
        if type(self.file_) in (list, tuple):
            id, attr = self.file_
            return Obj.get_id_polymorphic(id).get(attr, None)
        return super(ArgoFile, self).file

    # Cannot use @file.setter because __setattr__ will be called instead.
    # Use store_file

    def link(self, obj, attr_key):
        """ Populates the ArgoFile as a Linked file """
        try:
            obj.get(attr_key)
        except KeyError:
            raise ValueError('%s does not exist for %s' % (attr_key, obj))
        self.file_ = (obj.id, attr_key)
        self.save()


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
    __allowed_keys = ['date', 'stamp', 'submitter', 'line', 'folder', 'files', ]

    def from_mongo(self, doc):
        super(OldSubmission, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    def remove(self):
        for file in self.files_:
            fs().delete(file)
        super(OldSubmission, self).remove()


class Submission(Obj, _FileHolder):
    """ A Submission to the CCHDO. These interface with humans so they need
        intervention to make everything behaves nicely before going into the
        system.

        Attributes:
        expocode
        ship_name
        line
        action
        public - whether the submission is of public or non-public data
        cruise_date - the date of the cruise being submitted
        file - the file that is being suggested
        attached - an _Attr id.
            When this is set, the submission has been looked at by a human and
            the corresponding _Attr represents verified information representing
            this submission.

            SPECIAL CASE: This is set to True during legacy import because there
            is no way to determine it without human help.

    """
    __allowed_keys = ['expocode', 'ship_name', 'line', 'action', 'public',
                      'cruise_date', 'attached', 'file', ] 

    def from_mongo(self, doc):
        super(Submission, self).from_mongo(doc)
        self.copy_keys_from(doc, self.__allowed_keys)
        return self

    @property
    def identifier(self):
        return self.expocode_

    def cruises_from_identifier(self):
        cruises = Cruise.get_by_attrs(expocode=self.expocode)
        if len(cruises) > 0:
            return cruises
        return []

    @property
    def attached(self):
        """ Gives the _Attr that the submission is attached into OR True if
            the submission was imported and attached already.

        """
        if self.attached_ == True:
            return True
        return _Attr.get_id(self.attached_)

    def attach(self, attr, signer):
        """ Attaches the submission to a new _Attr. The submission will be also
            be accepted.

        """
        self.attached_ = attr.id
        self.accept(signer)

    @classmethod
    def unacknowledged(cls):
        """ Gives Submissions that have not yet been reviewed """
        return [] # TODO


class Parameter(Obj):
    """ A parameter

        Attributes:
        name - the WOCE mnemonic
        aliases - other names for the parameter
        full_name - the full name of the parameter
        name_netcdf - the accepted name for the parameter in WOCE NetCDF format
        description - a description of the parameter
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
    def aliases(self):
        return self.get('aliases') or []

    @property
    def unit(self):
        return Unit.get_id(self.get('unit'))

    units = unit

    @property
    def bounds(self):
        bounds = self.get('bounds') or []
        if all(x is None for x in bounds):
            return []
        return bounds

    @property
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
    @property
    def order(self):
        order = self.get('order')
        return [Parameter.get_id(id) for id in order]
