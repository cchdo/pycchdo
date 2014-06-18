import sys
import os
import os.path
from shutil import rmtree
from contextlib import closing
from cgi import FieldStorage
from StringIO import StringIO
from json import JSONEncoder, loads, dumps
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    event, distinct,
    Table, Column, ForeignKey, 
    Integer, Unicode, String, Boolean, DateTime,
    )
from sqlalchemy.exc import DataError, ProgrammingError
from sqlalchemy.sql import (
    func, and_, not_, or_,
    )
from sqlalchemy.sql.expression import case, literal, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from sqlalchemy.orm import (
    relationship, scoped_session, sessionmaker, backref, aliased,
    )
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.collections import (
    collection, InstrumentedSet, attribute_mapped_collection,
    )
from sqlalchemy.schema import DropSchema, CreateSchema, Index

from zope.sqlalchemy import ZopeTransactionExtension

import geojson

from shapely.geometry import asShape, shape, mapping
from shapely.wkt import loads as wktloads, dumps as wktdumps

from geoalchemy2.types import Geography 
from geoalchemy2.shape import to_shape, from_shape

from sqlalchemy_imageattach.context import current_store, store_context

from libcchdo.recipes.orderedset import OrderedSet
from libcchdo.fns import uniquify

from pycchdo.models import triggers
from pycchdo.models.attrmgr import AllowableMgr
from pycchdo.models.types import *
from pycchdo.models.filestorage import AdaptedFile, FSStore
from pycchdo.models.file_types import (
    DataFileTypes,
    data_file_descriptions,
    )
from pycchdo.util import drop_everything, is_valid_ip, timestamp_now
from pycchdo.log import getLogger, INFO


log = getLogger(__name__)
log.setLevel(INFO)


Base = declarative_base()
Meta = Base.metadata
Meta.schema = 'pycchdo'

Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)


def reset_database(engine):
    """Clears the database and recreates schema."""
    drop_everything(engine)
    try:
        engine.execute(DropSchema(Meta.schema, cascade=True))
    except ProgrammingError:
        pass
    engine.execute(CreateSchema(Meta.schema))
    Meta.create_all(engine)


def reset_fs(fsstore):
    fss_root = fsstore.path
    for root, dirs, files in os.walk(fss_root):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            rmtree(os.path.join(root, d))


def _repr_state(obj):
    if obj.accepted:
        return 'acc'
    if obj.ts_j:
        return 'rej'
    try:
        if obj.change.ts_ack:
            return 'ack'
    except Exception:
        pass
    return 'sug'


class OnceAtEnd(object):
    ran = False
    at_end = []

    @classmethod
    def register(cls, func):
        cls.at_end.append(func)

    @classmethod
    def run(cls):
        if cls.ran:
            return
        cls.ran = True
        for func in cls.at_end:
            func()


once_at_end = OnceAtEnd()


class MixinCreation(object):
    """Mixin regarding the creation time and person."""
    @hybrid_property
    def ctime(cls):
        return cls.ts_c


def query_in_order_ids(query, field, ids):
    """Append to a query to filter by ids in order."""
    order = case([(field == value, literal(index)) for index, value in enumerate(ids)])
    return query.filter(field.in_(ids)).order_by(order)


class DBQueryable(object):
    """Mixin to obtain query on this class for global database session."""
    @classmethod
    def query(cls, *args):
        """Return a query for this class on the global database session."""
        if args:
            return DBSession.query(*args)
        return DBSession.query(cls)

    @classmethod
    def get_all_by_ids(cls, *ids):
        """Return the instances in the order of the ids."""
        # Fast track empty lists, avoid SQL generation error
        ids = filter(None, ids)
        if not ids:
            return []
        return query_in_order_ids(cls.query(), cls.id, ids).all()

    @classmethod
    def get_id(cls, id):
        log.warn(u'get_id is deprecated')
        return cls.get_all_by_ids(id)

    @classmethod
    def by_ids(cls, ids):
        log.warn(u'by_ids is deprecated')
        return cls.get_all_by_ids(*ids)


class Note(Base, DBQueryable, MixinCreation):
    """A Note that can be attached to any Change.

    A Change may have many Notes.

    Parameters::

    body - the actual note
    action - the action taken
    data_type - the type of data that was changed
    subject - a nice summary
    discussion - Setting this True makes the note only visible for mergers.
                     
    """
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True)

    p_id_c = Column(Integer, ForeignKey('people.id'))
    p_c = relationship('Person', foreign_keys=[p_id_c])
    ts_c = Column(DateTime, default=func.now())

    body = Column(Unicode)
    action = Column(Unicode)
    data_type = Column(Unicode)
    subject = Column(Unicode)
    discussion = Column(Boolean)

    change_id = Column(Integer, ForeignKey('changes.id'))
    change = relationship('Change',
        backref=backref('_notes', uselist=True, lazy='dynamic',
                        cascade='all, delete-orphan'))

    import_id = Column(String)

    def __init__(self, person, body=None, action=None, data_type=None,
                 subject=None, discussion=False):
        self.p_c = person
        self.ts_c = func.now()
        self.body = body
        self.action = action
        self.data_type = data_type
        self.subject = subject
        self.discussion = discussion

    def __eq__(self, other):
        return (
            self.p_c == other.p_c and 
            self.ts_c == other.ts_c and 
            self.body == other.body and 
            self.action == other.action and 
            self.data_type == other.data_type and 
            self.subject == other.subject and 
            self.discussion == other.discussion)

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'Note({0}, {1!r})'.format(self.id, self.subject)

    def __repr__(self):
        return u'Note({0}, {1!r}, {2})'.format(self.id, self.subject, self.discussion)


class ChangePermission(Base):
    """Permissions required to read or write an attribute.

    This function is used for situations such as archives of old data that
    should only be read by staff or Argo data.

    Permissions for attribute Changes are subdivided into read and write.

    """
    __tablename__ = 'permissions'
    change_id = Column(ForeignKey('changes.id'), primary_key=True)
    perm_type = Column(
        Enum('read', 'write', name='perm_type'), default='read',
        primary_key=True)
    permission = Column('perm', Unicode, primary_key=True)

    def __init__(self, perm_type, permission):
        self.perm_type = perm_type
        self.permission = permission


def filter_query_change(query, state=None, replaced=False, query_modifier=None):
    """Modify a query for Changes.

    state - enum: unjudged, unacknowledged, pending, accepted
    replaced - if True, requires that the Changes have an accepted value

    """
    query = query.filter(and_(Change.attr != None, Change.value != None))

    if state == 'unjudged':
        query = query.filter(and_(Change.ts_j == None, Change.p_j == None))
    elif state == 'unacknowledged':
        query = query.filter(and_(
            Change.ts_ack == None, Change.p_ack == None, 
            Change.ts_j == None, Change.p_j == None))
    elif state == 'pending':
        query = query.filter(and_(
            Change.ts_ack != None, Change.p_ack != None,
            Change.ts_j == None, Change.p_j == None))
    elif state == 'accepted':
        query = query.filter(and_(
            Change.ts_j != None, Change.p_j != None, Change.accepted))

    if replaced:
        query = query.filter(Change._value_accepted != None)

    if query_modifier:
        query = query_modifier(query)
    return query


def filter_changes_data(changes, data=True):
    """Filter Changes to those pertaining to attributes that store Files.

    """
    func = lambda change: change.obj.attr_type(change.attr) == File
    if not data:
        func = lambda change: change.obj.attr_type(change.attr) != File
    return filter(func, changes)


class ChangePersonTransformer(Comparator):
    """Transform a query for Change to enable queries against its Person."""
    def __init__(self, cls):
        self._aliased = aliased(Person, name='chgp')
        self._aliased_change = Obj.change._aliased

    @property
    def join(self):
        def go(q):
            return q.join(self._aliased,
                self._aliased.id == self._aliased_change.p_id_c)
        return go


