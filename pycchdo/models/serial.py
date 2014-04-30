#!/usr/bin/env python

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
    event,
    Table, Column, ForeignKey, 
    Integer, Unicode, String, Boolean, DateTime,
    )
from sqlalchemy.exc import DataError
from sqlalchemy.sql import (
    func, and_, not_, or_,
    )
from sqlalchemy.sql.expression import case, literal
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, scoped_session, sessionmaker, backref
from sqlalchemy.orm.query import Query
from sqlalchemy.orm.collections import (
    collection, InstrumentedList, attribute_mapped_collection,
    )
from sqlalchemy.schema import CreateSchema

from zope.sqlalchemy import ZopeTransactionExtension

import geojson

from geoalchemy2.types import Geography 

from sqlalchemy_imageattach.context import current_store, store_context

from libcchdo.recipes.orderedset import OrderedSet

from pycchdo.models import triggers
from pycchdo.models.attrmgr import AllowableMgr
from pycchdo.models.types import *
from pycchdo.models.filestorage import AdaptedFile, FSStore
from pycchdo.models.file_types import (
    DataFileTypes,
    data_file_descriptions,
    )
from pycchdo.util import drop_everything, is_valid_ip, timestamp_now
from pycchdo.models import log
#from pycchdo.log import DEBUG
#log.setLevel(DEBUG)

Base = declarative_base()
Meta = Base.metadata
Meta.schema = 'pycchdo'

Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)


def reset_database(engine):
    """Clears the database and recreates schema."""
    drop_everything(engine)
    engine.execute(CreateSchema(Meta.schema))
    Meta.create_all(engine)


def reset_fs(fsstore):
    fss_root = fsstore.path
    for root, dirs, files in os.walk(fss_root):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            rmtree(os.path.join(root, d))


# TODO Store a UOW object that links to multiple changes?


def _repr_state(obj):
    if obj.accepted:
        return 'accept'
    if obj.ts_j:
        return 'reject'
    return 'pendin'


class MixinCreation(object):
    """Mixin regarding the creation time and person."""
    @hybrid_property
    def ctime(cls):
        return cls.ts_c


class DBQueryable(object):
    """Mixin to obtain query on this class for global database session."""
    @classmethod
    def query(cls, *args):
        """Return a query for this class on the global database session."""
        if args:
            return DBSession.query(*args)
        return DBSession.query(cls)


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
        backref=backref('_notes', uselist=True, lazy='dynamic'))

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

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'Note({0}, {1})'.format(self.id, self.subject)

    def __repr__(self):
        return u'Note({0}, {1}, {2})'.format(self.id, self.subject, self.discussion)


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
    _value = Column('value', String, default=None)
    _value_accepted = Column('value_accepted', String, default=None)

    accepted = Column(Boolean, default=False)

    deleted = Column(Boolean, default=False)

    p_id_c = Column(Integer, ForeignKey('people.id'))
    p_c = relationship('Person', foreign_keys=[p_id_c])
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

    def __init__(self, obj, person, attr, value):
        self.obj = obj
        self.attr = attr
        log.debug('creating change {0}.{1}={2!r}'.format(obj, attr, value))
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
        suggested value deseriailized.

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

    @value.setter
    def value_accepted(self, val):
        """Serialize the value so it can be stored in the database.

        """
        self._value_accepted = self.obj.serialize(self.attr, val)

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

    def accept(self, person, replacement=None):
        """Accept a Change.

        This means bookkeeping as well as updating the Obj's (if any) attribute
        cached value. If a replacement value is offered, it will be serialized
        and stored as well.

        """
        self.p_j = person
        self.ts_j = func.now()
        self.accepted = True

        if replacement is not None:
            self.value_accepted = replacement
        value = self.value

        log.debug(u'accepting {0!r}:{1!r}'.format(self, value))

        if self.is_obj:
            self.obj.accepted = True
            self.obj.ts_j = func.now()
        else:
            try:
                self.obj._set_cache(self.attr, value)
            except (DataError, TypeError):
                # If the value does not store well in the Obj cache, we'll have
                # to leave it in string form. Communicate to the Obj that the
                # cache is not valid.
                delattr(self.obj, self.attr)

    def acknowledge(self, person):
        self.p_ack = person
        self.ts_ack = func.now()

    def reject(self, person):
        self.p_j = person
        self.ts_j = func.now()
        self.accepted = False

        if self.is_obj:
            self.obj.accepted = False

    @classmethod
    def get_all_by_ids(cls, *ids):
        """Return the instances in the order of the ids."""
        return query_in_order_ids(DBSession.query(cls), cls.id, ids).all()

    @classmethod
    def get_id(cls, id):
        log.warn(u'get_id is deprecated')
        return cls.get_all_by_ids(id)

    @classmethod
    def by_ids(cls, ids):
        log.warn(u'by_ids is deprecated')
        return cls.get_all_by_ids(*ids)

    @classmethod
    def only_if_accepted_is(cls, accepted=True):
        """Return a query for this class only when accepted or not."""
        return DBSession.query(cls).filter(cls.accepted == accepted)

    @property
    def notes(self):
        return self._notes.all()

    @property
    def notes_public(self):
        return self._notes.filter(not_(Note.discussion)).all()

    @property
    def notes_discussion(self):
        return self._notes.filter(Note.discussion).all()

    def __unicode__(self):
        return u'{0}, {1}, {2}'.format(
            _repr_state(self), self.obj, self.attr, self.value)

    def __repr__(self):
        return u'<Change({0}, {1}, {2})>'.format(
            _repr_state(self), self.obj, self.attr, self.value)


