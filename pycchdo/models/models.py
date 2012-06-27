from datetime import datetime
from tempfile import mkdtemp
from string import capwords
import re

from webob.multidict import MultiDict

# underlying FS implementation
from django.conf import settings as django_settings
from django.core.files.storage import FileSystemStorage
from django.core.files.base import File as DjangoFile
from django.utils.functional import empty

from sqlalchemy import (
    create_engine,
    event,
    Column,
    ForeignKey,
    Table,
    )
from sqlalchemy.exc import StatementError
from sqlalchemy.types import (
    TypeEngine,
    Integer, Boolean, Enum, Text, String, Unicode, DateTime, TIMESTAMP,
    )
from sqlalchemy.sql import (
    and_, not_,
    case, select, exists,
    )
from sqlalchemy.orm import (
    backref,
    scoped_session,
    sessionmaker,
    composite,
    relationship,
    object_session,
    )
from sqlalchemy.orm.collections import collection, attribute_mapped_collection
from sqlalchemy.ext.associationproxy import (
    association_proxy, AssociationProxy, _AssociationList)
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from sqlalchemy.ext.mutable import MutableComposite
from sqlalchemy.ext.declarative import (
    declarative_base,
    declared_attr, 
    )

from zope.sqlalchemy import ZopeTransactionExtension

from geoalchemy import LineString

import shapely.wkt
import shapely.geometry

import geojson

from libcchdo.fns import uniquify

from pycchdo.util import (
    flatten,
    str2uni,
    FileProxyMixin,
    deprecated,
    )
import triggers as triggers
from pycchdo.log import ColoredLogger


log = ColoredLogger(__name__)


__all__ = [
    'data_file_human_names',
    'data_file_descriptions',
    'DBSession', 
    'Base', 
    'Stamp',
    'Note',
    'FSFile',
    'RequestForAttr',
    'FileComposite',
    'Obj',
    'Person',
    'Cruise',
    'CruiseAssociate',
    'CruiseParticipantAssociate',
    'Country',
    'Institution',
    'Ship',
    'Collection',
    'ArgoFile',
    'OldSubmission',
    'Submission',
    'Parameter',
    'Unit',
    'ParameterOrder',
    '_Change',
    '_Attr',
]


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


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


Base = declarative_base()


def _reset_database(engine):
    """Clears the database and recreates schema."""
    meta = Base.metadata
    meta.reflect(bind=engine)
    for table in reversed(meta.sorted_tables):
        table.drop()
    Base.metadata.create_all(engine)


def timestamp_now():
    """Create a datetime.datetime representing Now."""
    # FIXME This needs to make a datetime that is timezone aware
    return datetime.utcnow()


class Stamp(MutableComposite):
    def __init__(self, person_id, timestamp=None):
        """Create a Stamp representing a Person and a time.

        Arguments::
        person_id -- the Person id
        timestamp -- the time (default: now)

        """
        self.person_id = None
        self.timestamp = None
        if person_id:
            self.person_id = person_id
            if not timestamp:
                timestamp = timestamp_now()
            self.timestamp = timestamp
        elif timestamp:
            raise ValueError('Stamp must have a Person')

    def __composite_values__(self):
        return [self.person_id, self.timestamp, ]

    def __setattr__(self, key, value):
        """Intercept set events and alert parents to change."""
        object.__setattr__(self, key, value)
        self.changed()

    def __eq__(self, other):
        if self.person_id is None and self.timestamp is None and other is None:
            return True
        if type(other) is not Stamp:
            return False
        return (
            self.person_id == other.person_id and 
            self.timestamp == other.timestamp)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __unicode__(self):
        if self.__eq__(None):
            return u'Stamp(empty)'
        return u"Stamp(%s, %s)" % (
            self.person_id, self.timestamp.strftime('%FT%T'))

    def __repr__(self):
        return unicode(self)


class Note(Base):
    """ A Note that can be attached to any _Change

    A _Change may have many Notes.

    Attrs:
        creation_stamp - creation stamp
        body - the actual note
        action - the action taken
        data_type - the type of data that was changed
        subject - a nice summary
        discussion - Setting this True makes the note only visible
                     for mergers.
                     
    """
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True)

    creation_timestamp = Column(DateTime, default=timestamp_now)
    creation_person_id = Column(ForeignKey('people.id'))
    creation_stamp = composite(Stamp, creation_person_id, creation_timestamp)
    #creation_person = relationship('Person', primaryjoin="Note.creation_person_id==Person.id")

    body = Column(Unicode)
    action = Column(Unicode)
    data_type = Column(Unicode)
    subject = Column(Unicode)
    discussion = Column(Boolean)

    change_id = Column(ForeignKey('changes.id'))

    def __init__(self, person, body=None, action=None, data_type=None,
                 subject=None, discussion=False):
        self.creation_stamp = Stamp(person.id)
        self.body = body
        self.action = action
        self.data_type = data_type
        self.subject = subject
        self.discussion = discussion

    def __unicode__(self):
        try:
            return u'Note(%s, %s)' % (self.id, self.subject)
        except AttributeError:
            try:
                return u'Note(%s)' % self.id
            except AttributeError:
                return u'Note()'


@event.listens_for(Note, 'after_insert')
@event.listens_for(Note, 'after_update')
def _saved_note(mapper, connection, target):
    triggers.saved_note(target)


@event.listens_for(Note, 'after_delete')
def _deleted_note(mapper, connection, target):
    triggers.deleted_note(target)


class FSFile(Base, FileProxyMixin):
    __tablename__ = 'fsfile'

    id = Column(Integer, primary_key=True)
    fsid = Column(Unicode)
    name = Column(Unicode)
    content_type = Column(String)
    upload_date = Column(TIMESTAMP)

    _fs = None

    def __init__(self, file=None, filename=None, contentType=None):
        if file:
            self.file = DjangoFile(file)
        self.name = filename
        self.content_type = contentType

    @property
    def fs(self):
        if not self._fs:
            self.reconfig_fs_storage()
        return self._fs
    
    @classmethod
    def reconfig_fs_storage(cls, root=None, url='', perms=0644):
        if not root:
            root = mkdtemp()
        django_settings._wrapped = empty
        django_settings.configure(
            MEDIA_ROOT=root,
            MEDIA_URL=url,
            FILE_UPLOAD_PERMISSIONS=perms,
        )
        cls._fs = FileSystemStorage()


@event.listens_for(FSFile, 'before_insert')
def _saved_file(mapper, connection, target):
    target.fsid = target.fs.save(target.fs.get_available_name(''), target.file)


@event.listens_for(FSFile, 'load')
def _loaded_file(target, context):
    target.file = target.fs.open(target.fsid)


@event.listens_for(FSFile, 'before_delete')
def _deleted_file(mapper, connection, target):
    target.fs.delete(target.fsid)