class Change(Base, MixinCreation, DBQueryable):
    """A log of each change in the database.

    Each change can be proposed, acknowledged, accepted, or rejected.

    There are two main kinds of changes: Objs and their attributes.

    An Obj creation is differentiated in the log by total lack of attr name and
    value. An attribute change includes both.

    Attribute values are serialized; those with Objs only save the Obj ids and
    reload the Obj when deserializing. This is acceptable because the Obj will
    have to be persisted before serialization and will remain in perpetuity. 

    """
    __tablename__ = 'changes'
    id = Column(Integer, primary_key=True)

    obj_id = Column(Integer, ForeignKey('objs.id'), nullable=False)
    obj = relationship('Obj',
        backref=backref(
            '_changes', lazy='dynamic', cascade='all, delete-orphan'))

    attr = Column(String, default=None)
    _value = Column('value', Unicode, default=None)
    _value_accepted = Column('value_accepted', Unicode, default=None)

    accepted = Column(Boolean, default=False)

    deleted = Column(Boolean, default=False)

    p_id_c = Column(Integer, ForeignKey('people.id'))
    _p_c = relationship('Person', foreign_keys=[p_id_c])
    ts_c = Column(DateTime, default=func.now())

    p_id_ack = Column(Integer, ForeignKey('people.id'))
    p_ack = relationship('Person', foreign_keys=[p_id_ack])
    ts_ack = Column(DateTime)

    p_id_j = Column(Integer, ForeignKey('people.id'))
    p_j = relationship('Person', foreign_keys=[p_id_j])
    ts_j = Column(DateTime)

    permissions_read_ = relationship(
        ChangePermission,
        primaryjoin='and_(ChangePermission.change_id == Change.id, '
                    "ChangePermission.perm_type == 'read')",
        cascade='all, delete-orphan')
    permissions_read = association_proxy(
        'permissions_read_', 'permission',
        creator=lambda x: ChangePermission('read', x))
    permissions_write_ = relationship(
        ChangePermission,
        primaryjoin='and_(ChangePermission.change_id == Change.id, '
                    "ChangePermission.perm_type == 'write')",
        cascade='all, delete-orphan')
    permissions_write = association_proxy(
        'permissions_write_', 'permission',
        creator=lambda x: ChangePermission('write', x))

    requests = relationship(
        'RequestFor', backref='change', cascade='all, delete-orphan')

    # Used mainly for file import
    file_holder_type = 'c'
    import_id = Column(String)

    __table_args__ = (
        Index('idx_changes_accepted_attr', 'accepted', 'attr'),
        )

    def __init__(self, obj, person, attr, value):
        self.obj = obj
        self.attr = attr
        log.debug(u'creating {0}.{1}={2!r}'.format(obj, attr, value))
        if attr is not None or value is not None:
            self.value = value

        self.p_c = person
        self.ts_c = func.now()

    def _get_value(self):
        """Return the value that is most appropriate.

        If value_accepted is set, a different value than the one suggested has
        been accepted. Prefer that one over the original.

        """
        if self._value_accepted is None:
            return self._value
        else:
            return self._value_accepted

    @property
    def value(self):
        """Deserialize the value from the database.

        If the accepted_value has been set, will return the deserialized
        instance of the accepted_value, otherwise will return the original
        suggested value deserialized.

        """
        return self.obj.deserialize(self.attr, self._get_value())

    @value.setter
    def value(self, val):
        """Serialize the value so it can be stored in the database.

        """
        self._value = self.obj.serialize(self.attr, val)

    @property
    def value_original(self):
        """Deserialize the suggested value from the database."""
        return self.obj.deserialize(self.attr, self._value)

    @property
    def value_accepted(self):
        """Deserialize the accepted value from the database."""
        return self.obj.deserialize(self.attr, self._value_accepted)

    @value_accepted.setter
    def value_accepted(self, val):
        """Serialize the value so it can be stored in the database.

        """
        self._value_accepted = self.obj.serialize(self.attr, val)

    def _set_value(self, val):
        """Set the value and recache.

        Useful for internally modifying a change and propagating its effects.

        """
        if self._value_accepted is None:
            self.value = val
        else:
            self.value_accepted = val
        self.set_cache()

    @hybrid_property
    def is_obj(self):
        """Return whether the change is an Obj."""
        return self.attr is None and self._value is None

    def is_judged(self):
        return self.ts_j is not None

    def is_acknowledged(self):
        return self.ts_ack is not None

    def is_accepted(self):
        return self.is_judged() and self.accepted

    def is_rejected(self):
        return self.is_judged() and not self.accepted

    def set_cache(self):
        """Set the value cache for the Obj."""
        try:
            self.obj._set_cache(self.attr, self.value)
        except (DataError, TypeError):
            # If the value does not store well in the Obj cache, we'll have to
            # leave it in string form. Communicate to the Obj that the cache is
            # not valid.
            delattr(self.obj, self.attr)

    def accept(self, person, replacement=None):
        """Accept a Change.

        This means bookkeeping as well as updating the Obj's (if any) attribute
        cached value. If a replacement value is offered, it will be serialized
        and stored as well.

        """
        self.p_j = person
        self.ts_j = timestamp_now()
        self.accepted = True

        if replacement is not None:
            self.value_accepted = replacement

        log.debug(u'accepting {0!r}:{1!r}'.format(self, self.value))

        if self.is_obj:
            self.obj.accepted = True
            self.obj.ts_j = timestamp_now()
        else:
            self.set_cache()

    def acknowledge(self, person):
        self.p_ack = person
        self.ts_ack = timestamp_now()

    def reject(self, person):
        self.p_j = person
        self.ts_j = timestamp_now()
        self.accepted = False

        if self.is_obj:
            self.obj.accepted = False

    @classmethod
    def only_if_accepted_is(cls, accepted=True):
        """Return a query for this class only when accepted or not."""
        return cls.query().filter(cls.accepted == accepted)

    @property
    def notes(self):
        return self._notes.all()

    @property
    def notes_public(self):
        return self._notes.filter(not_(Note.discussion)).all()

    @property
    def notes_discussion(self):
        return self._notes.filter(Note.discussion).all()

    @hybrid_property
    def p_c(self):
        return self._p_c

    @p_c.setter
    def p_c(self, value):
        self._p_c = value

    @p_c.comparator
    def p_c(cls):
        # memoize a ChangePersonTransformer per class
        if '_cpt' not in cls.__dict__:
            cls._cpt = ChangePersonTransformer(cls)
        return cls._cpt

    @classmethod
    def filtered(cls, state=None, replaced=False, query_modifier=None):
        query = filter_query_change(
            cls.query(), state, replaced, query_modifier)
        return query.all()

    @classmethod
    def filtered_data(cls, state=None, replaced=False, query_modifier=None):
        return filter_changes_data(
            cls.filtered(state, replaced, query_modifier))

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'{1}.{2}(0)={3!r}'.format(
            _repr_state(self), self.obj, self.attr, self.value)

    def __repr__(self):
        return u'<Change({0}, {1}, {2})>'.format(
            _repr_state(self), self.obj, self.attr, self.value)


class RequestFor(Base):
    """Store HTTP requests for a Change."""
    __tablename__ = 'requests_for'

    id = Column(Integer, primary_key=True)

    change_id = Column(ForeignKey('changes.id'))
    # relationship is declared in Change

    dt = Column(DateTime)
    ua = Column(String)
    ip = Column(String)

    request = Column(Unicode)

    def __init__(self, request):
        """Takes a webob.Request and stores information relevant to tracking.

        Parameters:
        request - the webob.Request

        """
        try:
            self.request = unicode(request)
            self.dt = request.date
            self.ip = request.remote_addr
            self.ua = request.user_agent
            if not type(self.dt) is datetime:
                raise ValueError()
            if not is_valid_ip(self.ip):
                raise ValueError()
        except (AttributeError, ValueError):
            pass

    def __eq__(self, other):
        return (self.dt.replace(tzinfo=None) == other.dt.replace(tzinfo=None) and
                self.ip == other.ip and
                self.ua == other.ua and
                self.request == other.request)


class ExtrasJSONEncoder(JSONEncoder):
   def default(self, obj):
       if isinstance(obj, Decimal):
           return float(obj)
       if not isinstance(obj, list) and hasattr(obj, '__iter__'):
           return list(obj)
       # Let the base class default method raise the TypeError
       return JSONEncoder.default(self, obj)


class Serializer(object):
    @classmethod
    def serialize(cls, value):
        return dumps(value, cls=ExtrasJSONEncoder)

    @classmethod
    def deserialize(cls, value):
        return loads(value)


class SerializerDateTime(Serializer):
    # FIXME +%z preserve the timezone, if any. Is this necessary?
    format_string = '%Y-%m-%dT%H:%M:%S.%f'
    @classmethod
    def serialize(cls, value):
        try:
            value = {'type': 'dt', 'val': value.strftime(cls.format_string)}
        except AttributeError:
            value = {'type': 'u', 'val': value}
        return super(SerializerDateTime, cls).serialize(value)

    @classmethod
    def deserialize(cls, value):
        serial = loads(value)
        if serial['type'] == 'dt':
            try:
                return datetime.strptime(serial['val'], cls.format_string)
            except ValueError:
                return None
        elif serial['type'] == 'u':
            return serial['val']
        else:
            log.error(u'Invalid serialization for datetime: {0!r}'.format(serial))
            return None


class SerializerTrack(Serializer):
    @classmethod
    def serialize(cls, value):
        if isinstance(value, list):
            value = geojson.LineString(value)
        return wktdumps(asShape(value))

    @classmethod
    def deserialize(cls, value):
        return wktloads(value)


class SerializerObj(Serializer):
    @classmethod
    def serialize(cls, value):
        try:
            return dumps({'type': 'obj', 'obj_type': type(value).__name__,
                          'val': value.id})
        except AttributeError:
            return dumps({'type': 'u', 'val': value})

    @classmethod
    def Deserializer(cls, obj):
        return lambda value: cls.deserialize(obj, value)

    @classmethod
    def deserialize(cls, obj, value):
        serial = loads(value)
        if serial['type'] == 'obj':
            return obj.query().get(serial['val'])
        elif serial['type'] == 'u':
            return serial['val']
        else:
            log.error(u'Invalid serialization for obj: {0!r}'.format(serial))
            return None


class SerializerFSFile(SerializerObj):
    @classmethod
    def serialize(cls, value):
        if not isinstance(value, FSFile):
            value = FSFile.from_fieldstorage(value)
        return super(SerializerFSFile, cls).serialize(value)

    @classmethod
    def deserialize(cls, value):
        return super(SerializerFSFile, cls).deserialize(FSFile, value)