class RequestFor(Base):
    """Store HTTP requests for a Change."""
    __tablename__ = 'requests_for'

    id = Column(Integer, primary_key=True)

    change_id = Column(ForeignKey('changes.id'))

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


class AllowableSerialMgr(AllowableMgr):
    """Manages which attributes are tracked as well as serialization."""

    __serializers = {}
    __deserializers = {}
        
    @classmethod
    def allow_attr(cls, key, attr_type, name=None, batch=False):
        super(AllowableSerialMgr, cls).allow_attr(key, attr_type, name, batch)

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
            deserializer = attrdef[attr]
            log.warn(u'Deserializer for {0}.{1} already registered: {2}'.format(
                cls, attr, deserializer))
        except KeyError:
            attrdef['deserializer'] = deserializer

    def serialize(self, attr, value):
        """Serialize the value from a python object to a string."""
        attrdef = self._allowed_attrs_dict()[attr]
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

    @property
    def change(self):
        """Return the Change that created the Obj.

        """
        return self._changes.filter(Change.attr.is_(None)).filter(
            Change._value.is_(None)).first()

    def changes_query(self, state=None, replaced=False):
        """Return a query for the Obj's attribute Changes.

        state - enum: unjudged, unacknowleged, pending, accepted
        replaced - if True, requires that the Changes have an accepted value

        """
        query = self._changes.filter(and_(
            Change.attr != None, Change.value != None))

        if state == 'unjudged':
            query = query.filter(and_(Change.ts_j == None, Change.p_j == None))
        elif state == 'unacknowledged':
            query = query.filter(and_(Change.ts_ack == None, Change.p_ack == None))
        elif state == 'pending':
            query = query.filter(and_(Change.ts_ack != None, Change.p_ack != None))
        elif state == 'accepted':
            query = query.filter(Change.accepted)

        if replaced:
            query = query.filter(Change._value_accepted != None)

        return query

    def changes(self, state=None, replaced=False):
        """Return the Obj's Changes excluding the one that created it."""
        return self.changes_query(state, replaced).all()

    def changes_filter_data(self, changes):
        """Filter Changes to those pertaining to attributes that store Files.

        """
        return filter(
            lambda change: change.obj.attr_type(change.attr) == File, changes)

    def changes_data(self, state=None, replaced=False):
        """Return changes for the Obj that store files."""
        changes = self.changes_query(state, replaced).all()
        return self.changes_filter_data(changes)

    def get_attr(self, attr):
        """Return the most recent accepted Change for key.

        Raises: KeyError if none

        """
        change = self.changes_query('accepted').filter(Change.attr == attr).\
            order_by(Change.ts_j).first()
        if change is None:
            raise KeyError(attr)
        return change

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

    def get_attr_change(self, attr):
        """Return the last Change for this Obj's attr."""
        return self._changes.filter(Change.attr == attr).first()

    def _set_cache(self, attr, value):
        """Set the attribute value to cache."""
        try:
            setattr(self, attr, value)
        except AttributeError:
            # If the Obj does not declare this attribute, it doesn't really care
            # if the value is cached.
            pass

    def _get_cache(self, attr):
        """Attempt to get the attribute value from cache."""
        try:
            return getattr(self, attr)
        except AttributeError:
            return None

    def get(self, attr, default=None, force_original=False, force_change=False):
        """Get the attribute's value.

        default - the default value if unable to get value (TODO)
        force_original - force the getter to return the original value of the
            Change. This implies force_change
        force_change - force the getter to return the last applicable Change
            instead of the cached version.

        """
        if force_original or force_change:
            change = self.get_attr_change(attr)
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

    def delete(self):
        """Delete this Obj from the database and remove its Changes."""
        # This option purges the Changes as well.
        # Is this desirable because there would no longer be a log of that obj's
        # creation?
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

    def __repr__(self):
        return u'{cls}()'.format(cls=type(self))


