#!/usr/bin/env python

import sys
from contextlib import closing
from cgi import FieldStorage
from StringIO import StringIO
from json import loads, dumps
from datetime import datetime

from sqlalchemy import (
    create_engine, Table, Column, Integer, Unicode, String, Boolean, ForeignKey,
    DateTime,
    )
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
    collection, InstrumentedList,
    )

import geojson

from geoalchemy import (
    GeometryColumn, LineString, GeometryDDL, 
    )
from geoalchemy.postgis import PGComparator

from sqlalchemy_imageattach.context import current_store, store_context

from pycchdo.models.attrmgr import AllowableMgr
from pycchdo.models.types import *
from pycchdo.models.filestorage import AdaptedFile, FSStore
from pycchdo.models.file_types import (
    data_file_human_names, data_file_descriptions,
    )
from pycchdo.util import (
    timestamp_now
    )

from pycchdo.log import ColoredLogger, INFO, DEBUG
log = ColoredLogger(__name__)
log.setLevel(DEBUG)

Base = declarative_base()

engine = create_engine('sqlite:///zzerial.db')

Session = sessionmaker(bind=engine)
DBSession = scoped_session(Session)


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


class Note(Base, MixinCreation):
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
    ts_c = Column(DateTime, default=timestamp_now)

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
    perm_type = Column(Enum('read', 'write'), default='read', primary_key=True)
    permission = Column('perm', Unicode, primary_key=True)

    def __init__(self, perm_type, permission):
        self.perm_type = perm_type
        self.permission = permission


class Change(Base, MixinCreation):
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

    obj_id = Column(Integer, ForeignKey('objs.id'))
    obj = relationship('Obj', backref=backref('_changes', lazy='dynamic'))
    attr = Column(String, default=None)
    _value = Column('value', String, default=None)
    _value_accepted = Column('value_accepted', String, default=None)

    accepted = Column(Boolean, default=False)

    p_id_c = Column(Integer, ForeignKey('people.id'))
    p_c = relationship('Person', foreign_keys=[p_id_c])
    ts_c = Column(DateTime, default=timestamp_now)

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
        return bool(self.ts_j)

    def is_acknowledged(self):
        return bool(self.ts_ack)

    def is_accepted(self):
        return self.is_judged() and self.accepted

    def is_rejected(self):
        return self.is_judged() and not self.accepted

    def accept(self, sesh, person, replacement=None):
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
                setattr(self.obj, self.attr, value)
            except AssertionError:
                lll = getattr(self.obj, self.attr)
                log.debug(repr(lll))
                for val in value:
                    lll.append(val)
            except AttributeError:
                # If the Obj does not declare this attribute, it doesn't really
                # care if the value is cached.
                pass

    def acknowledge(self, sesh, person):
        self.p_ack = person
        self.ts_ack = func.now()

    def reject(self, sesh, person):
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

    serializers = {}
    deserializers = {}

    @classmethod
    def register_serializer_pair(cls, attr, serializer, deserializer):
        """Register serializer/deserializer for the attribute key."""
        try:
            serializer = cls.serializers[attr]
            log.warn(u'Serializer   for {0}.{1} already registered: {2}'.format(
                cls, attr, serializer))
        except KeyError:
            cls.serializers[attr] = serializer
        try:
            deserializer = cls.deserializers[attr]
            log.warn(u'Deserializer for {0}.{1} already registered: {2}'.format(
                cls, attr, deserializer))
        except KeyError:
            cls.deserializers[attr] = deserializer

    def serialize(self, attr, value):
        """Serialize the value from a python object to a string."""
        try:
            return self.serializers[attr](value)
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
            deserializer = self.deserializers[attr]
            return deserializer(value)
        except KeyError:
            return value
        except Exception, err:
            log.error(u'Unable to deserialize: {0}'.format(err))
            raise


class Creatable(object):
    """Creatable objects can be created and added to the database at once."""
    @classmethod
    def create(cls, sesh, *args, **kwargs):
        """Create and add an object to the database."""
        obj = cls(*args, **kwargs)
        sesh.add(obj)
        sesh.flush()
        return obj