class SerializerObjs(SerializerObj):
    @classmethod
    def serialize(cls, value):
        try:
            ids = [obj.id for obj in value]
            try:
                otype = type(value[0]).__name__
            except (TypeError, IndexError):
                otype = 'Obj'
            return dumps({'type': 'objs', 'obj_type': otype, 'val': ids})
        except AttributeError:
            return dumps({'type': 'u', 'val': value})

    @classmethod
    def deserialize(cls, obj, value):
        serial = loads(value)
        if serial['type'] == 'objs':
            return obj.get_all_by_ids(*serial['val'])
        elif serial['type'] == 'u':
            return serial['val']
        else:
            log.error(u'Invalid serialization for objs: {0!r}'.format(serial))
            return None


class AllowableSerialMgr(AllowableMgr):
    """Manages which attributes are tracked as well as serialization."""

    __serializers = {}
    __deserializers = {}
        
    @classmethod
    def allow_attr(cls, key, attr_type, name=None, batch=False):
        obj_type = None
        if type(attr_type) == list:
            main_type = attr_type[0]
            # Rewrite so Allowable Mgr knows how to deal
            if type(main_type) == tuple:
                obj_type = main_type[1]
                main_type = attr_type[0] = main_type[0]
        else:
            main_type = attr_type
            if type(main_type) == tuple:
                obj_type = main_type[1]
                main_type = attr_type = main_type[0]

        super(AllowableSerialMgr, cls).allow_attr(key, attr_type, name, batch)

        if main_type == ID:
            obj = globals()[obj_type]
            cls.register_serializer_pair(
                key, SerializerObj.serialize, SerializerObj.Deserializer(obj))
        elif main_type == IDList:
            obj = globals()[obj_type]
            cls.register_serializer_pair(
                key, SerializerObjs.serialize, SerializerObjs.Deserializer(obj))
        elif main_type == TextList:
            cls.register_serializer_pair(key, Serializer)
        elif main_type == DateTime:
            cls.register_serializer_pair(key, SerializerDateTime)
        elif main_type == File:
            cls.register_serializer_pair(key, SerializerFSFile)
        elif main_type == LineString:
            cls.register_serializer_pair(key, SerializerTrack)
        else:
            cls.register_serializer_pair(key, Serializer)

    @classmethod
    def register_serializer_pair(cls, attr, serializer, deserializer=None):
        """Register serializer/deserializer for the attribute key."""
        attrdef = cls._allowed_attrs_dict()[attr]

        # If only one argument given for serializers, assume it is a Serializer
        # object
        if deserializer is None:
            deserializer = getattr(serializer, 'deserialize')
            serializer = getattr(serializer, 'serialize')
        try:
            serializer = attrdef['serializer']
            log.warn(u'Serializer   for {0}.{1} already registered: {2}'.format(
                cls, attr, serializer))
        except KeyError:
            attrdef['serializer'] = serializer
        try:
            deserializer = attrdef['deserializer']
            log.warn(u'Deserializer for {0}.{1} already registered: {2!r}'.format(
                cls, attr, deserializer))
        except KeyError:
            attrdef['deserializer'] = deserializer

    def serialize(self, attr, value):
        """Serialize the value from a python object to a string."""
        try:
            attrdef = self._allowed_attrs_dict()[attr]
        except KeyError:
            raise ValueError(
                u'{0} cannot be stored as {1}'.format(value, attr))
        try:
            return attrdef['serializer'](value)
        except KeyError:
            if not isinstance(value, basestring):
                if attr is not None or value is not None:
                    raise ValueError(
                        u'No serializer for {0}.{1}: {2!r}'.format(
                        self, attr, value))
            return value
        except Exception, err:
            log.error(u'Unable to serialize {0}.{1}: {2!r}: {3!r}'.format(
                self, attr, value, err))
            raise

    def deserialize(self, attr, value):
        """Deserialize the value from a string to a python object."""
        try:
            attrdef = self._allowed_attrs_dict()[attr]
            return attrdef['deserializer'](value)
        except KeyError:
            return value
        except Exception, err:
            log.error(u'Unable to deserialize: {0}'.format(err))
            raise


class Creatable(object):
    """Creatable objects can be created and added to the database at once."""
    @classmethod
    def create(cls, *args, **kwargs):
        """Create and add an object to the database."""
        obj = cls(*args, **kwargs)
        DBSession.add(obj)
        DBSession.flush()
        return obj


class ObjChangeTransformer(Comparator):
    """Transform a query for Obj to enable queries against its Change."""
    def __init__(self, cls):
        self._aliased = aliased(Change, name='ochg')

    @property
    def join(self):
        def go(q):
            return q.join(self._aliased, and_(
                self._aliased.obj_id == Obj.id, self._aliased.attr.is_(None),
                self._aliased._value.is_(None)))
        return go


class Obj(Base, DBQueryable, Creatable, AllowableSerialMgr):
    """

    The ideal is to provide an Obj with the relevant current attr values stored
    in the database to allow for quicker queries against them. The suggested and
    rejected Changes should still be accessible through the interfaces provided.

    All Obj notes are stored against the Obj's Change.

    """
    __tablename__ = 'objs'

    id = Column(Integer, primary_key=True)
    obj_type = Column(String, nullable=False)

    accepted = Column(Boolean, default=False)
    ts_j = Column(DateTime)

    import_id = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_on': obj_type,
        'polymorphic_identity': 'obj',
        }

    @hybrid_property
    def uid(self):
        """A unified ID that can be adapted for alternate ids.

        E.g. Cruise's are supposed to have an alternate ID called ExpoCode.
        """
        return self.id

    @property
    def mtime(self):
        """Last modified time.
        This is either the object creation time or the latest attribute judgment
        time.

        """
        creation_time = self.change.ts_c
        accepted = self.changes_query(state='accepted').order_by(Change.ts_j.desc()).first()
        if not accepted:
            return creation_time
        last_attr_ctime = accepted.ts_j
        try:
            return max(creation_time, last_attr_ctime)
        except TypeError:
            return creation_time

    @hybrid_property
    def change(self):
        """Return the Change that created the Obj.

        """
        return self._changes.filter(Change.attr.is_(None)).filter(
            Change._value.is_(None)).first()

    @change.comparator
    def change(cls):
        # memoize a ObjChangeTransformer per class
        if '_oct' not in cls.__dict__:
            cls._oct = ObjChangeTransformer(cls)
        return cls._oct

    def changes_query(self, state=None, replaced=False, query_modifier=None):
        """Return a query for the Obj's attribute Changes.

        """
        return filter_query_change(
            self._changes, state, replaced, query_modifier)

    def changes(self, state=None, replaced=False, data=None):
        """Return the Obj's Changes excluding the one that created it."""
        changes = self.changes_query(state, replaced).all()
        if data is None:
            return changes
        else:
            return filter_changes_data(changes, data)

    @property
    def attr_keys(self):
        changes = self._changes.\
            with_entities(distinct(Change.attr), Change.ts_j).\
            order_by(Change.ts_j.desc())
        changes = changes.all()
        return uniquify(filter(None, [c[0] for c in changes]))

    def _filter_changes_attr(self, query, attr):
        return query.filter(Change.attr == attr).order_by(Change.ts_j.desc())

    def get_attr(self, attr):
        """Return the most recent accepted Change for key.

        Raises: KeyError if no changes.

        """
        change = self._filter_changes_attr(
            self.changes_query('accepted'), attr).first()
        if change is None:
            raise KeyError(attr)
        return change

    def get_attr_change(self, attr):
        """Return the last Change for this Obj's attr."""
        return self._filter_changes_attr(self._changes, attr).first()

    def get_attr_or(self, attr, default=None):
        """Return the most recent accepted Change for key or default."""
        try:
            return self.get_attr(attr)
        except KeyError:
            return default

    def get_attrs_or(self, attrs, default=None):
        """Return the most recent accepted Change for the keys or default."""
# TODO make sure this actually returns the most recently accepted Change for each attr
# I believe this may return all of them
        change = self.changes_query('accepted').filter(Change.attr.in_(attrs)).\
            order_by(Change.ts_j).all()
        return change

    def sugg(self, person, attr, value):
        """Suggest that an attribute's value should be."""
        change = Change(self, person, attr, value)
        DBSession.add(change)
        return change

    def set(self, person, attr, value):
        """Set the attribute's value."""
        change = self.sugg(person, attr, value)
        change.accept(person)
        return change

    def _set_cache(self, attr, value):
        """Set the attribute value to cache.

        In the case that multiple types are acceptable, we will have to check
        that the type is ok before storing, otherwise there will be a
        persistence error. If the type is not persistable in the cache, the
        cache should be set to None so that get() will attempt to load from
        Changes.

        """
        # Multiple acceptable types always end in Unicode. That is the
        # cache unpersistable type.
        if isinstance(self.attr_type(attr), list):
            if isinstance(value, basestring):
                setattr(self, attr, None)
                return
        try:
            setattr(self, attr, value)
        except AttributeError:
            # If the Obj does not declare this attribute, it doesn't really care
            # if the value is cached.
            pass

    def _get_cache(self, attr):
        """Attempt to get the attribute value from cache.

        Return None if there is an error and get() will attempt to load from
        Changes.

        """
        try:
            return getattr(self, attr)
        except AttributeError:
            return None

    def get(self, attr, default=None, force_original=False, force_change=False):
        """Get the attribute's value.

        default - the default value if unable to get value
        force_original - force the getter to return the original value of the
            Change. This implies force_change
        force_change - force the getter to return the last applicable Change
            instead of the cached version.

        """
        if force_original or force_change:
            try:
                change = self.get_attr(attr)
            except KeyError:
                return default
            if not change:
                return default
            if force_original:
                return change.value_original
            else:
                return change.value
        value = self._get_cache(attr)
        if value is not None:
            return value
        return self.get(attr, default, force_original, force_change=True)

    def delete(self, person, attr):
        """Set this attr to none."""
        return self.sugg(person, attr, None)

    def remove(self):
        """Delete this Obj from the database and remove its Changes."""
        # This option purges the Changes as well.
        # TODO Is this desirable because there would no longer be a log of that
        # obj's creation?
        DBSession.delete(self)

    @classmethod
    def propose(cls, person):
        """Propose a Change to add a new instance of this class."""
        change = Change(cls(), person, None, None)
        DBSession.add(change)
        DBSession.flush()
        return change

    @classmethod
    def create(cls, person):
        """Propose and accept a Change to add a new instance of this class."""
        change = cls.propose(person)
        change.accept(person)
        return change

    @property
    def notes(self):
        return self.change.notes

    @property
    def notes_public(self):
        return self.change.notes_public

    @property
    def notes_discussion(self):
        return self.change.notes_discussion

    def to_dict(self):
        """Return a dict representation of the Obj.

        This is used to present JSON.

        """
        return {
            'id': self.id,
            'obj_type': self.__class__.__name__,
        }

    def __repr__(self):
        return u'{cls}()'.format(cls=type(self))