class _Change(Base):
    """ A Change to the dataset that should be recorded along with the time and
    person who changed it.

    Changes may be accepted or rejected. Changes may also have attached notes
    which may themselves be public or for dicussion purposes only.

    """
    __tablename__ = 'changes'
    id = Column(Integer, primary_key=True)
    accepted = Column(Boolean, default=False)
    notes = relationship(
        'Note', backref='change', lazy='dynamic',
        cascade='all, delete, delete-orphan')
    notes_public = relationship(
        'Note', viewonly=True,
        primaryjoin='and_(Note.change_id == _Change.id, not_(Note.discussion))')
    notes_discussion = relationship(
        'Note', viewonly=True,
        primaryjoin='and_(Note.change_id == _Change.id, Note.discussion)')
    obj_type = Column(String)

    ctime = creation_timestamp = Column(DateTime, default=timestamp_now)
    creation_person_id = Column(ForeignKey('people.id'))
    creation_stamp = composite(Stamp, creation_person_id, creation_timestamp)
    #creation_person = relationship('Person', 
    #    primaryjoin="_Change.creation_person_id==Person.id", post_update=True)

    pending_timestamp = Column(DateTime)
    pending_person_id = Column(ForeignKey('people.id'))
    pending_stamp = composite(Stamp, pending_person_id, pending_timestamp)
    #pending_person = relationship('Person', 
    #    primaryjoin="_Change.pending_person_id==Person.id")

    judgment_timestamp = Column(DateTime)
    judgment_person_id = Column(ForeignKey('people.id'))
    judgment_stamp = composite(Stamp, judgment_person_id, judgment_timestamp)
    #judgment_person = relationship('Person', 
    #    primaryjoin="_Change.judgment_person_id==Person.id")

    __mapper_args__ = {
        'polymorphic_on': obj_type,
    }

    def __init__(self, person, note=None, *args, **kwargs):
        super(_Change, self).__init__(*args, **kwargs)
        self._set_creation_stamp(person)
        if note:
            self.add_note(note)

    def _set_creation_stamp(self, person):
        """Set the creation_stamp for person."""
        self.creation_stamp = Stamp(person.id)

    def is_judged(self):
        return self.judgment_stamp != None

    def is_acknowledged(self):
        return self.pending_stamp != None

    def is_accepted(self):
        return self.is_judged() and self.accepted

    def is_rejected(self):
        return self.is_judged() and not self.accepted

    def accept(self, person):
        self.judgment_stamp = Stamp(person.id)
        self.accepted = True

    def acknowledge(self, person):
        if not self.pending_stamp:
            self.pending_stamp = Stamp(person.id)

    def reject(self, person):
        self.judgment_stamp = Stamp(person.id)
        self.accepted = False

    @deprecated('Use _Change.notes.append(note)')
    def add_note(self, note):
        self.notes.append(note)

    @deprecated('Use _Change.notes.remove(note)')
    def remove_note(self, note):
        self.notes.remove(note)

    def __repr__(self):
        return u'{}({})'.format(type(self).__name__, self.id)


@event.listens_for(_Change.notes, 'append')
def _appended_note(target, value, initiator):
    triggers.saved_note(target)


@event.listens_for(_Change.notes, 'remove')
def _removed_note(target, value, initiator):
    triggers.removed_note(target)


class RequestFor(Base):
    """ Information about HTTP request of another object """
    __tablename__ = 'requests_for'

    id = Column(Integer, primary_key=True)

    dt = Column(DateTime)
    ip = Column(String)
    type = Column(String)

    def __init__(self, request):
        """ Takes a webob request and stores relevant information related to
        tracking.

        Parameters:
            request - the webob.Request

        """
        try:
            self.dt = request.date
            self.ip = request.remote_addr
            if not type(self.dt) is datetime:
                raise ValueError()
            if not is_valid_ip(self.ip):
                raise ValueError()
        except (AttributeError, ValueError):
            # Don't store request if either of these are invalid or missing
            return False
        try:
            self.date = request.date
        except AttributeError:
            pass

    __mapper_args__ = {
        'polymorphic_identity': 'request_for',
        'polymorphic_on': type,
    }


class RequestForAttr(RequestFor):
    __tablename__ = 'requests_for_attrs'

    id = Column(ForeignKey('requests_for.id'), primary_key=True)
    attr_id = Column(ForeignKey('attrs.id'))

    __mapper_args__ = {
        'polymorphic_identity': 'request_for_attr',
    }


class FileComposite(object):
    """A composite for storing files.

    """
    def __init__(self, fileid):
        self.fileid = fileid

    def get(self, fs):
        return fs.get(self.fileid)

    @classmethod
    def store(cls, fs, field):
        """ Stores the file described by field in the filesystem and keeps a
        reference

        Raises: AttributeError when field does not have file, filename, and type

        """
        file = field.file
        filename = field.filename
        content_type = field.type

        try:
            id = fs.put(file, filename=filename, contentType=content_type)
        except Exception, e:
            raise e
        return cls(id)


# Types for database storage
class ID(Integer):
    pass


class IDList(TypeEngine):
    pass


class TextList(TypeEngine):
    pass


class File(TypeEngine):
    pass


class _AttrValue(Base):
    """A value stored by _Attr.

    Meant to be abstract but has a concrete table because it contains the
    reference to the _Attr that helps with polymorphic querying.

    """
    id = Column(Integer, primary_key=True)
    type = Column(String)

    accepted = Column(Boolean, default=False)
    attr_id = Column(ForeignKey('attrs.id'))

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def __mapper_args__(cls):
        if cls.__name__ == '_AttrValue':
            return {
                'polymorphic_on': cls.type,
                'polymorphic_identity': cls.__name__,
            }
        else:
            return {
                'polymorphic_identity': cls.__name__,
            }

    @hybrid_property
    def value(self):
        raise ValueError('_AttrValue is not a valid storage container.')

    @value.expression
    def value(cls):
        return '{}.{}'.format(cls.__name__, 'value')

    def __repr__(self):
        return u'{}({}, {})'.format(type(self).__name__, self.id, self.value)


@event.listens_for(DBSession, 'after_flush')
def delete_attrvalue_orphans(session, ctx):
    """Clean up _AttrValues whose _Attrs no longer exist.

    Called after each session flush.

    """
    orphans = session.query(_AttrValue).with_polymorphic('*').\
        filter(~_AttrValue.attr.has())
    for orphan in orphans:
        session.delete(orphan)


class _AttrValueNone(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)

    @hybrid_property
    def value(self):
        return None


class _AttrValueInteger(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Integer)


class _AttrValueBoolean(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Boolean)


class _AttrValueUnicode(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Unicode)