Obj.allow_attr('import_id', String, 'Import ID')


class ExtrasJSONEncoder(JSONEncoder):
   def default(self, obj):
       if isinstance(obj, Decimal):
           return str(obj)
       # Let the base class default method raise the TypeError
       return json.JSONEncoder.default(self, obj)


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
            return value.strftime(cls.format_string)
        except AttributeError:
            return super(SerializerDateTime, cls).serialize(value)

    @classmethod
    def deserialize(cls, value):
        try:
            return datetime.strptime(value, cls.format_string)
        except ValueError:
            return None


class SerializerTrack(Serializer):
    @classmethod
    def serialize(cls, value):
        return geojson.dumps(value)

    @classmethod
    def deserialize(cls, value):
        return geojson.loads(value)


def query_in_order_ids(query, field, ids):
    """Append to a query to filter by ids in order."""
    order = case([(field == value, literal(index)) for index, value in enumerate(ids)])
    return query.filter(field.in_(ids)).order_by(order)


class SerializerObj(Serializer):
    @classmethod
    def serialize(cls, value):
        return dumps({'obj_type': str(cls), 'id': value.id})

    @classmethod
    def Deserializer(cls, obj):
        return lambda value: cls.deserialize(obj, value)

    @classmethod
    def deserialize(cls, obj, value):
        oid = loads(value)['id']
        return obj.query().get(oid)


class SerializerFSFile(SerializerObj):
    @classmethod
    def serialize(cls, value):
        return dumps({'obj_type': str(cls), 'id': value.id})

    @classmethod
    def Deserializer(cls, obj):
        return lambda value: cls.deserialize(obj, value)

    @classmethod
    def deserialize(cls, obj, value):
        oid = loads(value)['id']
        return obj.query().get(oid)


class SerializerObjs(SerializerObj):
    @classmethod
    def serialize(cls, value):
        return dumps({'obj_type': str(cls), 'ids': [obj.id for obj in value]})

    @classmethod
    def deserialize(cls, obj, value):
        ids = loads(value)['ids']
        # Fast track empty lists, avoid SQL generation error
        if not ids:
            return []
        objs = query_in_order_ids(DBSession.query(obj), obj.id, ids).all()
        return objs