once_at_end.register(lambda:
    Obj.allow_attr('import_id', String, 'Import ID'))


class Participant(Base, Creatable, DBQueryable):
    """A participant of a Cruise. 

    Participants are creatable for ease of adding. Otherwise, they would have to
    be manually persisted.

    A participant consists of role, person, and optionally institution.

    """
    __tablename__ = 'participants'

    id = Column(Integer, primary_key=True)

    role = Column(Unicode, nullable=False)

    cruise_id = Column(ForeignKey('cruises.id'))

    person_id = Column(ForeignKey('people.id'), nullable=False)
    person = relationship('Person', lazy='joined', backref='participants')

    institution_id = Column(Integer, ForeignKey('institutions.id'))
    institution = relationship('Institution', backref='participants')

    def __init__(self, role, person, institution=None):
        self.role = role
        self.person = person
        self.institution = institution

    def to_dict(self):
        return {
            'person': self.person_id,
            'institution': self.institution_id,
            'role': self.role}
    
    def equal_role_person(self, other):
        return self.role == other.role and self.person == other.person
    
    def __eq__(self, other):
        if self.equal_role_person(other):
            if self.institution:
                return self.institution == other.institution
            else:
                return bool(other.institution)
        return False

    def __hash__(self):
        return hash(u'{0}_{1}_{2}'.format(
            self.role, self.person_id, self.institution_id))

    def __repr__(self):
        return u'Participant({0}, {1}, {2})'.format(
            self.role, self.person, self.institution)
        

class Participants(InstrumentedSet):
    """The participants of a Cruise.

    This object acts like a dictionary keyed upon "roles".

    All mutators will suggest a new value for 'participants' and return the
    suggestion.

    This collection will also provide Person-Institution pairs when queried
    using with_role(role)

    Caution: it is possible to assign an invalid set when multiple role-person
    pairs have different institutions. The resulting set will have two
    role-persons with different institutions. This is not a problem for storage
    but is strange to interpret.
    
    """
    def __init__(self, *args, **kwargs):
        """Store Participants in order."""
        if args:
            part = args[0]
            if type(part) == Participants:
                data = part
            else:
                data = args
        else:
            data = []
        super(Participants, self).__init__(data)

    def add(self, value):
        """Override instrumented add to consider institution.

        If a participant has (role, person) already in the set but the set
        is missing an institution, update the one in the set instead of adding
        the new participant.

        """
        if value.institution:
            for part in self:
                if part.equal_role_person(value) and not part.institution:
                    part.institution = value.institution
                    return

        super(Participants, self).add(value)

    def with_role(self, role):
        """Return Participants for role."""
        return filter(lambda p: p.role == role, self)

    @property
    def roles(self, role=None):
        """Pairs of Persons and roles present in the map."""
        if role is None:
            participants = self
        else:
            participants = self[role]
        return [(p.person, p.role) for p in participants]

    def to_dict(self):
        return [ppp.to_dict() for ppp in self]

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'Participants({0!r})'.format(self)


class FSFile(Base, DBQueryable, AdaptedFile):
    """A file record that points to the filesystem file."""
    __tablename__ = 'fsfiles'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    import_path = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_identity': 'fsfile',
    }

    def __init__(self, fobj=None, filename=None, mimetype=None,
                 store=current_store):
        if not mimetype:
            mimetype = 'application/octet-stream'
        super(FSFile, self).__init__(mimetype=mimetype)
        self.file = fobj
        self.store = store
        self.name = unicode(filename)
        # TODO calculate md5 for etagging?

    @staticmethod
    def from_fieldstorage(fst):
        fobj = fst.file
        filename = fst.filename
        mime = fst.type
        fsf = FSFile(fobj, filename, mime)
        DBSession.add(fsf)
        DBSession.flush()
        return fsf

    def __unicode__(self):
        return u'FSFile({0}, {1!r})'.format(self.id, self.name)

    def __repr__(self):
        return unicode(self)


class Country(Obj):
    """Store references to countries based on ISO 3166-1 alpha 2 and 3."""
    __tablename__ = 'countries'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode)
    alpha2 = Column(String(2))
    alpha3 = Column(String(3))

    __mapper_args__ = {
        'polymorphic_identity': 'country',
    }

    def iso_code(self, alpha=None):
        """Return the country's ISO 3166 code.

        Depending on alpha, will return either the 2 or 3 character code.

        """
        if not alpha or alpha == 2:
            return self.alpha2
        elif alpha == 3:
            return self.alpha3
        return None

    @property
    def preferred_name(self):
        three = self.iso_code(3)
        if three:
            return three
        two = self.iso_code(2)
        if two:
            return two
        return self.name

    def merge(self, signer, *mergees):
        changes = Change.query().filter(Change.attr == 'country').all()
        for change in changes:
            if change.value in mergees:
                change._set_value(self)

        for mergee in mergees:
            mergee.remove()

    def to_dict(self):
        """Returns a dict representation of the Country."""
        rep = super(Country, self).to_dict()
        rep.update({
            'name': self.name,
            'alpha2': self.iso_code(),
            'alpha3': self.iso_code(3),
        })
        return rep

    def __unicode__(self):
        return u'Country({0}, {1!r})'.format(self.id, self.name)

    def __repr__(self):
        return unicode(self)


class Institution(Obj):
    __tablename__ = 'institutions'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode)
    phone = Column(Unicode)
    address = Column(Unicode)
    url = Column(Unicode)

    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id],
        backref="institutions")

    __mapper_args__ = {
        'polymorphic_identity': 'institution',
    }

    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        participants = Participant.query().\
            filter(Participant.institution_id.in_(mergee_ids)).all()
        for p in participants:
            p.institution = self

        pis = ParameterInformation.query().\
            filter(ParameterInformation.inst_id.in_(mergee_ids)).all()
        for pi in pis:
            pi.inst = self

        changes = Change.query().filter(Change.attr == 'institutions').all()
        for change in changes:
            insts = change.value
            new_insts = []
            replaced = False
            for inst in insts:
                if inst not in mergees:
                    new_insts.append(inst)
                else:
                    if not replaced:
                        new_insts.append(self)
                        replaced = True
            change._set_value(new_insts)

        changes = Change.query().filter(Change.attr == 'institution').all()
        for change in changes:
            if change.value in mergees:
                change._set_value(self)

        for mergee in mergees:
            mergee.remove()

    def to_dict(self):
        """Returns a dict representation of the Institution."""
        rep = super(Institution, self).to_dict()
        d = {
            'name': self.name,
        }
        if self.country:
            d['country'] = self.country.to_dict()
        rep.update(d)
        return rep

    def __repr__(self):
        return u'Institution({0!r})'.format(self.name)


once_at_end.register(lambda:
Institution.allow_attrs([
    ('name', Unicode),
    ('phone', Unicode),
    ('address', Unicode),
    ('url', Unicode, 'Link'),
    
    ('country', (ID, 'Country')),
    ]))


class Ship(Obj):
    __tablename__ = 'ships'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode)
    nodc_platform_code = Column(String)

    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id],
        backref="ships")

    __mapper_args__ = {
        'polymorphic_identity': 'ship',
    }

    def merge(self, signer, *mergees):
        changes = Change.query().filter(Change.attr == 'ship').all()
        for change in changes:
            if change.value in mergees:
                change._set_value(self)

        for mergee in mergees:
            mergee.remove()

    def to_dict(self):
        """Returns a dict representation of the Ship."""
        rep = super(Ship, self).to_dict()
        rep.update({
            'name': self.name,
            'nodc_platform_code': self.nodc_platform_code,
            'url': self.get('url', ''),
        })
        return rep

    def __unicode__(self):
        return u'Ship({0})'.format(self.name)

    def __repr__(self):
        return unicode(self)


once_at_end.register(lambda: 
Ship.allow_attrs([
    ('name', Unicode),
    ('nodc_platform_code', String, 'NODC Platform Code'),
    ('url', Unicode, 'Link'),
    
    ('country', (ID, 'Country')),
    ]))