class Obj(Base, Creatable, AllowableSerialMgr):
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

    def sugg(self, sesh, person, attr, value):
        """Suggest that an attribute's value should be."""
        change = Change(self, person, attr, value)
        sesh.add(change)
        return change

    def set(self, sesh, person, attr, value):
        """Set the attribute's value."""
        change = self.sugg(sesh, person, attr, value)
        change.accept(sesh, person)
        return change

    def _get_attr_change(self, sesh, attr):
        """Return the last Change for this Obj's attr."""
        return self._changes.filter(Change.attr == attr).first()

    def get(self, sesh, attr, default=None, force_original=False, force_change=False):
        """Get the attribute's value.

        default - the default value if unable to get value (TODO)
        force_original - force the getter to return the original value of the
            Change. This implies force_change
        force_change - force the getter to return the last applicable Change
            instead of the cached version.

        """
        if force_original or force_change:
            change = self._get_attr_change(sesh, attr)
            if force_original:
                return change.value_original
            else:
                return change.value
        try:
            return getattr(self, attr)
        except AttributeError:
            return self.get(
                sesh, attr, default, force_original, force_change=True)

    @classmethod
    def propose(cls, sesh, person):
        """Propose a Change to add a new instance of this class."""
        change = Change(cls(), person, None, None)
        sesh.add(change)
        sesh.flush()
        return change

    @classmethod
    def create(cls, sesh, person):
        """Propose and accept a Change to add a new instance of this class."""
        change = cls.propose(sesh, person)
        change.accept(sesh, person)
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


class Serializer(object):
    @classmethod
    def serialize(cls, value):
        return dumps(value)

    @classmethod
    def deserialize(cls, value):
        return loads(value)


class SerializerDateTime(Serializer):
    # FIXME +%z preserve the timezone, if any. Is this necessary?
    format_string = '%Y-%m-%dT%H:%M:%S.%f'
    @classmethod
    def serialize(cls, value):
        return value.strftime(cls.format_string)

    @classmethod
    def deserialize(cls, value):
        return datetime.strptime(value, cls.format_string)


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
        return dumps(value.id)

    @classmethod
    def Deserializer(cls, obj):
        return lambda value: cls.deserialize(obj, value)

    @classmethod
    def deserialize(cls, obj, value):
        oid = loads(value)
        return DBSession.query(obj).get(oid)


class SerializerObjs(SerializerObj):
    @classmethod
    def serialize(cls, value):
        return dumps([obj.id for obj in value])

    @classmethod
    def deserialize(cls, obj, value):
        ids = loads(value)
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
    person = relationship('Person')

    institution_id = Column(Integer, ForeignKey('institutions.id'))
    institution = relationship('Institution')

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


class SerializerParticipants(object):
    @classmethod
    def serialize(cls, value):
        return dumps([participant.id for participant in value])

    @classmethod
    def deserialize(cls, value):
        return query_in_order_ids(
            DBSession.query(Participant), Participant.id, loads(value)).all()
    

# TODO store the store with teh configuration, not here
store = FSStore(
    path='/Users/myshen/var/store',
    base_url='/',
)


class FSFile(Base, AdaptedFile):
    """A file record that points to the filesystem file."""
    __tablename__ = 'fsfiles'

    id = Column(Integer, primary_key=True)

    name = Column(Unicode)

    # Stores information used by pycchdo.importer.cchdo to correlate ArgoFiles
    # with Documents and QueueFiles with QueueFiles.
    import_id = Column(Unicode)
    import_path = Column(Unicode)

    def __init__(self, fobj=None, filename=None, mimetype=None,
                 store=current_store):
        super(FSFile, self).__init__(mimetype=mimetype)
        self.file = fobj
        self.store = store
        self.name = unicode(filename)

    @staticmethod
    def from_fieldstorage(fst):
        fobj = fst.file
        filename = fst.filename
        mime = fst.type
        if not mime:
            mime = 'application/octet-stream'
        fsf = FSFile(fobj, filename, mime)
        DBSession.add(fsf)
        DBSession.flush()
        return fsf

    @classmethod
    def attr_by_import_id(cls, import_id):
        """Return _Attr matching FSFile import_id.

        """
        return _Attr.query().join(_AttrValueFile).join(FSFile).\
            filter(FSFile.import_id == import_id).first()

    def __unicode__(self):
        return u'FSFile({0}, {1!r})'.format(self.id, self.name)

    def __repr__(self):
        return unicode(self)