class Participant(Base, Creatable):
    """A participant of a Cruise. 

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
    
    def __eq__(self, other):
        if (    hash(self) == hash(other) and
                self.institution == other.institution):
            return True
        return False

    def __hash__(self):
        return hash(u'{0}_{1}_{2}'.format(self.id, self.role, self.person))

    def __repr__(self):
        return u'Participant({0}, {1}, {2})'.format(
            self.role, self.person, self.institution)
        

class Participants(InstrumentedList):
    """The participants of a Cruise.

    This object acts like a dictionary keyed upon "roles".

    All mutators will suggest a new value for 'participants' and return the
    suggestion.

    This collection will also provide Person-Institution paris when queried with
    a role.
    
    """
    def __init__(self, *args, **kwargs):
        """Store Participants in order."""
        if args:
            part = args[0]
            if type(part) is Participants:
                data = part
            else:
                data = args
        else:
            data = []
        super(Participants, self).__init__(data)

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

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'Participants({0!r})'.format(self)


class FSFile(Base, DBQueryable, AdaptedFile):
    """A file record that points to the filesystem file.

    # FIXME
    FSFile is stored as an Obj because it is difficult to find a Change based on
    FSFile import id if the only link is via a string id.
    Actually... I don't understand. If attr_by_import_id is only used for import
    reimplement to not have FSfile inherit from Obj.

    """
    __tablename__ = 'fsfiles'

    id = Column(Integer, primary_key=True)

    name = Column(Unicode)

    change_id = Column(ForeignKey('changes.id'))
    change = relationship(Change,
        backref=backref('file', single_parent=True,
                        cascade='all, delete-orphan'))

    # Stores information used by pycchdo.importer.cchdo to correlate ArgoFiles
    # with Documents and QueueFiles with QueueFiles.
    import_id = Column(Unicode)
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

    @classmethod
    def attr_by_import_id(cls, import_id):
        """Return attr Change matching FSFile import_id.

        """
        return Change.query().join(FSFile).\
            filter(FSFile.import_id == import_id).first()

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

    # TODO make merge work
    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        people = self.people
        for person in people:
            if person.country != self.id:
                person.set_accept('country', self.id, signer)

        for mergee in mergees:
            mergee.delete()

    def to_nice_dict(self):
        """Returns a dict representation of the Country."""
        rep = super(Country, self).to_nice_dict()
        rep.update({
            'name': self.name,
            'iso_3166-1_alpha-2': self.iso_code(),
            'iso_3166-1_alpha-3': self.iso_code(3),
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

# TODO make merge work
    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        participants = Participant.query().\
            filter(Participant.institution_id.in_(mergee_ids)).all()
        for p in participants:
            p.institution_id = self.id

        pis = ParameterInformation.query().\
            filter(ParameterInformation.inst_id.in_(mergee_ids)).all()
        for pi in pis:
            pi.inst_id = self.id

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        for mergee in mergees:
            mergee.delete()

    def to_nice_dict(self):
        """Returns a dict representation of the Institution."""
        rep = super(Institution, self).to_nice_dict()
        d = {
            'name': self.name,
        }
        if self.country:
            d['country'] = self.country.to_nice_dict()
        rep.update(d)
        return rep

    def __repr__(self):
        return u'Institution({0!r})'.format(self.name)


Institution.allow_attrs([
    ('name', Unicode),
    ('phone', Unicode),
    ('address', Unicode),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])
Institution.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))


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

# TODO make merge work
    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        for mergee in mergees:
            mergee.delete()

    def to_nice_dict(self):
        """Returns a dict representation of the Ship."""
        rep = super(Ship, self).to_nice_dict()
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


Ship.allow_attrs([
    ('name', Unicode),
    ('nodc_platform_code', String, 'NODC Platform Code'),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])
Ship.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))


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

    # TODO make merge work
    def merge(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]
        cs = Change.query().\
            filter(Change.creation_person_id.in_(mergee_ids)).all()
        for c in cs:
            c.creation_person_id = self.id
        cs = Change.query().\
            filter(Change.pending_person_id.in_(mergee_ids)).all()
        for c in cs:
            c.pending_person_id = self.id
        cs = Change.query().\
            filter(Change.judgment_person_id.in_(mergee_ids)).all()
        for c in cs:
            c.judgment_person_id = self.id

        participant_lists = set()
        participants = Participant.query().\
            filter(Participant.person_id.in_(mergee_ids)).all()
        for p in participants:
            p.person_id = self.id
            participant_lists.add(p.attrvalue)

        for av in participant_lists:
            # Make a copy. Doing in-place operations on a collection makes for
            # funny business
            l = list(av.values)
            original = None
            i = 0
            while i < len(l) - 1:
                p = l[i]
                # designate the first participant with matching person as
                # original. This loop will continue until the end because it is
                # possible a single person to have multiple roles.
                if not original and p.person_id == self.id:
                    original = p
                else:
                    i += 1
                    continue

                # start from the end and remove participants that match the
                # person and role while filling in the institution if unknown
                j = len(l) - 1
                while j > i:
                    q = l[j]
                    if q.person_id != p.person_id or q.role != p.role:
                        j -= 1
                        continue
                    l.pop(j)
                    if not original.institution_id:
                        original.institution_id = q.institution_id
                    j -= 1

                # all the participants that matched the original are now
                # removed. clear things up to prepare for the next match
                original = None
                i += 1
            av.values = Participants(l)

        notes = Note.query().\
            filter(Note.creation_person_id.in_(mergee_ids)).all()
        for note in notes:
            note.creation_person_id = self.id

        pis = ParameterInformation.query().\
            filter(ParameterInformation.pi_id.in_(mergee_ids)).all()
        for pi in pis:
            pi.pi_id = self.id

        pps = _PersonPermissions.query().\
            filter(_PersonPermissions.person_id.in_(mergee_ids)).all()
        for pp in pps:
            pp.person_id = self.id

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        for mergee in mergees:
            mergee.delete()

        self._recache()

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

    def to_nice_dict(self):
        """Returns a dict representation of the Person.

        """
        rep = super(Person, self).to_nice_dict()
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


Person.allow_attrs([
    ('title', Unicode),
    ('job_title', Unicode),
    ('phone', Unicode),
    ('fax', Unicode),
    ('address', Unicode),
    
    ('institution', ID),
    ('country', ID),
    
    ('programs', IDList),

    # Legacy password parts
    ('password_hash', String),
    ('password_salt', String),
    ])
Person.register_serializer_pair(
    'institution', SerializerObj.serialize, SerializerObj.Deserializer(Institution))
Person.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))


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
            cruise.set(signer, 'collections', colls)

        for mergee in mergees:
            mergee.delete()

    def to_nice_dict(self):
        """Returns a dict representation of the Collection."""
        rep = super(Collection, self).to_nice_dict()
        rep.update({
            'names': self.names,
            'type': self.type,
            'basins': self.basins,
        })
        return rep

    def __repr__(self):
        return u'Collection({0}, {1}, {2}, {3})'.format(
            _repr_state(self), self.names, self.type, self.basins)


Collection.allow_attrs([
    ('type', Unicode),
    ('basins', TextList),
    ('names', TextList),
    ('date_start', [DateTime, Unicode], 'Start Date'), 
    ('date_end', [DateTime, Unicode], 'End Date'), 

    ('url', Unicode), 

    ('institution', ID), 
    ('country', ID), 
    ])
Collection.register_serializer_pair(
    'names', Serializer)
Collection.register_serializer_pair(
    'basins', Serializer)


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


Unit.allow_attrs([
    ('name', Unicode),
    ('mnemonic', Unicode),
    ])


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

    _aliases = relationship('_ParameterAlias', uselist=True)
    aliases = association_proxy('_aliases', 'alias')

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

    def __unicode__(self):
        return u'Parameter({0})'.format(self.name)

    def __repr__(self):
        return unicode(self)


Parameter.allow_attrs([
    ('name', Unicode, 'WOCE mnemonic'),
    ('aliases', TextList),
    ('full_name', Unicode),
    ('name_netcdf', Unicode, 'WOCE NetCDF name'),
    ('description', Unicode),
    ('format', Unicode, 'C format string'),
    ('bounds', DecimalList),
    ('units', ID),
    ('in_groups_but_did_not_exist', Boolean), 
    ])
Parameter.register_serializer_pair(
    'aliases', Serializer)
Parameter.register_serializer_pair(
    'bounds', Serializer)
Parameter.register_serializer_pair(
    'units', SerializerObj.serialize, SerializerObj.Deserializer(Unit))
Parameter.register_serializer_pair(
    'in_groups_but_did_not_exist', Serializer)


class _ParameterGroupOrder(Base):
    __tablename__ = 'parametergroup_orders'
    id = Column(Integer, primary_key=True)
    pg_id = Column(Unicode, ForeignKey('parameter_groups.name'))
    parameter_id = Column(Integer, ForeignKey('parameters.id'))
    parameter = relationship(Parameter, backref='parameter_groups')

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
    _order = relationship(_ParameterGroupOrder, uselist=True)
    order = association_proxy('_order', 'parameter')

    __mapper_args__ = {
        'polymorphic_identity': 'parameter_group',
    }

    def __unicode__(self):
        return u'ParameterGroup({0}, {1})'.format(self.name, self.order)

    def __repr__(self):
        return unicode(self)

ParameterGroup.allow_attrs([
    ('name', Unicode),
    ('order', IDList),
    ])
ParameterGroup.register_serializer_pair(
    'order', SerializerObjs.serialize, SerializerObjs.Deserializer(Parameter))


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
        self.parameter_id = parameter.id
        self.status = status
        if pi:
            self.pi_id = pi.id
        if inst:
            self.inst_id = inst.id
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
    Also can return a list of cruises based on the submission's cruise identifier.

    """

    @property
    def value(self):
        return self.file

    @value.setter
    def value(self, o):
        self.file = o

    def cruises_from_identifier(self):
        try:
            return Cruise.query().filter(
                Cruise.expocode == self.identifier).all()
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

    link_cruise_id = Column(Integer, ForeignKey('cruises.id'))
    link_cruise = relationship(
        'Cruise', primaryjoin='ArgoFile.link_cruise_id == Cruise.id')
    link_attr_key = Column(Unicode)

    request_for_id = Column(Integer, ForeignKey('requests_for.id'))
    requests_for = relationship(
        'RequestFor', secondary=argo_file_requests_for, single_parent=True,
        uselist=True, cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'argo_file',
    }

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
    file = relationship(
        'FSFile', foreign_keys=[file_id], single_parent=True,
        cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'old_submission',
    }


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
    attached -- an _Attr id.
        When this is set, the submission has been looked at by a human and
        the corresponding _Attr represents verified information representing
        this submission.

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

    attached_id = Column(Integer, ForeignKey('changes.id'))
    attached = relationship(Change,
        backref=backref('submission', uselist=False), lazy='joined')

    file_id = Column(Integer, ForeignKey('fsfiles.id'))
    file = relationship(
        'FSFile', foreign_keys=[file_id], single_parent=True,
        cascade='all, delete-orphan')

    request_for_id = Column(Integer, ForeignKey('requests_for.id'))
    request_for = relationship(
        'RequestFor', uselist=False, single_parent=True,
        cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'submission',
    }

    # TODO is this used?
    @property
    def identifier(self):
        return self.expocode

    def attach(self, attr, signer):
        """Attaches the submission to a new Change and accepts the submission.

        """
        self.attached = attr
        self.accept(signer)

    @classmethod
    def unacknowledged(cls):
        """Return Submissions that have not yet been reviewed."""
        # TODO
        return []


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

    NOTE: A difference exists between imported legacy submissions and created
    submissions. Imported submissions that have already been queued have their
    _Attr attachment set to True instead of being linked to a direct suggestion.
    This is because there is no easy inferred link from legacy submission to
    legacy queue file.

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

    _aliases = relationship('_CruiseAlias', lazy='joined', uselist=True)
    aliases = association_proxy('_aliases', 'alias')

    _statuses = relationship('_CruiseStatus', lazy='joined', uselist=True)
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

    track = Column(Geography(geometry_type='LINESTRING', srid=4326, dimension=2))

    participants = relationship(
        Participant, uselist=True, collection_class=Participants,
        backref='cruise',
        lazy='joined', cascade='all, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'cruise',
    }

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
            if attr.key.endswith('_status'):
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
        if attr.endswith('_status'):
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
            ending = '_status'
            if attr.endswith(ending):
                return self.files[attr[:-len(ending)]].statuses
        except KeyError:
            pass
        return super(Cruise, self)._get_cache(attr)

    @classmethod
    def get_by_expocode(cls, expocode):
        return cls.query().filter(Cruise.expocode == expocode).first()

    @classmethod
    def updated(cls, limit):
        """Provide list of _Attrs that have been recently approved."""
        file_types = data_file_descriptions.keys()
        file_types.remove('map_thumb')
        file_types.remove('map_full')

        skip = 0
        step = limit * 4
        updated = []
        cruise_ids = set()

        while len(updated) < limit:
            attrs = Change.query().\
                filter(Change.accepted==True).\
                filter(Change.attr.in_(file_types)).\
                order_by(Change.ts_j.desc()).\
                offset(skip).limit(step).all()
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
    def pending_with_date_starts(cls, offset=None, limit=None):
        """Gives a list of all pending cruises that have start dates"""
        pending = Cruise.query().\
            filter(Cruise.accepted==False).\
            filter(Cruise.id.in_(
                Change.query(Change.obj_id).\
                    filter(Change.attr == 'date_start').\
                    filter(Change.accepted)
                )
            )
        if offset:
            pending = pending.offset(offset)
        if limit:
            pending = pending.limit(limit)
        return pending

    @classmethod
    def upcoming(cls, limit):
        now = timestamp_now()
        query = Cruise.pending_with_date_starts()

        i = limit
        hardlimit = query.count()
        upcoming = []

        while len(upcoming) < limit and i <= hardlimit:
            upcoming = query.limit(i).all()
            try:
                upcoming = sorted(upcoming, key=lambda c: c.date_start)
            except TypeError:
                upcoming = []
            upcoming = filter(
                lambda x: x.date_start and now <= x.date_start, upcoming)
            i += limit
        return upcoming[:limit]


    @classmethod
    def pending_years(cls):
        """Gives a list of integer years that have pending cruises."""
        pending_with_date_starts = Cruise.pending_with_date_starts().all()
        years = set()
        for cruise in pending_with_date_starts:
            years.add(cruise.date_start.year)
        return list(years)

    @classmethod
    def cruises_in_selection(
            cls, selection, time_range, roi_result_limit=50):
        """Return cruises in selected polygon and time range.

        Returns a tuple of the matching cruises and also whether or not there
        were more results than the limit.

        """
        polygon = list(selection.exterior.coords)
        query = _Attr.query().filter(_Attr.key == 'track').\
            join(_AttrValueLineString).\
            filter(_AttrValueLineString.value_.intersects(str(selection))).\
            limit(roi_result_limit)
        attrs = query.all()

        limited = False
        if len(attrs) == roi_result_limit:
            limited = query.count() > roi_result_limit

        objs = set(attr.obj for attr in attrs)
        cruises = [obj for obj in objs if isinstance(obj, Cruise)]

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

    def __repr__(self):
        return u'Cruise({0}, {1})'.format(
            _repr_state(self), self.expocode)