class _PersonPermission(Base):
    """Permissions associated with a Person."""
    __tablename__ = 'person_permissions'
    person_id = Column(Integer, ForeignKey('people.id'), primary_key=True)
    permission = Column(Unicode, primary_key=True)

    def __init__(self, permission):
        self.permission = permission


class Person(Obj):
    """A Person in this system.

    People may be either verified or not. If they are associated with an ID
    provider via the attribute identifier then they are verified.

    People can also have a set of permissions. These are used to verify that
    they are privileged.

    """
    __tablename__ = 'people'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    identifier = Column(Unicode)
    name = Column(Unicode)

    email = Column(Unicode)

    institution_id = Column(Integer, ForeignKey('institutions.id'))
    institution = relationship('Institution', foreign_keys=[institution_id],
        backref=backref('people', uselist=True))

    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id],
        backref=backref('people', uselist=True))

    cruises = association_proxy('participants', 'cruise')

    _permissions = relationship(
        _PersonPermission, single_parent=True,
        lazy='joined', cascade='all, delete, delete-orphan')
    permissions = association_proxy('_permissions', 'permission')

    # Legacy name parts
    name_last = Column(Unicode)
    name_first = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_identity': 'person',
    }

    def set_id_names(self, identifier=None, name=None, name_last=None,
                     name_first=None):
        self.identifier = identifier
        self.name = name
        self.name_last = name_last
        self.name_first = name_first
        if self.name_last or self.name_first and not self.name:
            self.name = ' '.join(
                filter(None, (self.name_first, self.name_last)))
        if self.identifier is None and self.name is None:
            raise ValueError(
                'Person must be initialized with either identifier or names.')

    @hybrid_property
    def full_name(cls):
        return cls.name

    def is_verified(self):
        return self.identifier is not None

    def is_authorized(self, perms):
        """Check whether the person has sufficient permissions."""
        if not perms:
            return True
        try:
            permissions = self.permissions
            if 'staff' in permissions:
                return True
            return any(group in permissions for group in perms)
        except AttributeError:
            return False
        return False

    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]
        cs = Change.query().filter(Change.p_id_c.in_(mergee_ids)).all()
        for c in cs:
            c.p_c = self
        cs = Change.query().filter(Change.p_id_ack.in_(mergee_ids)).all()
        for c in cs:
            c.p_ack = self
        cs = Change.query().filter(Change.p_id_j.in_(mergee_ids)).all()
        for c in cs:
            c.p_j = self
        changes = Change.query().filter(Change.obj_id.in_(mergee_ids)).all()
        for change in changes:
            change.obj = self

        notes = Note.query().filter(Note.p_id_c.in_(mergee_ids)).all()
        for note in notes:
            note.p_c = self

        pis = ParameterInformation.query().\
            filter(ParameterInformation.pi_id.in_(mergee_ids)).all()
        for pi in pis:
            pi.pi = self

        perms = OrderedSet(self.permissions)
        for mergee in mergees:
            perms |= OrderedSet(mergee.permissions)
        self.permissions = list(perms)

        participants = Participant.query().\
            filter(Participant.person_id.in_(mergee_ids)).all()
        cruises = []
        for p in participants:
            pps = list(p.cruise.participants)
            try:
                idx = pps.index(Participant(p.role, self))
                pp = pps[idx]
                if pp.institution and p.institution:
                    log.warn(u'Cannot merge role-persons with different '
                             'institution {0} {1}'.format(
                        pp.institution, p.institution))
                else:
                    if p.institution:
                        pp.institution = p.institution
            except ValueError:
                p.person = self

        for mergee in mergees:
            mergee.remove()

    @classmethod
    def propose(cls, sponsor=None):
        """Propose a new Person.

        Override because a Person can be their own sponsor.

        """ 
        person = cls()
        if sponsor is None:
            sponsor = person
        change = Change(person, sponsor, None, None)
        DBSession.add(change)
        DBSession.flush()
        return change

    @classmethod
    def create(cls, sponsor=None):
        """Create a new Person.

        Override because a Person can be their own sponsor.

        """ 
        change = cls.propose(sponsor)
        if sponsor is None:
            sponsor = change.obj
        change.accept(sponsor)
        return change

    def to_dict(self):
        """Returns a dict representation of the Person.

        """
        rep = super(Person, self).to_dict()
        rep.update({
            'identifier': self.get('identifier', None),
            'name': self.name,
            'email': self.email,
        })
        return rep

    def __unicode__(self):
        return u'Person(identifier={0!r}, name={1!r})'.format(
            self.identifier, self.name)

    def __repr__(self):
        return u'Person({0}, {1!r})'.format(
            _repr_state(self), self.name)


once_at_end.register(lambda:
Person.allow_attrs([
    ('title', Unicode),
    ('job_title', Unicode),
    ('phone', Unicode),
    ('fax', Unicode),
    ('address', Unicode),
    
    ('institution', (ID, 'Institution')),
    ('country', (ID, 'Country')),
    
    ('programs', (IDList, 'Collection')),

    # Legacy password parts
    ('password_hash', String),
    ('password_salt', String),
    ]))


class MultiName(object):
    """MultiName mixin for multiple possible names.

    The first stored name is taken as the canonical name.

    TODO perhaps Institutions and Ships may also have multiple names. For now
    let them have just one canonical name.

    """
    @classmethod
    def get_all_by_name(cls, name):
        """Returns all collections that match the given name.

        Parameters:
            name - either a string or a regular expression object
        
        """
        # TODO handle regular expression names
        return DBSession.query(cls).filter(cls.names.contains(name)).all()


class _CollectionName(Base):
    __tablename__ = 'collection_names'
    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collections.id'))
    name = Column(Unicode)

    def __init__(self, name):
        self.name = name


class _CollectionBasin(Base):
    __tablename__ = 'collection_basins'
    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey('collections.id'))
    basin = Column(Unicode)

    def __init__(self, basin):
        self.basin = basin


class Collection(MultiName, Obj):
    """Essentially tags for Cruises.
    
    A Cruise may belong to Basin Collection, WOCE line Collection, etc.
        
    A Collection will also include a type as part of its identifier to
    differentiate between the fields it came from in the original database.

    Parameters::
    names - names associated with the collection. The first name in the list is
        the canonical name.
    type - identifier of WOCE line, group, program, basin
    basins - a list of any combination of atlantic, arctic, pacific,
        indian, southern. Having this attribute designates the collection as
        a spatial_group.
    
    """
    __tablename__ = 'collections'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    type = Column(Unicode)

    _names = relationship('_CollectionName', lazy='joined', uselist=True)
    names = association_proxy('_names', 'name')

    _basins = relationship('_CollectionBasin', lazy='joined', uselist=True)
    basins = association_proxy('_basins', 'basin')

    date_start = Column(DateTime)
    date_end = Column(DateTime)
    url = Column(Unicode)

    institution_id = Column(ForeignKey('institutions.id'))
    institution = relationship('Institution', foreign_keys=[institution_id])

    country_id = Column(ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id])

    __mapper_args__ = {
        'polymorphic_identity': 'collection',
    }

    @property
    def name(self):
        try:
            return self.names[0]
        except IndexError:
            return None

    def merge(self, signer, *mergees):
        """Merge other Collections into this one."""
        names = OrderedSet(self.names)
        types = OrderedSet(filter(None, [self.type]))
        basins = OrderedSet(self.basins)
        cruises = OrderedSet()
        mergee_ids = OrderedSet()
        for mergee in mergees:
            names |= OrderedSet(mergee.names)
            if mergee.type:
                types.add(mergee.type)
            mergee_ids.add(mergee.id)
            cruises |= OrderedSet(mergee.cruises)
            basins |= OrderedSet(mergee.basins)
        names = list(names)

        if names != self.names:
            self.set(signer, 'names', names)

        # If the current collection doesn't have a type, pick up the type of
        # first mergee.
        if types:
            new_type = list(types)[0]
            if len(types) > 1:
                log.warn(u'Merging {0} with types {1}. Picked {2}'.format(
                    self, types, new_type))
            if new_type != self.type:
                self.set(signer, 'type', new_type)

        if basins:
            self.set(signer, 'basins', list(basins))

        # Cruises referencing mergees via collections need to be redirected to
        # this collection instead.
        for cruise in cruises:
            colls = OrderedSet(cruise.collections)
            colls = colls - OrderedSet(mergees)
            change = cruise.get_attr('collections')
            change._set_value(colls)

        for mergee in mergees:
            mergee.remove()

    def to_dict(self):
        """Returns a dict representation of the Collection."""
        rep = super(Collection, self).to_dict()
        rep.update({
            'names': self.names,
            'type': self.type,
            'basins': self.basins,
        })
        return rep

    def __repr__(self):
        return u'Collection({0}, {1}, {2}, {3})'.format(
            _repr_state(self), self.names, self.type, self.basins)


once_at_end.register(lambda:
Collection.allow_attrs([
    ('type', Unicode),
    ('basins', TextList),
    ('names', TextList),
    ('date_start', [DateTime, Unicode], 'Start Date'), 
    ('date_end', [DateTime, Unicode], 'End Date'), 

    ('url', Unicode), 

    ('institution', (ID, 'Institution')), 
    ('country', (ID, 'Country')), 
    ]))