class SerializerFile(Serializer):
    @classmethod
    def serialize(cls, value):
        """Return the key for the file storage system."""
        return dumps(value.id)

    @classmethod
    def deserialize(cls, value):
        """Converts key for the file storage system back to cgi.FieldStorage"""
        fsfid = loads(value)
        return DBSession.query(FSFile).get(fsfid)


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
    def merge_(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        people = self.people
        for person in people:
            if person.country != self.id:
                person.set_accept('country', self.id, signer)

        for mergee in mergees:
            DBSession.delete(mergee)

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
    def merge_(self, signer, *mergees):
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
            DBSession.delete(mergee)

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


Institution.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))

Institution.allow_attrs([
    ('name', Unicode),
    ('phone', Unicode),
    ('address', Unicode),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])


class Ship(Obj):
    __tablename__ = 'ships'

    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship('Country', foreign_keys=[country_id],
        backref="ships")

    __mapper_args__ = {
        'polymorphic_identity': 'ship',
    }

    name = Column(Unicode)
    nodc_platform_code = Column(String)

# TODO make merge work
    def merge_(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        for mergee in mergees:
            DBSession.delete(mergee)

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

Ship.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))

Ship.allow_attrs([
    ('name', Unicode),
    ('nodc_platform_code', String, 'NODC Platform Code'),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])


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
    def merge_(self, signer, *mergees):
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

        cavs = CacheObjAttrs.query().\
            filter(CacheObjAttrs.obj_id.in_(mergee_ids)).all()
        for cav in cavs:
            DBSession.delete(cav)

        for mergee in mergees:
            DBSession.delete(mergee)

        self._recache()

    @classmethod
    def propose(cls, sesh, sponsor=None):
        """Propose a new Person.

        Override because a Person can be their own sponsor.

        """ 
        person = cls()
        if sponsor is None:
            sponsor = person
        change = Change(person, sponsor, None, None)
        sesh.add(change)
        sesh.flush()
        return change

    @classmethod
    def create(cls, sesh, sponsor=None):
        """Create a new Person.

        Override because a Person can be their own sponsor.

        """ 
        change = cls.propose(sesh, sponsor)
        if sponsor is None:
            sponsor = change.obj
        change.accept(sesh, sponsor)
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


Person.register_serializer_pair(
    'institution', SerializerObj.serialize, SerializerObj.Deserializer(Institution))
Person.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))

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

    _names = relationship('_CollectionName', uselist=True)
    names = association_proxy('_names', 'name')

    _basins = relationship('_CollectionBasin', uselist=True)
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

# TODO make merge work
    def merge_(self, signer, *mergees):
        """Merge this Collection with others, leaving this one."""
        names = self.names
        types = []
        mergee_ids = []
        for mergee in mergees:
            names.extend(mergee.names)
            if mergee.type:
                types.append(mergee.type)
            mergee_ids.append(mergee.id)

        names = uniquify(names)
        self.set_accept('names', names, signer)

        if self.type is None and types:
            if len(types) > 1:
                log.debug(
                    u'Merging {0} with types {1}. Picked {2}'.format(
                        self, types, types[0]))
            self.set_accept('type', types[0], signer)

        basins = list(self.get('basins', []))
        basins += list(mergee.get('basins', []))
        basins = uniquify(basins)
        if basins:
            self.set_accept('basins', basins, signer)

        # Replace all instances of mergees in cruises.collections with this one.
        cruises = self._mergee_cruises(*mergees)
        for cruise in cruises:
            colls = cruise.get(self.cruise_associate_key, [])
            for mergee_id in mergee_ids:
                try:
                    colls.remove(mergee_id)
                except ValueError:
                    pass
                if not self.id in colls:
                    colls.append(self.id)
                cruise.set_accept(self.cruise_associate_key, colls, signer)

        for mergee in mergees:
            DBSession.delete(mergee)

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