# TODO move this into the class definition so it only gets called once even if
# the module is reimported
__cruise_allow_attrs = [
    ('expocode', Unicode, 'ExpoCode'),
    ('link', Unicode, 'Expedition Link'),
    ('frequency', Unicode),

    ('date_start', [DateTime, Unicode], 'Start Date'),
    ('date_end', [DateTime, Unicode], 'End Date'),

    ('statuses', TextList, 'Cruise statuses'),
    ('aliases', TextList),
    ('ports', TextList),

    ('ship', [ID, Unicode]),
    ('country', [ID, Unicode]),

    ('collections', [IDList, Unicode]),
    ('institutions', [IDList, Unicode]),

    ('track', LineString),

    ('participants', [ParticipantsType, TextList]),

    ('parameter_informations', ParameterInformations), 

    ('data_suggestion', File, 'Data suggestion'),

    ('data_dir', Unicode, 'Import data directory'),
    ('archive', File, 'Import archive'),
    ]
to_register = []
for key, name in DataFileTypes.human_names.items():
    to_register.append((
        key, SerializerObj.serialize, SerializerObj.Deserializer(FSFile)))
    status_key = '{0}_status'.format(key)
    to_register.append((status_key, Serializer))

    __cruise_allow_attrs.extend([
        (key, File, name),
        (status_key, TextList),
        ])