class Unit(Obj):
    """A unit for parameters.

    Attributes::

    name - The name for a unit
    mnemnoic - the WOCE mnemonic for the unit

    """
    __tablename__ = 'units'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode)
    mnemonic = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_identity': 'unit',
    }

    def to_dict(self):
        return {
            'unit': {
                'def': self.get('name'),
                'aliases': [
                    {'name': {'singular': self.get('mnemonic')}}
                ]
            }
        }


once_at_end.register(lambda:
Unit.allow_attrs([
    ('name', Unicode),
    ('mnemonic', Unicode),
    ]))


class _ParameterAlias(Base):
    __tablename__ = 'parameter_aliases'
    id = Column(Integer, primary_key=True)
    parameter_id = Column(Integer, ForeignKey('parameters.id'))
    alias = Column(Unicode)

    def __init__(self, alias):
        self.alias = alias


class Parameter(Obj):
    """A parameter that is measured.

    Attributes::

    name - the WOCE mnemonic
    aliases - other names for the parameter
    full_name - the full name of the parameter
    name_netcdf - the accepted name for the parameter in WOCE NetCDF format
    description - a description of the parameter
    format - a C format string. This should actually be the number of
        significant figures but this is how the data was stored.
    unit - the unit for the parameter
    bounds - a tuple marking the generally acceptable range for the parameter
        for its primary unit
    in_groups_but_did_not_exist - marks the parameter as existing in the table
        parameter_groups but no where else in the database. Import use only.

    """
    __tablename__ = 'parameters'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode)

    _aliases = relationship('_ParameterAlias', lazy='joined', uselist=True)
    aliases = association_proxy('_aliases', 'alias')

    full_name = Column(Unicode)
    name_netcdf = Column(Unicode)

    description = Column(Unicode)

    _bounds = Column(Unicode)

    units_id = Column(Integer, ForeignKey('units.id'))
    units = relationship(Unit, foreign_keys=[units_id])

    in_groups_but_did_not_exist = Column(Unicode)

    __mapper_args__ = {
        'polymorphic_identity': 'parameter',
    }

    @hybrid_property
    def unit(self):
        return self.units

    @property
    def bounds(self):
        if self._bounds is None:
            return []
        bounds = loads(self._bounds)

        # If all bounds are None, there are no bounds
        if all(x is None for x in bounds):
            return []
        return bounds

    @bounds.setter
    def bounds(self, value):
        self._bounds = dumps(value)

    @property
    def display_order(self):
        # TODO
        return 0

    def to_dict(self):
        response = {'parameter': {
            'name': self.get('name', ''),
            'aliases': filter(None,
                [self.get('name_netcdf'),
                 self.get('full_name')] + self.aliases),
            'format': self.get('format', ''),
            'bounds': self.bounds,
            },
            'description': self.get('description', None),
        }
        units = self.units
        if units:
            response['parameter']['units'] = units.to_dict()
        return response

    def __unicode__(self):
        return u'Parameter({0})'.format(self.name)

    def __repr__(self):
        return unicode(self)


once_at_end.register(lambda:
Parameter.allow_attrs([
    ('name', Unicode, 'WOCE mnemonic'),
    ('aliases', TextList),
    ('full_name', Unicode),
    ('name_netcdf', Unicode, 'WOCE NetCDF name'),
    ('description', Unicode),
    ('format', Unicode, 'C format string'),
    ('bounds', DecimalList),
    ('units', (ID, 'Unit')),
    ('in_groups_but_did_not_exist', Boolean), 
    ]))


class _ParameterGroupOrder(Base):
    __tablename__ = 'parametergroup_orders'
    id = Column(Integer, primary_key=True)
    pg_id = Column(Unicode, ForeignKey('parameter_groups.name'))
    parameter_id = Column(Integer, ForeignKey('parameters.id'))
    parameter = relationship(Parameter, lazy='joined', backref='parameter_groups')

    def __init__(self, parameter):
        self.parameter = parameter


class ParameterGroup(Obj):
    """Parameters are grouped together in a specific order.

    Attributes::

    name - the class
    order - the list of parameters in the order they should appear

    """
    __tablename__ = 'parameter_groups'
    
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    name = Column(Unicode, unique=True)
    _order = relationship(_ParameterGroupOrder, uselist=True, lazy="joined")
    order = association_proxy('_order', 'parameter')

    __mapper_args__ = {
        'polymorphic_identity': 'parameter_group',
    }

    def __unicode__(self):
        return u'ParameterGroup({0}, {1})'.format(self.name, self.order)

    def __repr__(self):
        return unicode(self)

once_at_end.register(lambda:
ParameterGroup.allow_attrs([
    ('name', Unicode),
    ('order', (IDList, 'Parameter')),
    ]))


class ParameterInformation(Base, DBQueryable):
    """Metadata about a parameter.

    Columns:

    parameter - the parameter
    status - the status of the parameter; one of the following: online,
        reformatted, submitted, not_measured, proposed, no_information
    pi - the principal investigator for the parameter on the cruise
    inst - the institution that the pi was operating for
    ts - some date attached to the status and PI of the parameter

    """
    __tablename__ = 'param_infos'

    id = Column(Integer, primary_key=True)

    parameter_id = Column(Integer, ForeignKey('parameters.id'))
    parameter = relationship('Parameter')
    status = Column(
        Enum('online', 'reformatted', 'submitted', 'not_measured', 'proposed',
             'no_information', name='status'))
    pi_id = Column(Integer, ForeignKey('people.id'))
    pi = relationship('Person')
    inst_id = Column(Integer, ForeignKey('institutions.id'))
    inst = relationship('Institution')
    ts = Column(DateTime)

    def __init__(self, parameter, status, pi, inst, ts):
        self.parameter = parameter
        self.status = status
        if pi:
            self.pi = pi
        if inst:
            self.inst = inst
        self.ts = ts
    
    def is_empty(self):
        """Return whether ParameterInformation has no details about parameter.

        """
        return (
            self.status is None and self.pi_id is None and
            self.inst_id is None and self.ts is None)

    def __eq__(self, other):
        return (
            self.parameter_id == other.parameter_id and
            self.status == other.status and
            self.pi_id == other.pi_id and
            self.inst_id == other.inst_id and 
            self.ts == other.ts
            )

    def __repr__(self):
        return u'ParameterInformation({0}, {1}, {2}, {3}, {4})'.format(
            self.parameter_id, self.status, self.pi_id,
            self.inst_id, self.ts)


class FileHolder(object):
    """Mixin to map value property to the file property.
    Also can return a list of cruises based on the cruise identifier.

    """
    @property
    def value(self):
        return self._file

    @value.setter
    def value(self, o):
        self.file = o

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, o):
        self._file = o

    @property
    def file_holder_type(self):
        if isinstance(self, Submission):
            return 's'
        elif isinstance(self, OldSubmission):
            return 'o'
        elif isinstance(self, ArgoFile):
            return 'a'
        else:
            raise ValueError(
                u'No file holder type assigned for {0}'.format(self))

    @classmethod
    def file_holder(cls, fht):
        if fht == 's':
            return Submission
        elif fht == 'o':
            return OldSubmission
        elif fht == 'a':
            return ArgoFile
        else:
            return Change

    def cruises_from_identifier(self):
        try:
            return Cruise.get_all_by_expocode(self.identifier)
        except AttributeError:
            return []


argo_file_requests_for = Table('argo_file_requests_for', Base.metadata,
    Column('argo_file_id', ForeignKey('argo_files.id')),
    Column('request_for_id', ForeignKey('requests_for.id')),
    )


class ArgoFile(Obj, FileHolder):
    """Files that are given to the CCHDO for Argo calibration only.

    THESE ARE NOT PUBLIC DATA and are only to be shown in the Argo Secure File
    Repository.

    There are two types of ArgoFile::

    1. Provided files

       These are given to us to be put online and appear nowhere else.

    2. Linked files

       These are actually part of the CCHDO holdings and need to exist as a
       link to the most recent version of the data.

    Columns::

    text_identifier - some text that makes the file quickly identifiable to a
        human. Usually an ExpoCode
    file - either an id that is the file in the filesystem or a tuple like
           (id, attribute) that describes which attr of which obj holds the
           file.
    description - a description of the file
    display - whether or not the file is meant to be visible

    """
    __tablename__ = 'argo_files'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    text_identifier = Column(Unicode)
    description = Column(Unicode)
    display = Column(Boolean)

    file_id = Column(Integer, ForeignKey('fsfiles.id'))
    _file = relationship(
        'FSFile', foreign_keys=[file_id], single_parent=True,
        cascade='all, delete-orphan')

    link_cruise_id = Column(Integer, ForeignKey('cruises.id'))
    link_cruise = relationship(
        'Cruise', primaryjoin='ArgoFile.link_cruise_id == Cruise.id')
    link_attr_key = Column(Unicode)

    requests_for = relationship(
        'RequestFor', secondary=argo_file_requests_for, single_parent=True,
        uselist=True, cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'argo_file',
    }

    @hybrid_property
    def identifier(self):
        return self.text_identifier

    @property
    def value(self):
        """Return the file that the ArgoFile refers to."""
        if self.link_cruise:
            return self.link_cruise.get(self.link_attr_key, None)
        return self.file

    @value.setter
    def value(self, f):
        self.file = f

    def link(self, cruise, attr_key):
        """Populates the ArgoFile as a linked file."""
        try:
            cruise.get(attr_key)
        except KeyError:
            raise ValueError('%s does not exist for %s' % (attr_key, cruise))
        self.link_cruise = cruise
        self.link_attr_key = attr_key