Collection.register_serializer_pair(
    'names', Serializer.serialize, Serializer.deserialize)
Collection.register_serializer_pair(
    'basins', Serializer.serialize, Serializer.deserialize)

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
        bounds = self._bounds

        # If all bounds are None, there are no bounds
        if all(x is None for x in bounds):
            return []
        return bounds

    @bounds.setter
    def bounds(self, value):
        self._bounds = value

    @property
    def display_order(self):
        # TODO
        return 0

    def __unicode__(self):
        return u'Parameter({0})'.format(self.name)

    def __repr__(self):
        return unicode(self)


Parameter.register_serializer_pair(
    'aliases', Serializer.serialize, Serializer.deserialize)
Parameter.register_serializer_pair(
    'bounds', Serializer.serialize, Serializer.deserialize)
Parameter.register_serializer_pair(
    'units', SerializerObj.serialize, SerializerObj.Deserializer(Unit))
Parameter.register_serializer_pair(
    'in_groups_but_did_not_exist', Serializer.serialize, Serializer.deserialize)

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

    name = Column(Unicode)
    _order = relationship(_ParameterGroupOrder, uselist=True)
    order = association_proxy('_order', 'parameter')

    __mapper_args__ = {
        'polymorphic_identity': 'parameter_group',
    }

    def __unicode__(self):
        return u'ParameterGroup({0}, {1})'.format(self.name, self.order)

    def __repr__(self):
        return unicode(self)

Parameter.register_serializer_pair(
    'order', SerializerObjs.serialize, SerializerObjs.Deserializer(Parameter))

ParameterGroup.allow_attrs([
    ('name', Unicode),
    ('order', IDList),
    ])


cruise_collections = Table('cruise_collections', Base.metadata,
    Column('cruise_id', Integer, ForeignKey('cruises.id')),
    Column('collection_id', Integer, ForeignKey('collections.id')),
)


cruise_institutions = Table('cruise_institutions', Base.metadata,
    Column('cruise_id', Integer, ForeignKey('cruises.id')),
    Column('institution_id', Integer, ForeignKey('institutions.id')),
)


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

    date_start = Column(DateTime)
    date_end = Column(DateTime)

    ship_id = Column(Integer, ForeignKey('ships.id'))
    ship = relationship(Ship, foreign_keys=[ship_id])
    country_id = Column(Integer, ForeignKey('countries.id'))
    country = relationship(Country, foreign_keys=[country_id])

    collections = relationship(
        'Collection', secondary=cruise_collections, backref='cruises')
    institutions = relationship(
        'Institution', secondary=cruise_institutions, backref='cruises')

# TODO
#    track = GeometryColumn(
#        LineString(2, spatial_index=False), comparator=PGComparator)

    participants = relationship(
        Participant, uselist=True, collection_class=Participants,
        cascade='all, delete-orphan')

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

    def __repr__(self):
        return u'Cruise({0}, {1})'.format(
            _repr_state(self), self.expocode)

#GeometryDDL(Cruise.__table__)

Cruise.register_serializer_pair(
    'date_start', SerializerDateTime.serialize, SerializerDateTime.deserialize)
Cruise.register_serializer_pair(
    'date_end', SerializerDateTime.serialize, SerializerDateTime.deserialize)
Cruise.register_serializer_pair(
    'statuses', Serializer.serialize, Serializer.deserialize)
Cruise.register_serializer_pair(
    'aliases', Serializer.serialize, Serializer.deserialize)
Cruise.register_serializer_pair(
    'ports', Serializer.serialize, Serializer.deserialize)
Cruise.register_serializer_pair(
    'ship', SerializerObj.serialize, SerializerObj.Deserializer(Ship))