Cruise.allow_attrs(__cruise_allow_attrs)
for item in to_register:
    Cruise.register_serializer_pair(*item)
Cruise.register_serializer_pair(
    'date_start', SerializerDateTime)
Cruise.register_serializer_pair(
    'date_end', SerializerDateTime)
Cruise.register_serializer_pair(
    'statuses', Serializer)
Cruise.register_serializer_pair(
    'aliases', Serializer)
Cruise.register_serializer_pair(
    'ports', Serializer)
Cruise.register_serializer_pair(
    'ship', SerializerObj.serialize, SerializerObj.Deserializer(Ship))
Cruise.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))
Cruise.register_serializer_pair(
    'collections', SerializerObjs.serialize, SerializerObjs.Deserializer(Collection))
Cruise.register_serializer_pair(
    'institutions', SerializerObjs.serialize, SerializerObjs.Deserializer(Institution))
Cruise.register_serializer_pair(
    'track', SerializerTrack)
Cruise.register_serializer_pair(
    'participants', SerializerObjs.serialize, SerializerObjs.Deserializer(Participant))
Cruise.register_serializer_pair(
    'parameter_informations', SerializerObjs.serialize, SerializerObjs.Deserializer(ParameterInformation))
Cruise.register_serializer_pair(
    'data_suggestion', SerializerObj.serialize, SerializerObj.Deserializer(FSFile))
Cruise.register_serializer_pair(
    'data_dir', Serializer)
Cruise.register_serializer_pair(
    'archive', SerializerObj.serialize, SerializerObj.Deserializer(FSFile))


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
    triggers.saved_obj(target)


@event.listens_for(Obj, 'after_delete')
def _deleted_obj(mapper, connection, target):
    triggers.deleted_obj(target)