class OldSubmission(Obj, FileHolder):
    """An old submission imported for record keeping.

    Other information stored:

    * The creation timestamp is the create time for the submission record.
    * The judgment timestamp is the update time for the submission record.

    Since it appears that the submissions were created using a script, only the
    first encountered time is recorded.
    
    Columns::

    date - the date of the submission
    submitter - the name of the submitter. Format varies.
    line - the WOCE line number of the submission. May be other things.
    folder - the original folder name of the submission. This is mainly used to
        group the submission files together during import.
    file - a zip of the original files in the folder

    """
    __tablename__ = 'old_submissions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    submitter = Column(Unicode)
    line = Column(Unicode)
    folder = Column(Unicode)

    file_id = Column(Integer, ForeignKey('fsfiles.id'))
    _file = relationship(
        'FSFile', foreign_keys=[file_id], single_parent=True,
        cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'old_submission',
    }

    @hybrid_property
    def identifier(self):
        return None


submission_changes = Table('submission_changes', Base.metadata,
    Column('submission_id', Integer, ForeignKey('submissions.id')),
    Column('change_id', Integer, ForeignKey('changes.id')),
)


class Submission(Obj, FileHolder):
    """A Submission to the CCHDO.

    These interface with humans so they need intervention to make everything
    behaves nicely before going into the system.

    Columns::

    expocode
    ship_name
    line
    action
    type -- the type of submission {public, non-public, argo}
    cruise_date -- the date of the cruise being submitted
    file -- the file that is being suggested
    attached -- a list of Changes
        The Changes are human verified representations of this submission.

        SPECIAL CASE: This is set to a special attribute of a fake cruise during
        legacy import because there is no good way to determine it without human
        help.

    """
    __tablename__ = 'submissions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    expocode = Column(Unicode)
    ship_name = Column(Unicode)
    line = Column(Unicode)
    action = Column(Unicode)
    cruise_date = Column(DateTime)
    type = Column(Unicode)

    attached = relationship(Change, secondary=submission_changes, uselist=True,
        backref=backref('submission', uselist=False), lazy='joined',
        cascade='all, delete')

    file_id = Column(Integer, ForeignKey('fsfiles.id'))
    _file = relationship(
        'FSFile', foreign_keys=[file_id], single_parent=True,
        cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'submission',
    }

    @hybrid_property
    def identifier(self):
        return self.expocode

    def attach(self, signer, *attrs):
        """Attaches the submission to Changes and accepts the submission."""
        self.attached = list(attrs)
        self.change.accept(signer)

    @classmethod
    def unacknowledged(cls):
        """Return Submissions that have not yet been reviewed."""
        # TODO
        return []

    @classmethod
    def filtered(cls, sid=None, attached=None, argo_type=None):
        query = cls.query()
        if sid is not None:
            query = query.filter(Submission.id == sid)
        if attached is not None:
            if attached:
                query = query.filter(Submission.attached.any())
            else:
                query = query.filter(~Submission.attached.any())
        if argo_type is not None:
            if argo_type:
                query = query.filter(Submission.type == 'argo')
            else:
                query = query.filter(or_(Submission.type != 'argo',
                                         Submission.type == None))
        return query

    def __repr__(self):
        return u'<Submission({0}, {1}, {2!r})>'.format(
            self.identifier, self.type, self.attached)


uow_suggestions = Table('uow_suggestions', Base.metadata,
    Column('uow_id', Integer, ForeignKey('uows.id')),
    Column('change_id', Integer, ForeignKey('changes.id')),
)


uow_results = Table('uow_results', Base.metadata,
    Column('uow_id', Integer, ForeignKey('uows.id')),
    Column('change_id', Integer, ForeignKey('changes.id')),
)


class UOW(Base, DBQueryable):
    """A Unit of Work.

    Represents an update to a cruise's dataset through
    1. suggested changes - these are submitted data
    2. other data, supporting the result changes - processing documents
    3. result changes - final updated dataset

    A UOW is linked to a note on the cruise's history.

    """
    __tablename__ = 'uows'
    id = Column(Integer, primary_key=True)
    suggestions = relationship(
        'Change', secondary=uow_suggestions, backref=backref('uow'),
        lazy='joined')
    results = relationship('Change', secondary=uow_results, lazy='joined')
    support_id = Column(ForeignKey('fsfiles.id'))
    support = relationship(FSFile, lazy='joined')
    note_id = Column(ForeignKey('notes.id'))
    note = relationship('Note', backref=backref('uow'), lazy='joined')


cruise_collections = Table('cruise_collections', Base.metadata,
    Column('cruise_id', Integer, ForeignKey('cruises.id')),
    Column('collection_id', Integer, ForeignKey('collections.id')),
)


cruise_institutions = Table('cruise_institutions', Base.metadata,
    Column('cruise_id', Integer, ForeignKey('cruises.id')),
    Column('institution_id', Integer, ForeignKey('institutions.id')),
)


class _CruiseAlias(Base):
    __tablename__ = 'cruise_aliases'
    id = Column(Integer, primary_key=True)
    cruise_id = Column(Integer, ForeignKey('cruises.id'))
    alias = Column(Unicode)

    def __init__(self, alias):
        self.alias = alias


class _CruiseStatus(Base):
    __tablename__ = 'cruise_statuses'
    id = Column(Integer, primary_key=True)
    cruise_id = Column(Integer, ForeignKey('cruises.id'))
    status = Column(Unicode)

    def __init__(self, status):
        self.status = status


class _CruiseFileStatus(Base):
    __tablename__ = 'cruise_file_statuses'
    id = Column(Integer, primary_key=True)
    cruisefile_id = Column(Integer, ForeignKey('cruise_files.id'))
    status = Column(Unicode)

    def __init__(self, status):
        self.status = status


class _CruiseFile(Base):
    __tablename__ = 'cruise_files'
    id = Column(Integer, primary_key=True)
    cruise_id = Column(Integer, ForeignKey('cruises.id'))
    attr = Column(Unicode)

    file_id = Column(ForeignKey('fsfiles.id'))
    file = relationship(FSFile, lazy='joined')

    _statuses = relationship(_CruiseFileStatus, lazy='joined', uselist=True)
    statuses = association_proxy('_statuses', 'status')

    def __init__(self, attr, file=None, statuses=[]):
        self.attr = attr
        self.file = file
        self.statuses = statuses


class Cruise(Obj):
    """The basic unit of metadata storage.

    Adding files
    ============
    Files are acquired by PIs submitting their data.

    There are two cases for adding files to a Cruise:

    1. Through the submit form and then through moderator intervention
    2. Added directly to the cruise as a suggested update to a file type

    Submit form
    -----------
    Each file stored with a copy of the submission information in the form of a
    Submission object.

    Submission objects can then be connected to a particular attribute on a
    cruise as is done for direct suggestions. A human must provide the type of
    file being suggested. In this manner, they are similar to imported legacy
    Queue files.

    Imported legacy Queue files
    ---------------------------
    Imported Queue files are direct suggestions but are abnormal in that their
    keys are "data_suggestion". This is because there is no guaranteed way to
    determine the type of file being suggested. This is left to a human and will
    require the imported queue files to be updated accordingly.

    Direct suggestion
    -----------------
    A direct suggestion involves an attribute attached to a particular Cruise
    that has a key associated with a file type. This state is similar to the
    legacy queue state of "as-received", but is not visible anywhere until the
    attribute has been acknowledged.
        
    Once the attribute has been acknowledged, it becomes visible to the public
    along with any visible notes. This is synonymous with the legacy queue state
    of "as-received". Public or discussion notes may be made on these
    attributes. The acknowledger becomes the equivalent of the legacy queue file
    CCHDO contact.

    An acknowledged file attribute may be rejected, accepted, or even accepted
    with a different value. Accepting a file attribute results in the legacy
    queue state of "merged". The accepted value becomes the most recent version
    of the value for the given file.

    Parameters::
    basin - imported from "internal"

    """
    __tablename__ = 'cruises'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)
    expocode = Column(String)

    _aliases = relationship(_CruiseAlias, lazy='joined', uselist=True)
    aliases = association_proxy('_aliases', 'alias')

    _statuses = relationship(_CruiseStatus, lazy='joined', uselist=True)
    statuses = association_proxy('_statuses', 'status')

    files = relationship(_CruiseFile,
        collection_class=attribute_mapped_collection('attr'),
        cascade='all, delete-orphan')

    date_start = Column(DateTime)
    date_end = Column(DateTime)

    ship_id = Column(Integer, ForeignKey('ships.id'))
    ship = relationship(Ship, foreign_keys=[ship_id], lazy='joined', backref='cruises')
    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship(
        Country, foreign_keys=[country_id], lazy='joined', backref='cruises')

    collections = relationship(
        'Collection', secondary=cruise_collections, lazy='joined',
        backref=backref('cruises', lazy='joined'))
    institutions = relationship(
        'Institution', secondary=cruise_institutions, lazy='joined', backref='cruises')

    _track = Column(Geography(geometry_type='LINESTRING', srid=4326, dimension=2))

    participants = relationship(
        Participant, uselist=True, collection_class=Participants,
        backref='cruise',
        lazy='joined', cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'cruise',
    }

    DATA_STATUS_ENDING = '_status'

    @property
    def uid(self):
        """A cruise's uid is the ExpoCode unless it is a seahunt cruise."""
        expo = self.expocode
        if (not expo or not self.accepted or ' ' in expo or '/' in expo
                or '-' in expo):
            return super(Cruise, self).uid
        return expo

    @property
    def preliminary(self):
        """Tell whether the cruise is preliminary for the purposes of displaying
        a warning.

        A cruise may either be completely marked preliminary or preliminary
        attributes may cause it to be considered preliminary as well.

        """