Cruise.register_serializer_pair(
    'country', SerializerObj.serialize, SerializerObj.Deserializer(Country))
Cruise.register_serializer_pair(
    'collections', SerializerObjs.serialize, SerializerObjs.Deserializer(Collection))
Cruise.register_serializer_pair(
    'institutions', SerializerObjs.serialize, SerializerObjs.Deserializer(Institution))
Cruise.register_serializer_pair(
    'track', SerializerTrack.serialize, SerializerTrack.deserialize)
Cruise.register_serializer_pair(
    'participants', SerializerParticipants.serialize, SerializerParticipants.deserialize)
Cruise.register_serializer_pair(
    'data_suggestion', SerializerFile.serialize, SerializerFile.deserialize)


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
for key, name in data_file_human_names.items():
    Cruise.register_serializer_pair(
        key, SerializerFile.serialize, SerializerFile.deserialize)
    status_key = '{0}_status'.format(key)
    Cruise.register_serializer_pair(
        status_key, Serializer.serialize, Serializer.deserialize)

    # TODO it might be need to store links to FSFiles, not doing at this time
    # using a sqlalchemy key map

    __cruise_allow_attrs.extend([
        (key, File, name),
        (status_key, TextList),
        ])
Cruise.allow_attrs(__cruise_allow_attrs)