class _AttrValueDatetime(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(DateTime)


class _AttrValueLineString(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(LineString)

    def _verify_and_normalize_linestring(self, value):
        """Convert value into a Shapely LineString."""
        if type(value) is shapely.geometry.linestring.LineString:
            return value
        elif type(value) is geojson.LineString:
            value = shapely.geometry.shape(value)
        else:
            assert not isinstance(value, str)
            for i, c in enumerate(value):
                assert not isinstance(c, str)
                assert len(c) is 2
                try:
                    float(c[0])
                    float(c[1])
                except ValueError:
                    raise TypeError(
                        'Coordinate list must contain numbers. '
                        'Element %d does not' % i)
            value = shapely.geometry.linestring.LineString(value)
        return value

    def __init__(self, value):
        value = self._verify_and_normalize_linestring(value)
        self.value = value.wkt


class _AttrValueFile(_AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    value_ = Column('value', ForeignKey('fsfile.id'))
    value = relationship(
        'FSFile', primaryjoin='FSFile.id == _AttrValueFile.value_')

    def __init__(self, value):
        self.value = FSFile(value.file, value.filename)


class _AttrValueElem(Base):
    """Base for _AttrValueList elements."""
    __abstract__ = True

    @declared_attr
    def id(cls):
        return Column(Integer, primary_key=True)

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.value == other.value
        return self.value == other

    def __ne__(self, other):
        if isinstance(other, type(self)):
            return self.value != other.value
        return self.value != other

    def __unicode__(self):
        return self.value

    def __repr__(self):
        return u'{}({}, {}, {})'.format(
            type(self).__name__, self.id, self.attrvalue_id, unicode(self))


class _AttrValueElemID(_AttrValueElem):
    __tablename__ = '_attrvalueelemid'
    attrvalue_id = Column(ForeignKey('_attrvalue.id'))
    value = Column(ID)


class _AttrValueElemText(_AttrValueElem):
    __tablename__ = '_attrvalueelemtext'
    attrvalue_id = Column(ForeignKey('_attrvalue.id'))
    value = Column(Text)


class _AttrValueList(object):
    # TODO figure out why value must be declared for each list type rather than
    # inherited
    pass


class _AttrValueListID(_AttrValueList, _AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    values = relationship(
        _AttrValueElemID, cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListText(_AttrValueList, _AttrValue):
    id = Column(ForeignKey('_attrvalue.id'), primary_key=True)
    values = relationship(
        _AttrValueElemText, cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrPermission(Base):
    """Permissions associated with an _Attr.

    Permissions for _Attrs are subdivided into read and write.
    # TODO perms need to store dicts...

    """
    __tablename__ = 'attrs_permissions'
    attr_id = Column(ForeignKey('attrs.id'), primary_key=True)
    perm_type = Column(Enum('read', 'write'), default='read', primary_key=True)
    permission = Column(Unicode, primary_key=True)

    def __init__(self, perm_type, permission):
        self.perm_type = perm_type
        self.permission = permission


class _AttrValueTransformer(Comparator):
    def operate(self, op, other):
        def transform(q):
            clause = self.__clause_element__()
            log.debug(repr(clause) + str(clause))
            parent_alias = aliased(clause)
            return q.join(parent_alias, clause.parent).\
                filter(op(parent_alias.parent, other))

            #return and_(_AttrValue.attr_id == _Attr.id, _AttrValue.accepted == False)
            #return case([
            #    (cls.deleted == True, None),
            #    #(exists(select(cls.v_accepted)), cls.v_accepted),
            #], else_=cls.v)
        return transform


class _Attr(_Change):
    """An _Attr of an _AttrMgr.

    Not for general use. Please defer to _AttrMgr's methods.

    The life of an _Attr
    ====================

    States
    ------
    The possible states of an _Attr are::

    1. Suggested
    2. Acknowledged
    3. judged
      a. accepted
        i. As is
        ii. With new value
      b. Rejected

    Accepted value
    --------------
    In addition to being accepted, an _Attr may be accepted with a new
    value. This is useful for handling user suggestions. E.g.

    1. suggested: An _Attr has been attached to a Cruise using a key

    >>> aaa = _Attr(submitter, cruise, 'bottle_exchange', File,
    >>>             'bottle_exchange', preliminary_file)

    2. acknowledged: The suggestion has been reviewed by staff and is
           being actively worked on.

    >>> aaa.acknowledge(staff_working_on_file)

    The states diverge here for acceptance and acceptance with a new value::

    3a. accepted as is -- The suggestion has been accepted as is and becomes
    part of the object state. In this case, the preliminary_file would have been
    reviewed by a merger and determined to be good for public dissemination.

    >>> aaa.accept(staff_working_on_file)
    >>> aaa.value == preliminary_file
    True

    3. accepted with new value -- The suggestion has been accepted but a new
    value is added. The original value is still stored but only as the suggested
    value.

    A case where this is useful: a partial file has been suggested as
    "bottle_exchange" on a cruise. A merger finishes merging the partial
    file with the original and accepts the partial file with the merged file as
    the new value. Both merged and partial are retained in history but only the
    merged becomes part of the object state.

    >>> aaa.accept_value(someone, merged_file)
    >>> aaa.value == merged_file
    True
    >>> aaa.value_original == preliminary_file
    True

    """
    __tablename__ = 'attrs'

    id = Column(ForeignKey('changes.id'), primary_key=True)
    key = Column(Unicode)
    type = Column(String)
    deleted = Column(Boolean)
    obj_id = Column(ForeignKey('objs.id'))

    @declared_attr
    def obj(cls):
        return relationship(
            'Obj', primaryjoin='_Attr.obj_id == Obj.id',
            single_parent=True,
            backref=backref(
                'attrs',
                lazy='dynamic',
                order_by=_Change.judgment_timestamp.desc,
                cascade='all, delete, delete-orphan',
                ),
            )

    vs = relationship(
        _AttrValue, primaryjoin='and_(_AttrValue.attr_id == _Attr.id)',
        uselist=False, single_parent=True,
        backref='attr', cascade='all, delete, delete-orphan')
    v = relationship(
        '_AttrValue', primaryjoin='and_(_AttrValue.attr_id == _Attr.id, '
                                  '_AttrValue.accepted == False)',
        uselist=False, single_parent=True,
        cascade='all, delete, delete-orphan')
    v_accepted = relationship(
        '_AttrValue', primaryjoin='and_(_AttrValue.attr_id == _Attr.id, '
                                  '_AttrValue.accepted == True)',
        uselist=False, single_parent=True,
        cascade='all, delete, delete-orphan')

    #permissions_ = relationship(
    #    _AttrPermission,
    #    collection_class=attribute_mapped_collection('perm_type'),
    #    cascade='all, delete-orphan')
    #permissions = association_proxy(
    #    'permissions_', 'perm_type',
    #    creator=lambda k, v: _AttrPermission(perm_type=v, permission=k))

    permissions_read_ = relationship(
        _AttrPermission,
        primaryjoin='and_(_AttrPermission.attr_id == _Attr.id, '
                    "_AttrPermission.perm_type == 'read')",
        cascade='all, delete-orphan')
    permissions_read = association_proxy(
        'permissions_read_', 'permission',
        creator=lambda x: _AttrPermission('read', x))
    permissions_write_ = relationship(
        _AttrPermission,
        primaryjoin='and_(_AttrPermission.attr_id == _Attr.id, '
                    "_AttrPermission.perm_type == 'write')",
        cascade='all, delete-orphan')
    permissions_write = association_proxy(
        'permissions_write_', 'permission',
        creator=lambda x: _AttrPermission('write', x))

    requests = relationship(
        'RequestForAttr', backref='attr', cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': '_attr',
    }

    def __init__(self, person, key, type, value=None, note=None, deleted=False):
        """Create an _Attr _Change state.

        Arguments::
        person -- the person who performed the change
        key -- the attribute name that this change is for
        type -- the type of value that this _Attr stores. This
            should be an sqlalchemy type
        
        Keyword arguments::
        value -- the value to store
        note -- a note to add during creation; syntactic sugar
        deleted -- whether this _Attr's new state is deleted. If this is True,
            the _Attr's value is disregarded.

        """
        super(_Attr, self).__init__(person)

        self.key = key
        self.type = _AttrMgr.attr_type_to_str(type)
        self.constructor = _AttrMgr.value_class(type)

        self.deleted = deleted
        if not deleted:
            self._set(value)

        if note is not None:
            self.add_note(note)

    def _set(self, value, accepted=False):
        """Set the _Attr value.

        Validate and store the value.

        Raises:
            TypeError when value does not match the defined type for the _Attr
        
        Special cases::
        value -- a cgi.FieldStorage-like object
            Attempts to store the file in the filesystem and stores the id in
            the 'file' attribute.
        key -- track
            Stores the value (which must be a GeoJSON linestring coordinate
            list) in the 'track' attribute.
        accepted -- whether to set the value for the original or accepted state

        """
        cannot_be_stored_error = TypeError(
            '{} cannot be stored as {}'.format(value, self.constructor))

        if value is None and self.type == 'ID':
            raise ValueError(
                'IDs should not be None. Is the object persisted?')

        try:
            if accepted:
                self.v_accepted = self.constructor(
                    value=value, accepted=accepted)
            else:
                self.v = self.constructor(value=value)
        except StatementError:
            raise cannot_be_stored_error

    def accept_value(self, value, person):
        """Accept the _Attr with a new value.
        
        Example use case::
        The original value of _Attr was a suggestion from a human and the new
        value is a moderated known-good value.

        """
        self._set(value, accepted=True)
        self.accept(person)

    @hybrid_property
    def attr_value(self):
        """Return the current _AttrValue of the _Attr.

        This takes into account whether the _Attr has been accepted with a new
        value.

        """
        if self.deleted:
            raise KeyError(self.key)
        if self.v_accepted:
            return self.v_accepted
        return self.v

    @hybrid_property
    def attr_value_original(self):
        """Return the original _AttrValue of the _Attr."""
        if self.deleted:
            raise KeyError(self.key)
        return self.v

    @hybrid_property
    def value(self):
        """Return the current value of the _Attr.

        This takes into account whether the _Attr has been accepted with a new
        value.

        """
        return self.attr_value.value

    @hybrid_property
    def value_original(self):
        """Return the original value of the _Attr."""
        return self.attr_value_original.value

    def remove(self):
        self.delete_file()
        super(_Attr, self).remove()

    def __repr__(self):
        try:
            mapping = u'{}, {}'.format(self.key, self.value)
        except KeyError:
            mapping = u'DEL'
        except IOError:
            mapping = u'404'

        state = 'SUGG'
        if self.accepted:
            if self.v_accepted:
                state = 'NEW'
            else:
                state = 'ASIS'
        elif self.pending_stamp != None:
            state = 'ACK'

        try:
            attr_class = self.obj.attr_class(self.key)
        except AttributeError:
            attr_class = '???'

        id = self.id or '?'
        return u"_Attr({}, {}, {}, {}, {})".format(
            mapping, state, self.type, attr_class, id)

    @classmethod
    def all_data(cls):
        return object_session(self).query(_Attr).filter(_Attr.type == 'File').all()

    @classmethod
    def all_track(cls):
        return object_session(self).query(_Attr).filter(_Attr.type == 'LineString').all()

    @classmethod
    def pending(cls):
        return object_session(self).query(_Attr).filter(_Change.judgment_stamp == None).all()


class _AttrMgr(object):
    """Abstract class grouping _Attr related functionality.

    This includes modifiying _Attrs and querying them.

    _AttrMgrs define _Attr keys and types that are to be tracked. The value to
    be assigned to a key must match the type specified.

    Queries can be performed on _AttrMgrs based on the values of _Attrs.

    The main methods that _AttrMgrs have are get(), set() and delete().
    These methods, along with the _Attr implementation, govern how _Attr
    data is stored.

    Many queries on _Attrs involve their _Change status or type. These are
    easy queries. The tricky ones are obtaining Objs that are associated to
    other Objs through _Attrs. This involves finding _Attrs whose value
    contains the ID of one Obj with proper filtering and then collecting the
    Objs using the _Attrs. E.g. finding Cruises belonging to a Collection.

    TODO better writeup

    It could be best to construct a connection table with _Attr like attributes. However, does this consider the case of non-relational values?

    For example, a Collection to Cruise mapping through _Attr. The mapping
    should be tracked. This means the mapping has notes, acceptance, and
    creation, pending, and judgment stamps.

    Possible solution:
      Create a table for Collections.
      Create a table for Cruises.
      Create a mapping table for CruisesCollections with additional association with _Attr.
      _Attr knows about this mapping table and can pull up the correct Cruise-Collection mapping when called.
      Create a table for value types
      _Attr also knows about these value types and can pull up the correct value when called.

    Evaluation:
    * Does this allow querying in SQL?
      SQL can find CruisesCollection that match, find _Attr, and then find Cruise.
    * Does this allow querying values?
      SQL can find values that match, find _Attr, then find Cruise.

    How does setting an _Attr work then?
      1. Create an _Attr, saving its creation stamp
      2. The Mgr knows the _Attr's type. Verify and pass it along to the _Attr.
      3. The _Attr knows enough to persist its value.
      4. The _Attr needs to be accepted with a different value. How does it know where to look for its value?
      5. The _Attr knows its type and puts it in Integer, None, Boolean, etc How to tell apart which one is original and accepted?
      6. Store with a flag indicating whether the value is original. Filter based on current value?
        
    """
    __allowed_attrs__ = MultiDict()

    @classmethod
    def attr_type_to_str(cls, type):
        return type.__name__


    @classmethod
    def allow_attr(cls, key, type, name=None):
        """Add an _Attr definition to the list of allowed keys.

        Arguments:
        key -- (str)
        type -- (sqlalchemy type) the type of data that can be stored for key
        name -- (str) name of this key for humans (default: capitalized words
            with underscores converted to spaces)

        """
        attrs = cls.__allowed_attrs__
        if not name:
            name = capwords(key.replace('_', ' '))

        d = {'type': type, 'name': name}
        try:
            if d != attrs[key]:
                raise TypeError('{} already allowed for {} as {}. Clobbering '
                    'with {} will cause unexpected behavior.'.format(
                    key, cls, attrs[key], d))
        except KeyError:
            pass
        attrs[key] = d

        d = MultiDict()
        for key, attr in attrs.items():
            type = cls.attr_type_to_str(attr['type'])
            try:
                d[type].append(key)
            except KeyError:
                d[type] = [key]
        cls.allowed_attrs = d
        cls.allowed_attrs_list = attrs.keys()

        d = {}
        for key, attr in attrs.items():
            d[key] = attr['name']
        cls.allowed_attrs_human_names = d
        return d

    @classmethod
    def attr_type(cls, key):
        """Return the type of data allowed for key."""
        attrs = cls.__allowed_attrs__
        try:
            return attrs[key]['type']
        except KeyError:
            raise ValueError('{} is not an allowed key'.format(key))

    @classmethod
    def value_class(cls, type):
        """Get the _AttrValue class corresponding to the type."""
        if type is String:
            return _AttrValueUnicode
        elif type is Unicode:
            return _AttrValueUnicode
        elif type is Text:
            return _AttrValueUnicode
        elif type is Integer:
            return _AttrValueInteger
        elif type is DateTime:
            return _AttrValueDatetime
        elif type is ID:
            return _AttrValueInteger
        elif type is IDList:
            return _AttrValueListID
        elif type is TextList:
            return _AttrValueListText
        elif type is File:
            return _AttrValueFile
        elif type is LineString:
            return _AttrValueLineString

        raise TypeError(
            'Unknown type {} cannot be stored in _Attr system.'.format(type))

    @classmethod
    def attr_class(cls, key):
        """Return the class for the type allowed for key."""
        return cls.value_class(cls.attr_type(key))

    def _do_attr_query(self, finder, query={}, **kwargs):
        q = {'obj': self.id}
        if query:
            q.update(query)
            return finder(q, **kwargs)
        else:
            q.update(**kwargs)
            return finder(q)

    def find_attrs(self, query={}, **kwargs):
        return self._do_attr_query(_Attr.find, query, **kwargs)

    def find_attr(self, query={}, **kwargs):
        return self._do_attr_query(_Attr.find_one, query, **kwargs)

    def attrsq(self, key=None, accepted_only=True):
        """Return a query for _Attrs in the _AttrMgr with key.

        Arguments::
        key -- the key (default: None)
        accepted_only -- whether to limit the query to accepted _Attrs (default:
            True)

        """
        attrs = self.attrs
        if key:
            attrs = self.attrs.filter(_Attr.key == key)
        if accepted_only:
            attrs = attrs.filter(_Change.accepted == True)
        if attrs:
            return attrs
        else:
            raise KeyError("No _Attr '{}' for {}".format(key, self))

    @deprecated('Use attrsq() or attrs instead of history()')
    def history(self, key=None, **kwargs):
        return self.attrsq(key, **kwargs)

    @deprecated('Use attrsq() instead of get_attr()')
    def get_attr(self, key):
        """Return the most recent accepted _Attr for key."""
        return self.attrsq(key).first()

    def get(self, key, default=None):
        """Return the value of the most recent accepted _Attr for key.

        Arguments::
        key -- the key to fetch the _Attr for
        default -- if the key is not defined, return this (default: None)

        """
        try:
            attr = self.attrsq(key).first()
            value = attr.value
            if type(value) is _AssociationList:
                # AssociationList goes out of scope after return; get value now
                return list(value)
            return value
        except (AttributeError, KeyError):
            return default

    def set(self, key, value, person, note=None):
        """Set the value for key.

        Raises:
            ValueError when the key is not allowed.

        """
        try:
            restrictions = self.__allowed_attrs__[key]
        except KeyError:
            raise ValueError("'{}' is not an allowed key".format(key))
        # TODO
        # Don't check for type here. This can/will be done at flush time by the
        # engine
        #if type(value) != restrictions['type']:
        #    raise TypeError('expected {}, got {}'.format(
        #        restrictions['type'], type(value)))
        type = restrictions['type']
        attr = _Attr(person, key, type, value, note)
        self.attrs.append(attr)
        return attr

    def delete(self, key, person, note=None):
        """Delete the value for key."""
        try:
            restrictions = self.__allowed_attrs__[key]
        except KeyError:
            raise ValueError("'{}' is not an allowed key".format(key))
        type = restrictions['type']
        attr = _Attr(person, key, type, note=note, deleted=True)
        self.attrs.append(attr)
        return attr

    def set_accept(self, key, value, person, note=None):
        """Set the value for key and accept immediately."""
        attr = self.set(key, value, person, note)
        attr.accept(person)
        return attr

    def delete_accept(self, key, person, note=None):
        """Delete the value for key and accept immediately."""
        attr = self.delete(key, person, note)
        attr.accept(person)
        return attr

    @property
    def attrs_current(self):
        """Return a map of the most current _Attrs on the _AttrMgr by key."""
        curr = {}
        deleted = set()
        for attr in self.attrs.filter(_Change.accepted == True).all():
            k = attr.key
            if k not in curr and k not in deleted:
                if attr.deleted:
                    deleted.add(k)
                else:
                    curr[k] = attr
        return curr

    @property
    def attr_keys(self):
        """Return list of the _Attrs present for this _AttrMgr.

        This list does not include attributes that previously existed but
        are now deleted.

        """
        return self.attrs_current.keys()

    @hybrid_property
    def tracked(self, *args, **kwargs):
        return self.attrs

    @hybrid_property
    def tracked_data(self):
        return self.tracked.filter(_Attr.type == 'File')

    @hybrid_property
    def unjudged_tracked(self):
        return self.tracked.filter(_Change.judgment_timestamp == None).\
            filter(_Change.judgment_person_id == None)

    @hybrid_property
    def unjudged_tracked_data(self):
        return self.unjudged_tracked.filter(_Attr.type == 'File')

    @hybrid_property
    def unacknowledged_tracked(self):
        return self.unjudged_tracked.filter(_Change.pending_timestamp == None).\
            filter(_Change.pending_person_id == None)

    @hybrid_property
    def pending_tracked(self):
        return self.unjudged_tracked.filter(_Change.pending_timestamp != None).\
            filter(_Change.pending_person_id != None)

    @hybrid_property
    def pending_tracked_data(self):
        return self.pending_tracked.filter(_Attr.type == 'File')

    @hybrid_property
    def accepted_tracked(self):
        return self.tracked.filter(_Change.accepted == True)

    @hybrid_property
    def accepted_tracked_data(self):
        return self.accepted_tracked.filter(_Attr.type == 'File')

    @hybrid_property
    def accepted_tracked_changed_data(self):
        return self.accepted_tracked_data.filter(_Attr.v_accepted)

    @classmethod
    def _attr_value_key(cls, key, value_key=None):
        if value_key:
            return '%s.%s' % (key, value_key)
        return key

    @classmethod
    def _get_by_attrs_true_match(cls, obj, value_key, accepted_only=True,
                                 **kwargs):
        """Make sure the most current values match by filtering resulting objs.

        """
        if obj is None or (accepted_only and not obj.accepted):
            return False
        for k, v in kwargs.items():
            key = cls._attr_value_key(k, value_key)
            obj_v = obj.get(k)

            if type(obj_v) is list and type(v) is not list:
                if '.' in key:
                    try:
                        i = int(key.split('.')[1])
                        try:
                            return v.match(obj_v[i])
                        except AttributeError:
                            return v == obj_v[i]
                    except ValueError:
                        # The user has specified a non integer in the array
                        # index portion of the query. Things should have failed
                        # long ago.
                        pass
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
    def _get_by_attrs_query(cls, k, v, value_key):
        value_query = str2uni(v)
        return {
            'key': unicode(k),
            'accepted': True,
            '$or': [
                 {'$and': [
                     {'accepted_value': {'$ne': None}},
                     {cls._attr_value_key('accepted_value', value_key):
                      value_query},
                 ]}, 
                 {'$and': [
                     {'accepted_value': None},
                     {cls._attr_value_key('value', value_key): value_query},
                 ]}, 
            ]
        }

    @classmethod
    def filter_by_key_value(cls, query, key, value):
        attrclass = cls.attr_class(key)
        query = query.join(attrclass).filter(_Attr.key == key)

        expect_list = type(attrclass.value) == AssociationProxy
        if type(value) is list:
            for v in value:
                if expect_list:
                    query = query.filter(attrclass.value.contains(v))
                else:
                    query = query.filter(attrclass.value == v)
        else:
            if expect_list:
                query = query.filter(attrclass.value.contains(value))
            else:
                query = query.filter(attrclass.value == value)

        return query

    @classmethod
    def _get_by_attrs_true_match2(cls, obj, dict, accepted_only=True):
        """Filter resulting objs to ensure the most current values match."""
        if obj is None or (accepted_only and not obj.accepted):
            return False

        def listlike(x):
            try:
                len(x)
                x.append
                return True
            except (TypeError, AttributeError):
                return False
            
        for k, v in dict.items():
            key = k
            obj_v = obj.get(k)

            if listlike(obj_v):
                if listlike(v):
                    if obj_v != v:
                        return False
                else:
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
    def get_by_attrs_query2(cls, session, dict={}, accepted_only=True):
        # TODO this should become an attribute on the mapped object so query works normally
        # TODO kwargs are no longer allowed. change any calls that use it.
        base_query = session.query(cls).join(cls.attrs)
        if accepted_only:
            base_query = base_query.filter(_Change.accepted == True)

        filters = []
        for k, v in dict.items():
            filters.append(cls.filter_by_key_value(base_query, k, v))
        if filters:
            objs = filters[0].intersect(*filters[1:])
        else:
            objs = base_query
        return objs

    @classmethod
    def get_by_attrs2(cls, session, dict={}, accepted_only=True):
        """Return _AttrMgr whose _Attrs values match the given dictionary.

        accepted_only -- (bool) limits the returned _AttrMgrs to ones whose were
            accepted.

        """
        #value_key -- (str) an additional key to be appended to the value key.
        #    This is useful for querying on sub-objects in the _Attr value e.g.
        #    requiring a specific value for a specific element of the _Attr value
        #    array.
        objs = cls.get_by_attrs_query2(session, dict, accepted_only)
        objs = objs.all()
        return filter(
            lambda o: cls._get_by_attrs_true_match2(
                o, dict, accepted_only), objs)

    @classmethod
    @deprecated('Use get_by_attrs2 and remove kwargs')
    def get_by_attrs(cls, d={}, value_key=None, accepted_only=True, **kwargs):
        """Gets all objects that have _Attrs that match all the requested
        key-value pairs.

        Values may be regular expression objects as compiled by `re`.

        Arguments:

        accepted_only -- (bool) requires that Objs retrieved must be accepted

        """
        return []
        #map = d
        #if not map:
        #    map = kwargs

        #if not map:
        #    raise ValueError("No filters specified. Did you mean get_all()?")
        #

        #query = [cls._get_by_attrs_query(k, v, value_key) 
        #         for k, v in map.items()]

        #len_query = len(query)
        #try:
        #    objs_attrs = _Attr._mongo_collection().group(
        #        ['obj'],
        #        {'$or': query},
        #        {'a': 0}, 
        #        'function (x, o) { o.a++; }')
        #except IOError:
        #    return []

        ## Filter the matched ids for the correct number of matched attrs
        #obj_ids = [oa['obj'] for oa in objs_attrs if oa['a'] >= len_query]
        #objs = cls.get_all_by_ids(obj_ids)

        #return filter(
        #    lambda o: cls._get_by_attrs_true_match(
        #        o, value_key, accepted_only, **map), objs)


class Obj(_Change, _AttrMgr):
    """Base object for all tracked objects in the system.

    Objs may have two types of attributes:
    1. system attributes (Keys) - written directly into the object
    2. tracked attributes (_Attrs) - written as _Attrs which are
        _Changes themselves. These should only be edited using the provided
        accessors/mutators.

    """
    __tablename__ = 'objs'
    id = Column(ForeignKey('changes.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'obj',
    }

    @hybrid_property
    def uid(self):
        return self.id

    @property
    def mtime(self):
        creation_time = super(Obj, self).ctime
        accepted = self.accepted_tracked()
        if not accepted:
            return creation_time
        last_attr_creation_time = accepted[0].creation_timestamp
        try:
            return max(creation_time, last_attr_creation_time)
        except TypeError:
            return creation_time

    @classmethod
    def all_by_ids(cls, session, ids):
        return session.query(cls).filter(cls.id.in_(ids)).all()

    def to_nice_dict(self):
        """ Returns a dict representation of the Obj.

            This ends up being used to present JSON.

        """
        return {
            'id': self.id,
            'obj_type': self.__class__.__name__,
        }

    def __unicode__(self):
        d = {}
        for col in self.__class__.__table__.columns:
            d[col.name] = self.__getattribute__(col.name)
        kws = ', '.join(['='.join(map(unicode, x)) for x in d.items()])
        return u'%s(%s)' % (type(self).__name__, kws)


@event.listens_for(Obj, 'after_insert')
@event.listens_for(Obj, 'after_update')
def _saved_obj(mapper, connection, target):
    triggers.saved_obj(target)


@event.listens_for(Obj, 'after_delete')
def _deleted_obj(mapper, connection, target):
    triggers.deleted_obj(target)


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

    def __len__(self):
        return sum(len(x) for x in self.values())

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
    __tablename__ = 'cruises'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'cruise',
    }

    #def __getattr__(self, key):
    #    """ Attempt to get attribute as _Attr or attribute on data model"""
    #    sup_attr = super(Cruise, self).__getattr__
    #    if key in self.allowed_attrs_list:
    #        return self.get(key)
    #    return sup_attr(key)

    @property
    def uid(self):
        expo = self.expocode
        if (not expo or not self.accepted or ' ' in expo or '/' in expo
                or '-' in expo):
            return super(Cruise, self).uid
        return expo

    # TODO perhaps override Obj.find_id to also find by uid to alleviate view
    # code doing the same thing

    @property
    def aliases(self):
        return self.get('aliases', [])

    @property
    def statuses(self):
        return self.get('statuses', [])

    @property
    def preliminary(self):
        """Tell whether the cruise is preliminary for the purposes of displaying
        a warning.

        A cruise may either be completely marked preliminary or preliminary
        attributes may cause it to be considered preliminary as well.

        """
        if self.find_attrs({'key': re.compile('_status$'),
                            'value': 'preliminary'}).count() > 0:
            return True
        return 'preliminary' in self.get('statuses', []) 

    @property
    def collections(self):
        collection_ids = self.get('collections', [])
        return Collection.all_by_ids(object_session(self), collection_ids)

    @property
    def institutions(self):
        """ These are institutions that are directly attached to the cruise.
            Suppose a cruise were to be done by an institution but the PI was
            from a different one.

        """
        institution_ids = self.get('institutions', [])
        return Institution.get_all_by_ids(institution_ids)

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
        return object_session(self).query(Ship).get(
            self.get('ship', None))

    @property
    def country(self):
        return object_session(self).query(Country).get(
            self.get('country', None))

    @property
    def files(self):
        files = {}
        file_types = data_file_descriptions.keys()
        for ft in file_types:
            v = self.get(ft)
            if v:
                files[ft] = v
        return files

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
        return shapely.wkt.loads(str(track.geom_wkb))

    @classmethod
    def filter_geo(cls, fn, cruises):
        return filter(lambda x: fn(x.track), cruises)

    @classmethod
    def get_by_expocode(cls, expocode):
        attrs = sort_by_stamp(_Attr.find({'key': 'expocode',
                                          'accepted': True}))
        # Get Attrs that represent most current key value for objs
        obj_expocodes = {}
        for attr in attrs:
            obj_id = attr['obj']
            if obj_id not in obj_expocodes:
                obj_expocodes[obj_id] = attr['value']
        # Don't return a cruise if the current value of expocode isn't
        obj_ids = [o for o, e in obj_expocodes.items() if e == expocode]

        # 1. Multiple cruises might have the same expocode
        return Cruise.get_all_by_ids(obj_ids)

    @classmethod
    def updated(cls, session, limit):
        file_types = data_file_descriptions.keys()

        skip = 0
        step = limit * 4
        updated = []
        cruises = set()

        while len(updated) < limit:
            attrs = session.query(_Attr).\
                filter(_Attr.accepted==True).\
                filter(_Attr.key.in_(file_types)).\
                order_by(_Attr.judgment_timestamp.desc()).\
                offset(skip).limit(step).all()
            if not attrs:
                break
            for attr in attrs:
                cruise = attr.obj
                if cruise not in cruises:
                    cruises.add(cruise)
                    updated.append(attr)
                if len(updated) >= limit:
                    break
            skip += step
        return updated

    @classmethod
    def pending_with_date_starts(cls, session):
        """Gives a list of all pending cruises that have start dates"""
        pending = session.query(Cruise).filter(Cruise.accepted==False).all()
        return filter(lambda c: c.date_start, pending)

    @classmethod
    def upcoming(cls, session, limit):
        upcoming = Cruise.pending_with_date_starts(session)
        now = datetime.utcnow()
        try:
            upcoming = sorted(upcoming, key=lambda c: c.date_start)
        except TypeError:
            upcoming = []

        # strip Seahunt cruises that are in the past
        i = 0
        while (len(upcoming) > 0 and
               upcoming[i].date_start and 
               now > upcoming[i].date_start):
            i += 1
        return upcoming[i:i + limit]

    @classmethod
    def pending_years(cls, session):
        """Gives a list of integer years that have pending cruises."""
        pending_with_date_starts = Cruise.pending_with_date_starts(session)
        years = set()
        for cruise in pending_with_date_starts:
            years.add(cruise.date_start.year)
        return list(years)

    @classmethod
    def all_only_accepted(cls, session, accepted=True):
        """Return all that are accepted or not."""
        return session.query(cls).filter(cls.accepted == accepted).all()

    def to_nice_dict(self):
        """ Returns a dict representation of the Cruise.

        """
        rep = super(Cruise, self).to_nice_dict()
        d = {
            'expocode': self.expocode,
            'accepted': self.accepted,
            'link': self.get('link', None),
            'frequency': self.get('frequency', None),
            'date_start': self.date_start,
            'date_end': self.date_end,
            'aliases': self.aliases,
            'ports': self.get('ports', []),
            'collections': [c.to_nice_dict() for c in self.collections],
            'institutions': [i.to_nice_dict() for i in self.institutions],
            'participants': self.get('participants', []),
        }
        if self.ship:
            d['ship'] = self.ship.to_nice_dict()
        if self.country:
            d['country'] = self.country.to_nice_dict()
        rep.update(d)
        return rep

# TODO move this into the class definition so it only gets called once even if
# the module is reimported
Cruise.allow_attr('expocode', Text, 'ExpoCode')
Cruise.allow_attr('link', Text, 'Expedition Link')
Cruise.allow_attr('frequency', Text)

Cruise.allow_attr('date_start', DateTime, 'Start Date')
Cruise.allow_attr('date_end', DateTime, 'End Date')

Cruise.allow_attr('aliases', TextList)
Cruise.allow_attr('ports', TextList)

Cruise.allow_attr('ship', ID)
Cruise.allow_attr('country', ID)

Cruise.allow_attr('collections', IDList)
Cruise.allow_attr('institutions', IDList)

Cruise.allow_attr('track', LineString)

# array of dicts
Cruise.allow_attr('participants', String)

Cruise.allow_attr('import_id', ID, 'Import ID')

for key, name in data_file_human_names.items():
    Cruise.allow_attr(key, File, name)
    Cruise.allow_attr('{}_status'.format(key), TextList)


class CruiseAssociate(Obj):
    """Provide a way to get the cruises that an Obj is associated to."""
    __tablename__ = 'cruise_associates'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'cruise_associate',
    }

    # Cruise associate key is the _Attr key of Cruise on which the
    # CruiseAssociate ids are stored.
    cruise_associate_key = ''

    def cruises(self, value_key=None, limit=0, accepted_only=True):
        session = object_session(self)
        query = Cruise.get_by_attrs_query2(
            session, {self.cruise_associate_key: self.id}, accepted_only)
        return query.all()


class CruiseParticipantAssociate(CruiseAssociate):
    """ Provide a way to get the cruises that an Participant attribute is
        associated to

        These are people or institutions.

    """
    __tablename__ = 'cruise_participant_associates'
    id = Column(ForeignKey('cruise_associates.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'cruise_participant_associate',
    }
    cruise_associate_key = 'participants'
    cruise_participant_associate_key = None

    def cruises(self):
        return super(CruiseParticipantAssociate, self).cruises(
            self.cruise_participant_associate_key)


class Country(CruiseAssociate):
    __tablename__ = 'countries'
    id = Column(ForeignKey('cruise_associates.id'), primary_key=True)

    iso_3166_1 = Column(Unicode, key='name')
    iso_3166_1_alpha_2 = Column(String(2), key='iso_code_2')
    iso_3166_1_alpha_3 = Column(String(3), key='iso_code_3')

    __mapper_args__ = {
        'polymorphic_identity': 'country',
    }

    cruise_associate_key = 'country'

    @property
    def people(self):
        return Person.get_all({'country': self.id})

    def __unicode__(self):
        try:
            return u'Country ("{name}", {id})'.format(
                name=self.name, id=self.id)
        except AttributeError:
            return u'Country ()'

    def to_nice_dict(self):
        """ Returns a dict representation of the Country.

        """
        rep = super(Country, self).to_nice_dict()
        rep.update({
            'name': self.name,
            'iso_3166-1_alpha-2': self.iso_code(),
            'iso_3166-1_alpha-3': self.iso_code(3),
            'people': [p.to_nice_dict() for p in self.people],
        })
        return rep


class _PersonPermissions(Base):
    """Permissions associated with a Person."""
    __tablename__ = 'person_permissions'
    person_id = Column(ForeignKey('people.id'), primary_key=True)
    permission = Column(Unicode, primary_key=True)

    def __init__(self, permission):
        self.permission = permission


class Person(CruiseParticipantAssociate):
    """A Person in this system.

    People may be either verified or not. If they are associated with an ID
    provider then they are verified.

    """
    __tablename__ = 'people'
    id = Column(
        ForeignKey(
            'cruise_participant_associates.id', use_alter=True,
            name='cruise_participant_associate_person'),
        primary_key=True)

    identifier = Column(String)
    name = Column(String)
    institution = Column(ForeignKey('institutions.id'))
    country = Column(ForeignKey('countries.id'))
    email = Column(String)
    permissions_ = relationship(
        _PersonPermissions, single_parent=True,
        cascade='all, delete, delete-orphan')
    permissions = association_proxy('permissions_', 'permission')

    cruise_participant_associate_key = 'person'

    __mapper_args__ = {
        'polymorphic_identity': 'person',
    }

    def __init__(self, *args, **kwargs):
        super(Person, self).__init__(self, *args, **kwargs)
        if self.identifier is None and self.name is None:
            raise ValueError(
                'Person must be initialized with either identifier or names.')

    @hybrid_property
    def full_name(self):
        return self.name

    def is_verified(self):
        return self.identifier is not None

    def is_authorized(self, perms):
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

    @property
    def institution(self):
        return Institution.get_id(self.institution_)

    @property
    def country(self):
        return object_session(self).query(Country).get(
            self.get('country', None))

    def __unicode__(self):
        return u'Person(identifier={}, name={})'.format(
            self.identifier, self.name)

    def to_nice_dict(self):
        """ Returns a dict representation of the Person.

        """
        rep = super(Person, self).to_nice_dict()
        rep.update({
            'identifier': self.get('identifier', None),
            'name': self.name,
            'email': self.email,
        })
        return rep

@event.listens_for(Person, 'after_insert')
def _insert_person_creation_person_id(mapper, connection, target):
    """Update the Person's creation_stamp.

    """
    target._set_creation_stamp(target)

Person.allow_attr('title', Text)
Person.allow_attr('job_title', Text)
Person.allow_attr('phone', Text)
Person.allow_attr('fax', Text)
Person.allow_attr('address', Text)

Person.allow_attr('programs', IDList)

class MultiNameObj(Obj):
    """ MultiNameObjs have multiple possible names

        The first stored name is taken as the default.

        TODO perhaps Institutions and Ships may also have multiple names. For
        now let them have just one canonical name.

    """
    __tablename__ = 'multi_name_objs'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'multi_name_obj',
    }

    @property
    def names(self):
        names = list(self.get('names', []))
        return names

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
    __tablename__ = 'institutions'
    id = Column(ForeignKey('cruise_participant_associates.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'institution',
    }

    cruise_participant_associate_key = 'institution'

    @property
    def name(self):
        return self.get('name', None)

    def people(self):
        return Person.get_all({'institution': self.id})

    @property
    def country(self):
        country = self.get('country', None)
        if country:
            return Country.get_id(country)
        return None

    def __unicode__(self):
        try:
            return u'Institution ({name})'.format(name=self.name)
        except AttributeError:
            return u'Institution ()'

    def to_nice_dict(self):
        """ Returns a dict representation of the Institution.

        """
        rep = super(Institution, self).to_nice_dict()
        d = {
            'name': self.name,
        }
        if self.country:
            d['country'] = self.country.to_nice_dict()
        rep.update(d)
        return rep

Institution.allow_attr('name', Text)
Institution.allow_attr('phone', Text)
Institution.allow_attr('address', Text)
Institution.allow_attr('url', Text, 'Link')

Institution.allow_attr('country', ID)


class Ship(CruiseAssociate):
    __tablename__ = 'ships'
    id = Column(ForeignKey('cruise_associates.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'ship',
    }

    cruise_associate_key = 'ship'

    @property
    def name(self):
        return self.get('name', None)

    @property
    def nodc_platform_code(self):
        return self.get('nodc_platform_code', None)

    def __unicode__(self):
        return u'Ship(%s)' % self.name

    def to_nice_dict(self):
        """ Returns a dict representation of the Ship.

        """
        rep = super(Ship, self).to_nice_dict()
        rep.update({
            'name': self.name,
            'nodc_platform_code': self.nodc_platform_code,
            'url': self.get('url', ''),
        })
        return rep

Ship.allow_attr('name', Text)
Ship.allow_attr('nodc_platform_code', String, 'NODC Platform Code')
Ship.allow_attr('url', Text, 'Link')

Ship.allow_attr('country', ID)


class Collection(CruiseAssociate, MultiNameObj):
    """Essentially tags for Cruises.
    
    A Cruise may belong to Basin Collection, WOCE line Collection, etc.
        
    A Collection will also include a type as part of its identifier to
    differentiate between the fields it came from in the original database.

    Attributes:
    names - names associated with the collection. The first name in the list is
        the canonical name.
    type - identifier of WOCE line, group, program, basin
    basins - a list of any combination of atlantic, arctic, pacific,
        indian, southern. Having this attribute designates the collection as
        a spatial_group.
    
    """
    __tablename__ = 'collections'
    id = Column(ForeignKey('cruise_associates.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'collection',
    }

    cruise_associate_key = 'collections'

    @classmethod
    def get_all_by_name(cls, name):
        """ Returns all collections that match the given name

            Parameters:
                name - either a string or a regular expression object
        
        """
        return self.get_by_attrs(names=name)

    @property
    def type(self):
        return self.get('type', None)

    @property
    def basins(self):
        return self.get('basins', [])

    @classmethod
    def get_by_name(cls, name):
        return cls.get_by_attrs({'names': name}, value_key='0')

    def merge_(self, mergee, signer):
        """Merge two Collections together."""
        names = uniquify(self.names + mergee.names)
        self.set_accept('names', names, signer)
        if self.type is None and mergee.type is not None:
            self.set_accept('type', mergee.type, signer)
        cruises = set(
            self.cruises(accepted_only=False)).union(
                mergee.cruises(accepted_only=False))
        for cruise in cruises:
            colls = cruise.collections
            try:
                colls.remove(mergee)
            except ValueError:
                pass
            try:
                colls.index(self)
            except ValueError:
                colls.append(self)
            cruise.set_accept(self.cruise_associate_key,
                              [c.id for c in colls], signer)

        basins = uniquify(list(self.get('basins', [])) + \
                          list(mergee.get('basins', [])))
        if basins:
            self.set_accept('basins', basins, signer)
        object_session(self).delete(mergee)

    # TODO this should be pulled up to at least CruiseAssociate level. This
    # requires merge_ to be implemented
    def merge(self, signer, *mergees):
        """Merge this Collection with other collections."""
        if not issubclass(type(signer), Person):
            raise TypeError('Signer is not a Person')
        if not all(issubclass(type(m), self.__class__) for m in mergees):
            raise TypeError('Not all mergees are %s' % self.__class__)
        for mergee in mergees:
            self.merge_(mergee, signer)

    @classmethod
    def merge_same(cls, signer):
        """Merge all collections that are the same together.

        TODO This function should be moved to the importers.

        """
        # Pass 1: same name and same type
        sames = {}
        colls = cls.get_all()
        for coll in colls:
            key = '|'.join([''.join(filter(None, coll.names)), coll.type or ''])
            try:
                sames[key].append(coll)
            except KeyError:
                sames[key] = [coll]
        for same in sames.values():
            if len(same) < 2:
                continue
            same[0].merge(signer, *same[1:])

        # Pass 2: same name and similar types
        sames = {}
        colls = cls.get_all()
        for coll in colls:
            key = ''.join(filter(None, coll.names))
            try:
                sames[key].append(coll)
            except KeyError:
                sames[key] = [coll]
        for same in sames.values():
            if len(same) < 2:
                continue

            types = {}
            for s in same:
                key = s.type or ''
                try:
                    types[key].append(s)
                except KeyError:
                    types[key] = [s]

            if '' in types:
                s = types['']
                if 'group' in types:
                    g = types['group'][0]
                    g.merge(signer, *s)
                elif 'program' in types:
                    p = types['program'][0]
                    p.merge(signer, *s)
                elif 'WOCE line' in types:
                    w = types['WOCE line'][0]
                    w.merge(signer, *s)
            if 'group' in types:
                g = types['group']
                if 'WOCE line' in types:
                    w = types['WOCE line'][0]
                    w.merge(signer, *g)
                elif 'program' in types:
                    p = types['program'][0]
                    p.merge(signer, *g)
            if 'spatial_group' in types:
                s = types['spatial_group']
                if 'WOCE line' in types:
                    w = types['WOCE line'][0]
                    w.merge(signer, *s)

    def to_nice_dict(self):
        """ Returns a dict representation of the Collection.

        """
        rep = super(Collection, self).to_nice_dict()
        rep.update({
            'names': self.names,
            'type': self.type,
            'basins': self.basins,
        })
        return rep

Collection.allow_attr('type', Text)
Collection.allow_attr('basins', TextList)
Collection.allow_attr('names', TextList)


class AutoAcceptingObj(Obj):
    """ When AutoAcceptingObjs are saved, they are also accepted using the
    creator as the signer, obviating the step of accepting known good changes.

    """
    def save(self):
        super(AutoAcceptingObj, self).save()
        if not self.judgment_stamp:
            self.accept(self.creation_stamp.person_id)


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

        Attributes:
        text_identifier - some text that makes the file quickly identifiable to
                          a human
        file - either an id that is the file in the filesystem or a tuple like
               (id, attribute) that describes which attr of which obj holds the
               file.
        description
        display - whether or not the file is meant to be visible

    """
    __tablename__ = 'argo_files'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    text_identifier = Column(Unicode)
    description = Column(Unicode)
    display = Column(Boolean)

    file_id = Column(String)
    file = composite(FileComposite, file_id)

    __mapper_args__ = {
        'polymorphic_identity': 'argo_file',
    }

    def __init__(self, person):
        super(ArgoFile, self).__init__(person)
        self.text_identifier = None
        self.file = None
        self.description = None
        self.display = None

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
    __tablename__ = 'old_submissions'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    date = Column(DateTime)
    stamp = Column(String(6))
    submitter = Column(Unicode)
    line = Column(Unicode)
    folder = Column(Integer(13))
    files = Column(String) # TODO array of file ids

    __mapper_args__ = {
        'polymorphic_identity': 'old_submission',
    }

    def remove(self):
        for file in self.files_:
            fs().delete(file)
        super(OldSubmission, self).remove()


class Submission(Obj):
    """ A Submission to the CCHDO. These interface with humans so they need
        intervention to make everything behaves nicely before going into the
        system.

        Attributes:
        expocode
        ship_name
        line
        action
        type - the type of submission {public, non-public, argo}
        cruise_date - the date of the cruise being submitted TODO not used?
        file - the file that is being suggested
        attached - an _Attr id.
            When this is set, the submission has been looked at by a human and
            the corresponding _Attr represents verified information representing
            this submission.

            SPECIAL CASE: This is set to True during legacy import because there
            is no way to determine it without human help.

    """
    __tablename__ = 'submissions'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    expocode = Column(Unicode)
    ship_name = Column(Unicode)
    line = Column(Unicode)
    action = Column(Unicode)
    type = Column(Unicode)
    attached_id = Column(ForeignKey('attrs.id'))
    attached = relationship('_Attr')

    file_id = Column(String)
    file = composite(FileComposite, file_id)

    __mapper_args__ = {
        'polymorphic_identity': 'submission',
    }

    @property
    def identifier(self):
        return self.expocode_

    def cruises_from_identifier(self):
        try:
            cruises = Cruise.get_by_attrs(expocode=self.expocode)
        except AttributeError:
            return []
        if len(cruises) > 0:
            return cruises
        return []

    @property
    def attached(self):
        """ Whether the submission has been attached.
            
            Gives either
            1. the _Attr that the submission is attached to
            OR
            2. True if the submission was imported and attached already. This is
               because no assumptions are made by the importer as to what cruise
               the submission is really attached to.

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
    __tablename__ = 'parameters'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'parameter',
    }
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
    __tablename__ = 'units'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'unit',
    }
    pass


class ParameterOrder(Obj):
    """ Defines the class that a Parameter of which it is a member.

    Attributes:
    name - the class
    order - the list of parameters in the order they should appear

    """
    __tablename__ = 'parameter_orders'
    id = Column(ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'parameter_order',
    }
    @property
    def order(self):
        order = self.get('order')
        return [Parameter.get_id(id) for id in order]