# TODO
        for attr in self.attrs_current.values():
            if attr.key.endswith(self.DATA_STATUS_ENDING):
                if 'preliminary' in attr.value:
                    return True
        return 'preliminary' in self.get('statuses', []) 

    @property
    def chief_scientists(self):
        try:
            return self.participants.with_role('Chief Scientist')
        except KeyError:
            return []

    @property
    def track(self):
        if self._track is not None:
            return to_shape(self._track)
        return None

    @track.setter
    def track(self, value):
        self._track = from_shape(value)

    @property
    def file_attrs(self):
        file_attrs = {}
        for attr in self.get_attrs_or(data_file_descriptions.keys()):
            file_attrs[attr.attr] = attr
        return file_attrs

    def _set_cache(self, attr, value):
        """Set the attribute value to cache."""
        if attr in data_file_descriptions.keys():
            try:
                self.files[attr].file = value
            except KeyError:
                self.files[attr] = _CruiseFile(attr, value)
            return
        if attr == 'participants':
            self.participants = set(value)
            return
        if attr.endswith(self.DATA_STATUS_ENDING):
            attr = attr[:-len(self.DATA_STATUS_ENDING)]
            try:
                self.files[attr].statuses = value
            except KeyError:
                self.files[attr] = _CruiseFile(attr, None, value)
            return
        return super(Cruise, self)._set_cache(attr, value)

    def _get_cache(self, attr):
        """Attempt to get the attribute value from cache."""
        try:
            if attr in data_file_descriptions.keys():
                return self.files[attr].file
            if attr.endswith(self.DATA_STATUS_ENDING):
                attr = attr[:-len(self.DATA_STATUS_ENDING)]
                return self.files[attr].statuses
        except KeyError:
            pass
        return super(Cruise, self)._get_cache(attr)

    @classmethod
    def filter_geo(cls, fn, cruises):
        """Filter a list of cruises using the spatial filter function."""
        return filter(lambda x: x.track and fn(asShape(x.track)), cruises)

    @classmethod
    def query_by_expocode(cls, expocode):
        return cls.query().filter(Cruise.expocode == expocode)

    @classmethod
    def get_by_expocode(cls, expocode):
        return cls.query_by_expocode(expocode).first()

    @classmethod
    def get_all_by_expocode(cls, expocode):
        return cls.query_by_expocode(expocode).all()

    @classmethod
    def get_by_id(cls, cruise_id):
        """Retrieve a cruise given an id. The id may be a number or uid."""
        cruise_obj = None
        if not cruise_id:
            return None

        try:
            cid = int(cruise_id)
            cruise_obj = Cruise.query().get(cid)
        except ValueError:
            pass

        # If the id does not refer to a Cruise, try searching based on ExpoCode
        if not cruise_obj:
            cruise_obj = Cruise.get_by_expocode(cruise_id)
        if not cruise_obj:
            # If not, try based on aliases.
            cruise_obj = Cruise.query().filter(
                Cruise.aliases.contains(cruise_id)).first()
        if not cruise_obj:
            raise ValueError('Not found')
        return cruise_obj

    @classmethod
    def updated(cls, limit):
        """Provide list of Changes that have been recently approved."""
        file_types = data_file_descriptions.keys()
        file_types.remove('map_thumb')
        file_types.remove('map_full')

        baseq = Change.query().\
            filter(Change.accepted == True).\
            filter(Change.attr.in_(file_types)).\
            order_by(Change.ts_j.desc())

        skip = 0
        step = limit * 4
        updated = []
        cruise_ids = set()

        while len(updated) < limit:
            attrs = baseq.offset(skip).limit(step).all()
            if not attrs:
                break
            for attr in attrs:
                cruise_id = attr.obj_id
                if cruise_id not in cruise_ids:
                    cruise_ids.add(cruise_id)
                    updated.append(attr)
                if len(updated) >= limit:
                    break
            skip += step
        return updated

    @classmethod
    def filter_pending_date_start(cls, query):
        return query.\
            filter(Cruise.ts_j == None).\
            filter(Cruise.accepted == False).\
            filter(Cruise.date_start != None).order_by(Cruise.date_start)

    @classmethod
    def pending_with_date_starts(cls):
        """Gives a list of all pending cruises that have start dates"""
        pending = cls.filter_pending_date_start(Cruise.query())
        return pending

    @classmethod
    def upcoming(cls, limit):
        now = timestamp_now()
        query = Cruise.pending_with_date_starts()

        i = limit
        hardlimit = query.count()
        upcoming = []

        while len(upcoming) < limit and i <= hardlimit:
            upcoming = query.\
                filter(Cruise.date_start >= func.now()).\
                order_by(Cruise.date_start).limit(i).all()
            i += limit
        return upcoming[:limit]

    @classmethod
    def pending_years(cls):
        """Gives a list of integer years that have pending cruises."""
        years = cls.filter_pending_date_start(
            DBSession.query(distinct(Cruise.date_start))).all()
        return [y[0].year for y in years]

    @classmethod
    def cruises_in_selection(
            cls, selection, time_range, roi_result_limit=50):
        """Return cruises in selected polygon and time range.

        Returns a tuple of the matching cruises and also whether or not there
        were more results than the limit.

        """
        polygon = list(selection.exterior.coords)
        query = Cruise.query().\
            filter(Cruise._track.intersects(str(selection))).\
            limit(roi_result_limit)
        cruises = query.all()

        limited = False
        if len(cruises) == roi_result_limit:
            limited = query.count() > roi_result_limit

        log.info(time_range)
        def date_filter(cruise):
            def d2y(d):
                try:
                    return d.date().year
                except AttributeError:
                    try:
                        return int(d)
                    except (TypeError, ValueError):
                        return time_range[0]
            return time_range[0] <= d2y(cruise.date_start) and \
                   d2y(cruise.date_end) <= time_range[1]
        return (filter(date_filter, cruises), limited)

    def to_dict(self):
        """Returns a dict representation of the Cruise."""
        rep = super(Cruise, self).to_dict()
        d = {
            'expocode': self.expocode,
            'accepted': self.accepted,
            'link': self.get('link', None),
            'frequency': self.get('frequency', None),
            'date_start': self.date_start,
            'date_end': self.date_end,
            'aliases': list(self.aliases),
            'ports': self.get('ports', []),
            'collections': [c.to_dict() for c in self.collections],
            'institutions': [i.to_dict() for i in self.institutions],
            'participants': self.get('participants', []),
        }
        if self.ship:
            d['ship'] = self.ship.to_dict()
        if self.country:
            d['country'] = self.country.to_dict()
        rep.update(d)
        return rep

    def __repr__(self):
        return u'Cruise({0}, {1})'.format(
            _repr_state(self), self.expocode)

def __allow_attr_cruise():
    cruise_allow_attrs = [
        ('expocode', Unicode, 'ExpoCode'),
        ('link', Unicode, 'Expedition Link'),
        ('frequency', Unicode),

        ('date_start', [DateTime, Unicode], 'Start Date'),
        ('date_end', [DateTime, Unicode], 'End Date'),

        ('statuses', TextList, 'Cruise statuses'),
        ('aliases', TextList),
        ('ports', TextList),

        ('ship', [(ID, 'Ship'), Unicode]),
        ('country', [(ID, 'Country'), Unicode]),

        ('collections', [(IDList, 'Collection'), Unicode]),
        ('institutions', [(IDList, 'Institution'), Unicode]),

        ('track', LineString),

        ('participants', [(IDList, 'Participant'), TextList]),

        ('parameter_informations', (IDList, 'ParameterInformation')), 

        ('data_suggestion', File, 'Data suggestion'),

        ('data_dir', Unicode, 'Import data directory'),
        ('archive', File, 'Import archive'),
        ]
    for key, name in DataFileTypes.human_names.items():
        status_key = '{0}{1}'.format(key, Cruise.DATA_STATUS_ENDING)
        cruise_allow_attrs.extend([
            (key, File, name),
            (status_key, TextList),
            ])

    Cruise.allow_attrs(cruise_allow_attrs)
once_at_end.register(__allow_attr_cruise)


@event.listens_for(Note, 'after_insert')
@event.listens_for(Note, 'after_update')
def _saved_note(mapper, connection, target):
    triggers.saved_note(target)


@event.listens_for(Note, 'after_delete')
def _deleted_note(mapper, connection, target):
    triggers.deleted_note(target)


@event.listens_for(Obj, 'after_insert')
@event.listens_for(Obj, 'after_update')
def _saved_obj(mapper, connection, target):
    if isinstance(target, Obj):
        return
    triggers.saved_obj(target)


@event.listens_for(Obj, 'after_delete')
def _deleted_obj(mapper, connection, target):
    if isinstance(target, Obj):
        return
    triggers.deleted_obj(target)


once_at_end.run()