def main(argv):
    Base.metadata.create_all(engine)

    sesh = DBSession()

    ppp = Person.create(sesh).obj

    suggcr = Cruise.propose(sesh, ppp)
    print sesh.query(Cruise).all()
    cruise = suggcr.obj
    suggcr.accept(sesh, ppp)
    print sesh.query(Cruise).all()
    cruise.set(sesh, ppp, 'expocode', '33RR20090320')
    suggexp = cruise.sugg(sesh, ppp, 'expocode', '33RR20099999')
    suggexp.reject(sesh, ppp)
    print cruise.expocode == '33RR20090320'

    print len(suggcr.obj.changes()) == 2
    print len(suggcr.obj.changes('accepted')) == 1

    # reject Obj proposal
    suggcr = Cruise.propose(sesh, ppp)
    suggcr.reject(sesh, ppp)

    ccc1 = Cruise.create(sesh, ppp).obj
    ccc1.set(sesh, ppp, 'expocode', 'C1')
    ccc2 = Cruise.create(sesh, ppp).obj
    ccc2.set(sesh, ppp, 'expocode', 'C2')

    ccc1.set(sesh, ppp, 'date_start', datetime.now())
    ccc1.set(sesh, ppp, 'track', geojson.LineString([(0, 1), (2, 3)]))

    # File storage
    fst = FieldStorage()
    fst.filename = 'testfile'
    contents = 'contents'
    fst.file = StringIO(contents)
    with store_context(store):
        ccc1.set(sesh, ppp, 'data_suggestion', FSFile.from_fieldstorage(fst))

    with store_context(store):
        print contents == ccc1.get(sesh, 'data_suggestion').make_blob()

    fst = FieldStorage()
    fst.filename = 'asdf_hy1.csv'
    contents = 'BOTTLE,123456'
    fst.file = StringIO(contents)
    with store_context(store):
        ccc1.set(sesh, ppp, 'btl_ex', FSFile.from_fieldstorage(fst))

    with store_context(store):
        print contents == ccc1.get(sesh, 'btl_ex').make_blob()
        sesh.commit()

    suggexp = cruise.sugg(sesh, ppp, 'expocode', 'badexpo')
    suggexp.accept(sesh, ppp, 'goodexpo')
    print suggexp.value == suggexp.value_accepted
    print 'badexpo' == suggexp.value_original
    print 'goodexpo' == suggexp.obj.expocode

    fst = FieldStorage()
    fst.filename = 'asdf_hy1.csv'
    contents0 = 'BOTTLE,123456'
    fst.file = StringIO(contents0)

    fst1 = FieldStorage()
    fst1.filename = 'qwer_hy1.csv'
    contents1 = 'BOTTLE,98765'
    fst1.file = StringIO(contents1)
    with store_context(store):
        suggfff = ccc1.sugg(sesh, ppp, 'btl_ex', FSFile.from_fieldstorage(fst))
        suggfff.accept(sesh, ppp, FSFile.from_fieldstorage(fst1))
        sesh.commit()

    with store_context(store):
        print contents1 == ccc1.get(sesh, 'btl_ex').make_blob()
        print contents0 == ccc1.get(sesh, 'btl_ex', force_original=True).make_blob()

    # getting tracked data
    # retrieve attr Changes on a cruise that store files
    print len(ccc1.changes_data('accepted')) == 3
    print [suggfff] == ccc1.changes_data('accepted', replaced=True)

    # collections
    coll0 = Collection.create(sesh, ppp).obj
    coll0.set(sesh, ppp, 'names', ['000'])
    coll1 = Collection.create(sesh, ppp).obj
    coll1.set(sesh, ppp, 'names', ['111'])
    log.info('accepting cruises suggested to a collection')
    scr = ccc1.sugg(sesh, ppp, 'collections', [coll1, coll0])
    scr.accept(sesh, ppp)
    print ccc1.collections[0] == coll1
    print ccc1.collections[1] == coll0

    colbassug = coll1.sugg(sesh, ppp, 'basins', [u'southern'])
    print coll0 == sesh.query(Collection).filter(Collection.names.contains('000')).all()[0]
    print sesh.query(Collection).filter(Collection.basins.contains('southern')).count() == 0
    colbassug.accept(sesh, ppp)
    print coll1 == sesh.query(Collection).filter(Collection.basins.contains('southern')).first()

    # notes
    ccc1.change._notes.append(Note(ppp, 'note0', subject='note0s'))
    ccc1.change._notes.append(Note(ppp, 'note1', subject='note1s', discussion=True))
    log.debug( ccc1.notes)
    log.debug( ccc1.notes_public)
    log.debug( ccc1.notes_discussion)

    # country
    cou0 = Country.create(sesh, ppp).obj
    cou0.name = 'United States of America'
    cou0.alpha2 = 'US'
    cou0.alpha3 = 'USA'

    cou = sesh.query(Country).filter(Country.alpha3 == 'USA').first()
    print cou == cou0
    ppp.set(sesh, ppp, 'country', cou0)
    print cou.people

    # Parameter
    param0 = Parameter.create(sesh, ppp).obj
    unit0 = Unit.create(sesh, ppp).obj
    unit0.set(sesh, ppp, 'name', 'decibars')
    unit0.set(sesh, ppp, 'mnemonic', 'DBAR')
    param0.set(sesh, ppp, 'name', 'CTDPRS')
    param0.set(sesh, ppp, 'full_name', 'CTDPRS')
    param0.set(sesh, ppp, 'units', unit0)

    pg0 = ParameterGroup.create(sesh, ppp).obj
    pg0.set(sesh, ppp, 'name', 'Primary')
    pg0.set(sesh, ppp, 'order', [param0])
    print pg0.order == [param0]

    sesh.flush()

    # Participants
    part0 = Participant.create(sesh, 'chief_scientist', ppp)
    part1 = Participant.create(sesh, 'cochief_scientist', ppp)

    participants = Participants(part0, part1)
    part = cruise.sugg(sesh, ppp, 'participants', participants)
    print [] == cruise.participants
    part.accept(sesh, ppp)
    print participants == cruise.participants

    # permissions
    print [] == part.permissions_read
    part.permissions_read.append('staff')
    print ['staff'] == part.permissions_read

    print cruise.mtime

    print 
    print 'this one should fail for now'
    somedict = {'a': 1, 'b': 2}
    suggsom = cruise.sugg(sesh, ppp, 'something', somedict)
    suggsom.accept(sesh, ppp)

    #from libcchdo.tools import HistoryConsole
    #console = HistoryConsole(locals=locals())
    #print repr(locals())
    #console.interact('hi')

    return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv))

