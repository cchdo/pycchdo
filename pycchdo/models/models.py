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
    Integer, Boolean, Enum, String, Unicode, DateTime, TIMESTAMP, DECIMAL,
    )
import sqlalchemy.sql.util
from sqlalchemy.sql import (
    and_, not_,
    case, select, exists,
    )
from sqlalchemy.schema import Index
from sqlalchemy.orm import (
    backref,
    scoped_session,
    sessionmaker,
    composite,
    relationship,
    object_session,
    reconstructor, 
    mapper,
    )
from sqlalchemy.orm.collections import (
    collection, attribute_mapped_collection,
    )
from sqlalchemy.ext.associationproxy import (
    association_proxy, AssociationProxy, _AssociationList)
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from sqlalchemy.ext.mutable import MutableComposite
from sqlalchemy.ext.declarative import (
    declarative_base,
    declared_attr, 
    )

from zope.sqlalchemy import ZopeTransactionExtension

from geoalchemy import (
    GeometryColumn, 
    LineString,
    GeometryDDL, 
    )

import shapely.wkb
import shapely.wkt
import shapely.geometry

import geojson

from libcchdo.fns import uniquify

from pycchdo.util import (
    flatten,
    str2uni,
    FileProxyMixin,
    is_valid_ip, 
    deprecated,
    _sorted_tables,
    )
import triggers as triggers
from pycchdo.log import ColoredLogger


log = ColoredLogger(__name__)


__all__ = [
    'data_file_human_names',
    'data_file_descriptions',
    'reset_database', 'Session', 'DBSession', 'Base',
    'Stamp',
    'Note',
    'FSFile',
    'RequestFor',
    'RequestForAttr',
    'Participants',
    'Participant',
    'ParameterInformation', 
    'Obj',
    'Person',
    'Cruise',
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


Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)


Base = declarative_base()


def reset_database(engine):
    """Clears the database and recreates schema."""
    meta = Base.metadata
    tables = meta.sorted_tables
    meta.drop_all(bind=engine, tables=tables)
    meta.create_all(engine)


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
            raise ValueError(
                'Stamp must have a Person with timestamp {}'.format(timestamp))

    def __composite_values__(self):
        return [self.person_id, self.timestamp, ]

    def __setattr__(self, key, value):
        """Intercept set events and alert parents to change."""
        object.__setattr__(self, key, value)
        self.changed()

    def __eq__(self, other):
        if type(other) is not Stamp:
            return False
        return (
            self.person_id == other.person_id and 
            self.timestamp == other.timestamp)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __not__(self):
        return self.person_id is None and self.timestamp is None

    def __unicode__(self):
        if not self:
            return u'Stamp(empty)'
        return u"Stamp(%s, %s)" % (
            self.person_id, self.timestamp.strftime('%FT%T'))

    def __repr__(self):
        return unicode(self)


class StampedCreation(object):
    """Mixin to store the creation time and person."""
#    @declared_attr
#    def creation_timestamp(cls):
#        return Column(DateTime, default=timestamp_now)
#
#    @declared_attr
#    def creation_person_id(cls):
#        return Column(Integer, ForeignKey('people.id'))
#
#    @declared_attr
#    def creation_stamp(cls):
#        return composite(Stamp, cls.creation_person_id, cls.creation_timestamp)
#
#    @declared_attr
#    def creation_person(cls):
#        return relationship(
#            'Person', primaryjoin="Note.creation_person_id==Person.id")

    @hybrid_property
    def ctime(cls):
        return cls.creation_timestamp


class StampedModeration(object):
    """Mixin to store the pending and judgment time and person."""
    pass


class Notable(object):
    """Mixin to store notes."""
    @declared_attr
    def notes(cls):
        if cls.__name__ == 'Person':
            fk = Note.person_id
        else:
            fk = Note.change_id
        return relationship(
            'Note', primaryjoin=fk == cls.id, lazy='dynamic',
            cascade='all, delete, delete-orphan')

    @declared_attr
    def notes_public(cls):
        if cls.__name__ == 'Person':
            fk = Note.person_id
        else:
            fk = Note.change_id
        return relationship(
            'Note', viewonly=True,
            primaryjoin=and_(fk == cls.id, not_(Note.discussion)))

    @declared_attr
    def notes_discussion(cls):
        if cls.__name__ == 'Person':
            fk = Note.person_id
        else:
            fk = Note.change_id
        return relationship(
            'Note', viewonly=True,
            primaryjoin=and_(fk == cls.id, Note.discussion))

    @deprecated('Use _Change.notes.append(note)')
    def add_note(self, note):
        self.notes.append(note)

    @deprecated('Use _Change.notes.remove(note)')
    def remove_note(self, note):
        self.notes.remove(note)


class Note(StampedCreation, Base):
    """A Note that can be attached to any _Change.

    A _Change may have many Notes.

    Attrs:
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
    creation_person_id = Column(Integer, ForeignKey('people.id'))
    creation_stamp = composite(Stamp, creation_person_id, creation_timestamp)

    body = Column(Unicode)
    action = Column(Unicode)
    data_type = Column(Unicode)
    subject = Column(Unicode)
    discussion = Column(Boolean)

    change_id = Column(Integer, ForeignKey('changes.id'))

    import_id = Column(String)

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


class _Change(StampedCreation, StampedModeration, Notable, Base):
    """A Change to the dataset that should be recorded along with the time and
    person who changed it.

    Changes may be accepted or rejected. Changes may also have attached notes
    which may be individually public or for dicussion purposes only.

    """
    __tablename__ = 'changes'
    id = Column(Integer, primary_key=True)
    obj_type = Column(String, nullable=False)

    creation_timestamp = Column(DateTime, default=timestamp_now)
    creation_person_id = Column(Integer, ForeignKey('people.id'))
    creation_stamp = composite(Stamp, creation_person_id, creation_timestamp)

    __mapper_args__ = {
        'polymorphic_on': obj_type,
        'polymorphic_identity': 'change',
        }

    __table_args__ = (
        Index('idx_changes_judgment_timestamp', 'judgment_timestamp'),
        Index('idx_changes_obj_type', 'obj_type'),
        )

    def __init__(self, person, note=None, *args, **kwargs):
        super(_Change, self).__init__(*args, **kwargs)
        self.creation_stamp = Stamp(person.id)
        if note:
            self.notes.append(note)

    def __repr__(self):
        return u'{}({})'.format(type(self).__name__, self.id)

    # Moderation attributes

    pending_timestamp = Column(DateTime)
    pending_person_id = Column(Integer, ForeignKey('people.id'))
    pending_stamp = composite(
        Stamp, pending_person_id, pending_timestamp)
    #pending_person = return relationship(
    #    'Person', primaryjoin="Note.pending_person_id==Person.id")

    judgment_timestamp = Column(DateTime)
    judgment_person_id = Column(Integer, ForeignKey('people.id'))
    judgment_stamp = composite(
        Stamp, judgment_person_id, judgment_timestamp)
    #judgment_person = relationship(
    #    'Person', primaryjoin="Note.judgment_person_id==Person.id")

    accepted = Column(Boolean, default=False)

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
        self.pending_stamp = Stamp(person.id)

    def reject(self, person):
        self.judgment_stamp = Stamp(person.id)
        self.accepted = False


class RequestFor(Base):
    """Information about HTTP request of another object."""
    __tablename__ = 'requests_for'

    id = Column(Integer, primary_key=True)

    dt = Column(DateTime)
    ua = Column(String)
    ip = Column(String)
    type = Column(String)

    def __init__(self, request):
        """Takes a webob.Request and stores relevant information related to
        tracking.

        Parameters:
            request - the webob.Request

        """
        try:
            self.dt = request.date
            self.ua = request.user_agent
            self.ip = request.remote_addr
            if not type(self.dt) is datetime:
                raise ValueError()
            if not is_valid_ip(self.ip):
                raise ValueError()
        except (AttributeError, ValueError):
            pass
        try:
            self.date = request.date
        except AttributeError:
            pass

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'request_for',
    }


class RequestForAttr(RequestFor):
    __tablename__ = 'requests_for_attrs'

    id = Column(Integer, ForeignKey('requests_for.id'), primary_key=True)
    attr_id = Column(Integer, ForeignKey('attrs.id'))

    __mapper_args__ = {
        'polymorphic_identity': 'request_for_attr',
    }


class FSFile(Base, FileProxyMixin):
    """A file record that points to the filesystem file."""
    __tablename__ = 'fsfile'

    id = Column(Integer, primary_key=True)
    fsid = Column(Unicode)
    name = Column(Unicode)
    content_type = Column(String)
    upload_date = Column(TIMESTAMP)

    # Stores information used by pycchdo.importer.cchdo to correlate ArgoFiles
    # with Documents.
    import_id = Column(Unicode)
    import_path = Column(Unicode)

    _fs = None

    def __init__(self, file=None, filename=None, contentType=None):
        if file:
            self.file = DjangoFile(file)
        self.name = filename
        self.content_type = contentType

    size = property(lambda self: self.file.size)

    @property
    def fs(self):
        cls = type(self)
        if not cls._fs:
            cls.reconfig_fs_storage()
        return cls._fs
    
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

    @staticmethod
    def from_fieldstorage(fs):
        file = fs.file
        filename = fs.filename
        content_type = fs.type
        fsfile = FSFile(file, filename, content_type)

        # Call size while file is still in scope to cache size
        fsfile.size
        return fsfile


@event.listens_for(FSFile, 'before_insert')
def _saved_file(mapper, connection, target):
    target.fsid = target.fs.save(target.fs.get_available_name(''), target.file)


@event.listens_for(FSFile, 'load')
def _loaded_file(target, context):
    target.file = target.fs.open(target.fsid)


@event.listens_for(FSFile, 'before_delete')
def _deleted_file(mapper, connection, target):
    target.fs.delete(target.fsid)


# Types for database storage
class ID(Integer):
    pass


class IDList(TypeEngine):
    pass


class TextList(TypeEngine):
    pass


class DecimalList(TypeEngine):
    pass


class File(TypeEngine):
    pass


class _Participants(TypeEngine):
    pass


class ParameterInformations(TypeEngine):
    pass


class _AttrValue(Base):
    """A value stored by _Attr.

    Meant to be abstract but has a concrete table because it contains the
    reference to the _Attr that helps with polymorphic querying.

    """
    id = Column(Integer, primary_key=True)
    type = Column(String)

    accepted = Column(Boolean, default=False)
    attr_id = Column(Integer, ForeignKey('attrs.id'))

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
        return u'{}.{}'.format(cls.__name__, 'value')

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


class _AttrValueInteger(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Integer)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        try:
            int(value)
        except Exception:
            raise ValueError('{} is not coerceable to int'.format(value))

event.listen(_AttrValueInteger.value, 'set', _AttrValueInteger.test_type)


class _AttrValueBoolean(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Boolean)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        try:
            bool(value)
        except Exception:
            raise ValueError('{} is not coerceable to bool'.format(value))

event.listen(_AttrValueBoolean.value, 'set', _AttrValueBoolean.test_type)


class _AttrValueUnicode(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(Unicode)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        if type(value) is datetime:
            raise ValueError('{} is not a string'.format(value))
        try:
            return unicode(value)
        except Exception:
            raise ValueError('{} is not coerceable to unicode'.format(value))

event.listen(
    _AttrValueUnicode.value, 'set', _AttrValueUnicode.test_type, retval=True)


class _AttrValueDatetime(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = Column(DateTime)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        if type(value) is not datetime:
            raise ValueError('{} is not a datetime'.format(value))

event.listen(_AttrValueDatetime.value, 'set', _AttrValueDatetime.test_type)


class _AttrValueLineString(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = GeometryColumn(LineString(2, spatial_index=False))

    def _verify_and_normalize_linestring(self, value):
        """Convert value into a Shapely LineString."""
        if type(value) is shapely.geometry.linestring.LineString:
            pass
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

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        try:
            shapely.wkt.loads(value)
        except Exception:
            raise ValueError('{} is not a WKT LineString'.format(value))

event.listen(_AttrValueLineString.value, 'set', _AttrValueLineString.test_type)

GeometryDDL(_AttrValueLineString.__table__)


class _AttrValueFile(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value_ = Column('value', ForeignKey('fsfile.id'))
    value = relationship(
        'FSFile', primaryjoin='FSFile.id == _AttrValueFile.value_',
        backref='av')

    def __init__(self, value):
        self.value = FSFile(value.file, value.filename)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        if type(value) is not FSFile:
            raise ValueError('{} is not an FSFile'.format(value))

event.listen(_AttrValueFile.value, 'set', _AttrValueFile.test_type)


class Participant(Base):
    """A participant consisting of role, person, and possibly institution."""
    __tablename__ = 'participants'
    attrvalue_id = Column(
        Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    role = Column(Unicode, nullable=False, primary_key=True)
    person_id = Column(
        ForeignKey('people.id'), nullable=False, primary_key=True)
    person = relationship('Person')
    institution_id = Column(Integer, ForeignKey('institutions.id'))
    institution = relationship('Institution')

    def __init__(self, role, person, institution=None):
        self.role = role
        self.person_id = person.id
        if institution:
            self.institution_id = institution.id
    
    def __eq__(self, other):
        if (    hash(self) == hash(other) and
                self.institution_id == other.institution_id):
            return True
        return False

    def __hash__(self):
        return hash(u'{}_{}_{}'.format(
            self.attrvalue_id, self.role, self.person_id))

    def __repr__(self):
        return u'Participant({}, {}, {})'.format(
            self.role, self.person_id, self.institution_id)
        

class Participants(object):
    """A list of Participants.

    All mutators will suggest a new value for 'participants' and return the
    suggestion.

    This collection will also provide Person-Institution paris when queried with
    a role.

    Participants presents a dictionary-like interface roles.
    
    """
    def __init__(self, *args, **kwargs):
        if args:
            p = args[0]
            if type(p) is Participants:
                self.data = p.data
            else:
                self.data = p
        else:
            self.data = []

    @collection.appender
    def _append(self, participant):
        """Adds a participant to the map under the given role."""
        self.data.append(participant)

    def _clear(self):
        self.data = []

    @collection.remover
    def _remove(self, participant):
        """Removes a participant from the map under the given role."""
        self.data.remove(participant)

    @collection.iterator
    def __iter__(self):
        return iter(self.data)

    def _extend(self, items):
        return self.data.extend(items)

    def __len__(self):
        return len(self.data)

    def extend(self, cruise, signer, *participants):
        """Return suggestion with participants appended."""
        p = Participants(self)
        p._extend(participants)
        return cruise.set('participants', p, signer)

    def remove(self, cruise, signer, *participants):
        """Return suggestion with participants removed."""
        p = Participants(self)
        for participant in participants:
            p._remove(participant)
        return cruise.set('participants', p, signer)

    def clear(self, cruise, signer):
        """Return suggestion with no participants."""
        p = Participants(self)
        p._clear()
        return cruise.set('participants', p, signer)

    def replace(self, cruise, signer, *participants):
        """Return suggestion with participants replaced."""
        p = Participants(self)
        p._clear()
        p._extend(participants)
        return cruise.set('participants', p, signer)

    def __getitem__(self, role):
        """Return Participants for role."""
        return filter(lambda p: p.role == role, self.data)

    @property
    def roles(self, role=None):
        """Pairs of Persons and roles present in the map."""
        if role is None:
            participants = self.data
        else:
            participants = self[role]
        return [(p.person, p.role) for p in participants]

    def __repr__(self):
        return u'Participants({})'.format(self.data)
        

class _AttrValueParticipants(_AttrValue):
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = relationship(
        'Participant', collection_class=Participants,
        cascade='all, delete, delete-orphan')


class _AttrValueElem(Base):
    """Base for _AttrValueList elements."""
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

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
    attrvalue_id = Column(Integer, ForeignKey('_attrvalue.id'))
    value = Column(ID)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        _AttrValueInteger.test_type(target, value)
        try:
            int(value)
        except Exception:
            raise ValueError('{} is not coerceable to int'.format(value))

event.listen(_AttrValueElemID.value, 'set', _AttrValueElemID.test_type)


class _AttrValueElemText(_AttrValueElem):
    attrvalue_id = Column(Integer, ForeignKey('_attrvalue.id'))
    value = Column(Unicode)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        _AttrValueUnicode.test_type(target, value)

event.listen(_AttrValueElemText.value, 'set', _AttrValueElemText.test_type)


class _AttrValueElemDecimal(_AttrValueElem):
    attrvalue_id = Column(Integer, ForeignKey('_attrvalue.id'))
    value = Column(DECIMAL)

    @staticmethod
    def test_type(target, value, oldvalue=None, initiator=None):
        try:
            float(value)
        except Exception:
            raise ValueError('{} is not coerceable to int'.format(value))

event.listen(_AttrValueElemText.value, 'set', _AttrValueElemText.test_type)


class ParameterInformation(_AttrValueElem):
    """Metadata about a parameter.

    Columns:
        parameter - the parameter
        status - the status of the parameter; one of the following:
            online, reformatted, submitted, not_measured, proposed,
            no_information
        pi - the principal investigator for the parameter on the cruise
        inst - the institution that the pi was operating for
        ts - some date attached to the status and PI of the parameter

    """
    attrvalue_id = Column(Integer, ForeignKey('_attrvalue.id'))

    parameter_id = Column(Integer, ForeignKey('parameters.id'))
    parameter = relationship('Parameter')
    status = Column(
        Enum('online', 'reformatted', 'submitted', 'not_measured', 'proposed',
             'no_information', name='parameter_status'))
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
    
    def __eq__(self, other):
        return (
            self.parameter_id == other.parameter_id and
            self.status == other.status and
            self.pi_id == other.pi_id and
            self.inst_id == other.inst_id and 
            self.ts == other.ts
            )

    def __repr__(self):
        return u'ParameterInformation({}, {}, {}, {}, {})'.format(
            self.parameter_id, self.status, self.pi_id,
            self.inst_id, self.ts)


class _AttrValueList(object):
    # TODO figure out why value must be declared for each list type rather than
    # inherited
    pass


class _AttrValueListID(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemID
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    values = relationship(
        __elem_class__, cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListText(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemText
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    values = relationship(
        __elem_class__, cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListDecimal(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemDecimal
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    values = relationship(
        __elem_class__, cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListParameterInformation(_AttrValueList, _AttrValue):
    __elem_class__ = ParameterInformation
    id = Column(Integer, ForeignKey('_attrvalue.id'), primary_key=True)
    value = relationship(
        __elem_class__, cascade='all, delete, delete-orphan')


@event.listens_for(_AttrValueListID, 'before_delete')
@event.listens_for(_AttrValueListText, 'before_delete')
@event.listens_for(_AttrValueListDecimal, 'before_delete')
@event.listens_for(_AttrValueListParameterInformation, 'before_delete')
def _delete_list_elems_first(mapper, connection, target):
    elemclass = target.__class__.__elem_class__
    delete_stmt = elemclass.__table__.delete(
        elemclass.attrvalue_id == target.id)
    connection.execute(delete_stmt)


class _AttrPermission(Base):
    """Permissions associated with an _Attr.

    Permissions for _Attrs are subdivided into read and write.
    # TODO perms need to store dicts...

    """
    __tablename__ = 'attrs_permissions'
    attr_id = Column(Integer, ForeignKey('attrs.id'), primary_key=True)
    perm_type = Column(
        Enum('read', 'write', name='attr_permission_type'),
        default='read', primary_key=True)
    permission = Column(Unicode, primary_key=True)

    def __init__(self, perm_type, permission):
        self.perm_type = perm_type
        self.permission = permission


#class _AttrValueTransformer(Comparator):
#    def operate(self, op, other):
#        def transform(q):
#            clause = self.__clause_element__()
#            parent_alias = aliased(clause)
#            return q.join(parent_alias, clause.parent).\
#                filter(op(parent_alias.parent, other))
#
#            #return and_(_AttrValue.attr_id == _Attr.id, _AttrValue.accepted == False)
#            #return case([
#            #    (cls.deleted == True, None),
#            #    #(exists(select(cls.v_accepted)), cls.v_accepted),
#            #], else_=cls.v)
#        return transform


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

    id = Column(Integer, ForeignKey('changes.id'), primary_key=True)
    key = Column(Unicode)
    str_type = Column(String)
    deleted = Column(Boolean)

    obj_id = Column(Integer, ForeignKey('objs.id'))
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

    __table_args__ = (
        Index('idx_attrs_obj_type_keys', 'key', 'obj_id', 'str_type'),
        )

    def __init__(self, person, key, attr_type, value=None, note=None,
                 deleted=False):
        """Create an _Attr _Change state.

        Arguments::
        person -- the person who performed the change
        key -- the attribute name that this change is for
        attr_type -- the type of value that this _Attr stores. This
            should be an sqlalchemy type
        
        Keyword arguments::
        value -- the value to store
        note -- a note to add during creation; syntactic sugar
        deleted -- whether this _Attr's new state is deleted. If this is True,
            the _Attr's value is disregarded.

        """
        super(_Attr, self).__init__(person)

        self.key = key
        self._attr_type = attr_type
        self.constructor = _AttrMgr.value_class(self._attr_type)

        self.deleted = deleted
        if not deleted:
            self._set(value)

        if note is not None:
            self.add_note(note)

    @reconstructor
    def reconstructor(self):
        """Reconstruct state on _Attr when loading from database."""
        self.constructor = self.obj.attr_class(self.key)
        attr_type = self.obj.attr_type(self.key)
        if type(attr_type) is list:
            for at in attr_type:
                if _AttrMgr.attr_type_to_str(at) == self.str_type:
                    self._attr_type = at
                    break
        else:
            self._attr_type = attr_type

    def _construct(self, *args, **kwargs):
        constructor = _AttrMgr.value_class(self._attr_type)
        str_type = _AttrMgr.attr_type_to_str(self._attr_type)
        if type(constructor) is not list:
            constructor = [constructor]
        if type(str_type) is not list:
            str_type = [str_type]

        constructor_str_types = zip(constructor, str_type)

        for constructor, str_type in constructor_str_types:
            try:
                v = constructor(*args, **kwargs)
                self.str_type = str_type
                return v
            except ValueError, e:
                log.debug(
                    u'Construct failed for {}: {}'.format(constructor, e))
        raise ValueError(u'No constructors {} for {} matched {}'.format(
            constructor_str_types, self.key, type(kwargs['value'])))

    def _set(self, value, accepted=False):
        """Set the _Attr value.

        Validate and store the value.

        Raises:
            TypeError when value does not match the defined type for the _Attr
        
        Special cases:
        value -- a cgi.FieldStorage-like object
            Attempts to store the file in the filesystem and stores the id in
            the 'file' attribute.
        key -- track
            Stores the value (which must be a GeoJSON linestring coordinate
            list) in the 'track' attribute.  accepted -- whether to set the value for the original or accepted state

        """
        if value is None and self.str_type == 'ID':
            raise ValueError(
                'IDs should not be None. Is the object persisted?')

        cannot_be_stored_error = TypeError(
            u'{} cannot be stored as {}'.format(value, self.constructor))

        try:
            if accepted:
                self.v_accepted = self._construct(
                    value=value, accepted=accepted)
            else:
                self.v = self._construct(value=value)
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
        av = self.attr_value
        if av:
            return av.value
        return None

    @hybrid_property
    def value_original(self):
        """Return the original value of the _Attr."""
        return self.attr_value_original.value

    def __repr__(self):
        try:
            mapping = u'{}, {}'.format(repr(self.key), repr(self.value))
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
            try:
                attr_class = self.person.attr_class(self.key)
            except AttributeError:
                attr_class = '???'

        id = self.id or '?'
        return u"_Attr({}, {}, {}, {}, {})".format(
            mapping, state, self.str_type, attr_class, id)

    @classmethod
    def all_data(cls):
        return object_session(self).query(_Attr).\
            filter(_Attr.str_type == 'File').all()

    @classmethod
    def all_track(cls):
        return object_session(self).query(_Attr).\
            filter(_Attr.str_type == 'LineString').all()

    @classmethod
    def pending(cls):
        return object_session(self).query(_Attr).filter(_Change.judgment_stamp == None).all()


class _AttrMgr(object):
    """Mixin grouping _Attr related functionality.

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
    __allowed_attrs = {}

    @classmethod
    def _attr_type_to_str(cls, attr_type):
        return attr_type.__name__

    @classmethod
    def attr_type_to_str(cls, attr_type):
        if type(attr_type) is list:
            return map(cls._attr_type_to_str, attr_type)
        return cls._attr_type_to_str(attr_type)

    @classmethod
    def _allowed_attrs_dict(cls):
        """Return the allowed attrs dict for this current class."""
        try:
            return cls.__allowed_attrs[cls]
        except KeyError:
            cls.__allowed_attrs[cls] = MultiDict()
        return cls.__allowed_attrs[cls]

    @classmethod
    def _allowed_attrs(cls):
        """Return the allowed attrs for this class based on polymorphism."""
        allowed_attrs = cls._allowed_attrs_dict()
        for c in cls.__bases__:
            if issubclass(c, _AttrMgr):
                allowed_attrs.update(c._allowed_attrs())
        return allowed_attrs

    @classmethod
    def _update_allowed_attrs_caches(cls):
        """Update the attr caches.

        These include allowed_attrs, allowed_attrs_list, and
        allowed_attrs_human_names. These are convenience attributes that should
        be replaced with function calls.
        TODO replace allowed_attrs, allowed_attrs_list, and
        allowed_attrs_human_names with functions.

        """
        attrs = cls._allowed_attrs()

        d = MultiDict()
        for key, attr in attrs.items():
            str_type = cls.attr_type_to_str(attr['type'])
            if type(str_type) is list and len(str_type) > 0:
                str_type = str_type[0]
            try:
                d[str_type].append(key)
            except KeyError:
                d[str_type] = [key]
        cls.allowed_attrs = d
        cls.allowed_attrs_list = attrs.keys()

        d = {}
        for key, attr in attrs.items():
            d[key] = attr['name']
        cls.allowed_attrs_human_names = d
        
    @classmethod
    def allow_attr(cls, key, attr_type, name=None, batch=False):
        """Add an _Attr definition to the list of allowed keys.

        Arguments:
        key -- (str)
        type -- (sqlalchemy type) the type of data that can be stored for key
        name -- (str) name of this key for humans (default: capitalized words
            with underscores converted to spaces)

        """
        attrs = cls._allowed_attrs_dict()

        if not name:
            name = capwords(key.replace('_', ' '))
        d = {'type': attr_type, 'name': name}
        try:
            if d != attrs[key]:
                raise TypeError(u'{} already allowed for {} as {}. Clobbering '
                    'with {} will cause unexpected behavior.'.format(
                    key, cls, attrs[key], d))
        except KeyError:
            pass
        attrs[key] = d
        if not batch:
            cls._update_allowed_attrs_caches()

    @classmethod
    def allow_attrs(cls, list):
        """Add _Attr definitions to the list of allowed keys."""
        for definition in list:
            cls.allow_attr(*definition, batch=True)
        cls._update_allowed_attrs_caches()

    @classmethod
    def attr_type(cls, key):
        """Return the type of data allowed for key."""
        attrs = cls._allowed_attrs()
        try:
            return attrs[key]['type']
        except KeyError:
            raise ValueError(u'key {} is not allowed for {}'.format(key, cls))

    @classmethod
    def _value_class(cls, type):
        """Get the _AttrValue class corresponding to the type."""
        if type is String:
            return _AttrValueUnicode
        elif type is Unicode:
            return _AttrValueUnicode
        elif type is Integer:
            return _AttrValueInteger
        elif type is Boolean:
            return _AttrValueBoolean
        elif type is DateTime:
            return _AttrValueDatetime
        elif type is ID:
            return _AttrValueInteger
        elif type is IDList:
            return _AttrValueListID
        elif type is TextList:
            return _AttrValueListText
        elif type is DecimalList:
            return _AttrValueListDecimal
        elif type is File:
            return _AttrValueFile
        elif type is LineString:
            return _AttrValueLineString
        elif type is _Participants:
            return _AttrValueParticipants
        elif type is ParameterInformations:
            return _AttrValueListParameterInformation
        raise TypeError(
            u'Unknown type {} cannot be stored in _Attr system.'.format(type))

    @classmethod
    def value_class(cls, attr_type):
        """Get the _AttrValue class corresponding to the type."""
        if type(attr_type) is list:
            return map(cls._value_class, attr_type)
        return cls._value_class(attr_type)

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
            attrs = attrs.filter(_Attr.key == key)
        if accepted_only:
            attrs = attrs.filter(_Change.accepted == True)
        return attrs

    @deprecated('Use attrsq() or attrs instead of history()')
    def history(self, key=None, **kwargs):
        return self.attrsq(key, **kwargs)

    def get_attr(self, key):
        """Return the most recent accepted _Attr for key."""
        attr = self.attrsq(key).first()
        if attr:
            return attr
        else:
            raise KeyError(u"No _Attr '{}' for {}".format(key, self))

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
        # TODO
        # Don't check for type here. This can & will be done at flush time by
        # the engine
        #if type(value) != restrictions['type']:
        #    raise TypeError(u'expected {}, got {}'.format(
        #        restrictions['type'], type(value)))
        attr_type = self.attr_type(key)
        attr = _Attr(person, key, attr_type, value, note)
        self.attrs.append(attr)
        return attr

    def delete(self, key, person, note=None):
        """Delete the value for key."""
        attr_type = self.attr_type(key)
        attr = _Attr(person, key, attr_type, note=note, deleted=True)
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
        return self.tracked.filter(_Attr.str_type == 'File')

    @hybrid_property
    def unjudged_tracked(self):
        return self.tracked.filter(_Change.judgment_timestamp == None).\
            filter(_Change.judgment_person_id == None)

    @hybrid_property
    def unjudged_tracked_data(self):
        return self.unjudged_tracked.filter(_Attr.str_type == 'File')

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
        return self.pending_tracked.filter(_Attr.str_type == 'File')

    @hybrid_property
    def accepted_tracked(self):
        return self.tracked.filter(_Change.accepted == True)

    @hybrid_property
    def accepted_tracked_data(self):
        return self.accepted_tracked.filter(_Attr.str_type == 'File')

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
    @deprecated
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
    def _filter_by_key_value(cls, query, attr_class, key, value):
        """Produce filter for the given value and attr_class."""
        expect_list = type(attr_class.value) == AssociationProxy

        #log.debug('{} {} {}'.format(attr_class, key, value))

        q = query.filter(_Attr.key == key)
        if type(value) is list:
            for v in value:
                if expect_list:
                    q = q.filter(attr_class.value.contains(v))
                else:
                    try:
                        v = attr_class.test_type(None, v)
                        if v != value:
                            return query
                    except ValueError:
                        return query
                    q = q.filter(attr_class.value == v)
        else:
            if expect_list:
                q = q.filter(attr_class.value.contains(value))
            else:
                try:
                    v = attr_class.test_type(None, value)
                    if v != value:
                        return query
                except ValueError:
                    return query
                q = q.filter(attr_class.value == value)
        return q

    @classmethod
    def filter_by_key_value(cls, query, key, value):
        attrclass = cls.attr_class(key)
        if type(attrclass) is list:
            filters = []
            for attr_class in attrclass:
                filters.append(
                    cls._filter_by_key_value(query, attr_class, key, value))
            if filters:
                return filters[0].union(*filters[1:])
        else:
            return cls._filter_by_key_value(query, attrclass, key, value)

    @classmethod
    def get_by_attrs_true_match2(cls, obj, dict, accepted_only=True):
        """Test resulting objs to ensure the most current values match."""
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
    def get_one_by_attrs(cls, session, dict={}, accepted_only=True):
        """Return _AttrMgr whose _Attrs values match the given dictionary.

        accepted_only -- (bool) limits the returned _AttrMgrs to ones whose were
            accepted.

        """
        query = cls.get_by_attrs_query2(session, dict, accepted_only)
        obj = query.first()
        if cls.get_by_attrs_true_match2(obj, dict, accepted_only):
            return obj
        return None

    @classmethod
    def get_by_attrs2(cls, session, dict={}, accepted_only=True):
        """Return _AttrMgrs whose _Attrs values match the given dictionary.

        accepted_only -- (bool) limits the returned _AttrMgrs to ones whose were
            accepted.

        """
        query = cls.get_by_attrs_query2(session, dict, accepted_only)
        objs = query.all()
        return filter(
            lambda o: cls.get_by_attrs_true_match2(
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
        #objs = cls.all_by_ids(session, obj_ids)

        #return filter(
        #    lambda o: cls._get_by_attrs_true_match(
        #        o, value_key, accepted_only, **map), objs)


class _IDAttrMgr(_AttrMgr):
    """Mixin of _Attr tracking and id related methods.

    This is the base for Obj and Person because linking Person to changes causes
    a cyclical dependency that causes SQLAlchemy to attempt to insert Person
    before Change.

    """
    @hybrid_property
    def uid(self):
        return self.id

    @property
    def mtime(self):
        creation_time = self.creation_timestamp
        accepted = self.accepted_tracked.all()
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
        """Return a dict representation of the Obj.

        This is used to present JSON.

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


class Obj(_Change, _IDAttrMgr):
    """Base object for all tracked objects in the system.

    Objs may have two types of attributes:
    1. system attributes (columns) - written directly into the object
    2. tracked attributes (_Attrs) - written as _Attrs which are
        _Changes themselves. These should only be edited using the _AttrMgr
        interface.

    """
    __tablename__ = 'objs'
    id = Column(Integer, ForeignKey('changes.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'obj',
    }

Obj.allow_attr('import_id', String, 'Import ID')

@event.listens_for(Obj, 'after_insert')
@event.listens_for(Obj, 'after_update')
def _saved_obj(mapper, connection, target):
    triggers.saved_obj(target)


@event.listens_for(Obj, 'after_delete')
def _deleted_obj(mapper, connection, target):
    triggers.deleted_obj(target)


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

    """
    __tablename__ = 'cruises'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

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
    def expocode(self):
        return self.get('expocode', None)

    @property
    def date_start(self):
        return self.get('date_start', None)

    @property
    def date_end(self):
        return self.get('date_end', None)

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
        """These are institutions that are directly attached to the cruise.

        Application: Suppose a cruise were to be done by an institution but the
        PI was from a different one.

        """
        institution_ids = self.get('institutions', [])
        return Institution.all_by_ids(object_session(self), institution_ids)

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
        id = self.get('ship', None)
        if id:
            return object_session(self).query(Ship).get(id)
        return None

    @property
    def country(self):
        id = self.get('country', None)
        if id:
            return object_session(self).query(Country).get(id)
        return None

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
        if not participants:
            return Participants()
        return participants

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
            return None
        return shapely.wkb.loads(str(track.geom_wkb))

    @classmethod
    def filter_geo(cls, fn, cruises):
        return filter(lambda x: fn(x.track), cruises)

    @classmethod
    def get_by_expocode(cls, session, expocode):
        """Return all Cruises that match expocode.

        Multiple Cruises *may* have the same expocode. *Yes* it has happened.

        """
        return Cruise.get_by_attrs2(session, {'expocode': expocode})

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

    ('participants', _Participants),

    ('parameter_informations', ParameterInformations), 
    ]
for key, name in data_file_human_names.items():
    __cruise_allow_attrs.extend([
        (key, File, name),
        ('{}_status'.format(key), TextList),
        ])
Cruise.allow_attrs(__cruise_allow_attrs)


class CruiseAssociate(object):
    """Mixin that provides a way to get the cruises associated with Obj."""

    # Cruise associate key is the _Attr key of Cruise on which the
    # CruiseAssociate ids are stored.
    cruise_associate_key = ''

    def cruise_query_dict(self):
        return {self.cruise_associate_key: self.id}

    def cruises_query(self, limit=0, accepted_only=True):
        session = object_session(self)
        query = Cruise.get_by_attrs_query2(
            session, self.cruise_query_dict(), accepted_only)
        return query

    def cruises(self, limit=0, accepted_only=True):
        query = self.cruises_query(limit, accepted_only)
        if accepted_only:
            query = query.order_by(Cruise.judgment_timestamp)
        else:
            query = query.order_by(Cruise.creation_timestamp)

        dict = self.cruise_query_dict()
        return filter(
            lambda c: Cruise.get_by_attrs_true_match2(
                c, dict, accepted_only), query.all())


class CruiseParticipantAssociate(CruiseAssociate):
    """Mixin that provides a way to get the cruises associated with 
    Participant.

    These are people or institutions.

    """
    cruise_associate_key = 'participants'
    cruise_participant_associate_key = None

    def cruises(self):
        return super(CruiseParticipantAssociate, self).cruises(
            self.cruise_participant_associate_key)


class Country(CruiseAssociate, Obj):
    __tablename__ = 'countries'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    iso_3166_1 = Column(Unicode, key='name')
    iso_3166_1_alpha_2 = Column(String(2), key='iso_code_2')
    iso_3166_1_alpha_3 = Column(String(3), key='iso_code_3')

    __mapper_args__ = {
        'polymorphic_identity': 'country',
    }

    cruise_associate_key = 'country'

    @hybrid_property
    def name(self):
        return self.iso_3166_1

    def iso_code(self, alpha=None):
        if not alpha:
            return self.name
        elif alpha == 2:
            return self.iso_3166_1_alpha_2
        elif alpha == 3:
            return self.iso_3166_1_alpha_3

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
    person_id = Column(
        Integer, ForeignKey('people.id'), primary_key=True)
    permission = Column(Unicode, primary_key=True)

    def __init__(self, permission):
        self.permission = permission


class Person(CruiseParticipantAssociate, Obj):
    """A Person in this system.

    People may be either verified or not. If they are associated with an ID
    provider then they are verified.

    """
    __tablename__ = 'people'
    id = Column(
        Integer, ForeignKey('objs.id', use_alter=True, name='pid'),
        primary_key=True)

    identifier = Column(String)
    name = Column(Unicode)

    email = Column(String)
    permissions_ = relationship(
        _PersonPermissions, single_parent=True,
        cascade='all, delete, delete-orphan')
    permissions = association_proxy('permissions_', 'permission')

    # Legacy name parts
    name_last = Column(Unicode)
    name_first = Column(Unicode)

    cruise_participant_associate_key = 'person'

    __mapper_args__ = {
        'polymorphic_identity': 'person',
    }

    def __init__(self, **kwargs):
        super(Person, self).__init__(self, **kwargs)
        if self.name_last or self.name_first and not self.name:
            self.name = ' '.join(
                filter(None, (self.name_first, self.name_last)))
        if self.identifier is None and self.name is None:
            raise ValueError(
                'Person must be initialized with either identifier or names.')

    @property
    def creation_person_id(self):
        return self.id

    @creation_person_id.setter
    def creation_person_id(self, id):
        pass

    @hybrid_property
    def full_name(cls):
        return cls.name

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
        id = self.get('institution', None)
        if id:
            return object_session(self).query(Institution).get(id)
        return None

    @property
    def country(self):
        id = self.get('country', None)
        if id:
            return object_session(self).query(Country).get(id)
        return None

    def __unicode__(self):
        return u'Person(identifier={}, name={})'.format(
            self.identifier, self.name)

    def __repr__(self):
        return unicode(self)

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

    def __repr__(self):
        return unicode(self)

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
    """MultiName mixin for multiple possible names in tracked _Attr.

    The first stored name is taken as the default.

    TODO perhaps Institutions and Ships may also have multiple names. For now
    let them have just one canonical name.

    """

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
    

class Institution(CruiseParticipantAssociate, Obj):
    __tablename__ = 'institutions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'institution',
    }

    cruise_participant_associate_key = 'institution'

    @property
    def name(self):
        return self.get('name', None)

    def people(self):
        return Person.get_by_attrs2(
            object_session(self), {'institution': self.id})

    @property
    def country(self):
        country = self.get('country', None)
        if country:
            return object_session(self).query(Country).get(country)
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

Institution.allow_attrs([
    ('name', Unicode),
    ('phone', Unicode),
    ('address', Unicode),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])


class Ship(CruiseAssociate, Obj):
    __tablename__ = 'ships'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

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

Ship.allow_attrs([
    ('name', Unicode),
    ('nodc_platform_code', String, 'NODC Platform Code'),
    ('url', Unicode, 'Link'),
    
    ('country', ID),
    ])


class Collection(CruiseAssociate, MultiName, Obj):
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
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'collection',
    }

    __table_args__ = (
        Index('idx_pkey_collection_id', 'id'),
        )

    cruise_associate_key = 'collections'

    @property
    def type(self):
        return self.get('type', None)

    @property
    def basins(self):
        return self.get('basins', [])

    @classmethod
    def get_all_by_name(cls, name):
        """Returns all collections that match the given name.

        Parameters:
            name - either a string or a regular expression object
        
        """
        return self.get_by_attrs2(DBSession, {'names': name})

    @classmethod
    def get_by_name(cls, name):
        # TODO
        return cls.get_by_attrs2(DBSession, {'names': name}, value_key='0')

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
        colls = DBSession.query(cls).all()
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
        colls = DBSession.query(cls).all()
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


class AutoAcceptingObj(Obj):
    """When AutoAcceptingObjs are saved, they are also accepted using the
    creator as the signer, obviating the step of accepting known good changes.

    """
    def save(self):
        super(AutoAcceptingObj, self).save()
        if not self.judgment_stamp:
            self.accept(self.creation_person)


argo_file_requests_for = Table('argo_file_requests_for', Base.metadata,
    Column('argo_file_id', ForeignKey('argo_files.id')),
    Column('request_for_id', ForeignKey('requests_for.id')),
    )


class ArgoFile(AutoAcceptingObj):
    """Files that are given to the CCHDO for Argo calibration only.

    THESE ARE NOT PUBLIC DATA and are only to be shown in the Argo Secure File
    Repository.

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
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    text_identifier = Column(Unicode)
    description = Column(Unicode)
    display = Column(Boolean)

    file__id = Column('file_id', Integer, ForeignKey('fsfile.id'))
    file_ = relationship('FSFile')

    link_cruise_id = Column(Integer, ForeignKey('cruises.id'))
    link_cruise = relationship(
        'Cruise', primaryjoin='ArgoFile.link_cruise_id == Cruise.id')
    link_attr_key = Column(Unicode)

    requests_for = relationship(
        'RequestFor', secondary=argo_file_requests_for, single_parent=True,
        cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'argo_file',
    }

    @property
    def file(self):
        """Gives the file that the ArgoFile refers to."""
        if self.link_cruise:
            return self.link_cruise.get(self.link_attr_key, None)
        return self.file_

    @file.setter
    def file(self, f):
        self.file_ = f

    def link(self, cruise, attr_key):
        """Populates the ArgoFile as a linked file."""
        try:
            cruise.get(attr_key)
        except KeyError:
            raise ValueError('%s does not exist for %s' % (attr_key, cruise))
        self.link_cruise = cruise
        self.link_attr_key = attr_key


old_submissions_files_table = Table('old_submission_files', Base.metadata,
    Column('fsfile_id', ForeignKey('fsfile.id')),
    Column('old_submission_id', ForeignKey('old_submissions.id')),
    )


class OldSubmission(Obj):
    """An old submission imported for record keeping.

    Other information stored:

    * The creation timestamp is the create time for the submission record.
    * The judgment timestamp is the update time for the submission record.

    Since it appears that the submissions were created using a script, only the
    first encountered time is recorded.
    
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
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    date = Column(DateTime)
    stamp = Column(String(6))
    submitter = Column(Unicode)
    line = Column(Unicode)
    folder = Column(Integer(13))
    files = relationship(
        'FSFile', secondary=old_submissions_files_table,
        single_parent=True,
        cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'old_submission',
    }


class Submission(Obj):
    """A Submission to the CCHDO.

    These interface with humans so they need intervention to make everything
    behaves nicely before going into the system.

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
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    expocode = Column(Unicode)
    ship_name = Column(Unicode)
    line = Column(Unicode)
    action = Column(Unicode)
    cruise_date = Column(TIMESTAMP)
    type = Column(Unicode)
    attached_id = Column(Integer, ForeignKey('attrs.id'))
    attached = relationship('_Attr')

    file_id = Column(Integer, ForeignKey('fsfile.id'))
    file = relationship('FSFile')

    request_for_id = Column(Integer, ForeignKey('requests_for.id'))
    request_for = relationship(
        'RequestFor', uselist=False, single_parent=True,
        cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'submission',
    }

    @property
    def identifier(self):
        return self.expocode_

    def cruises_from_identifier(self):
        try:
            cruises = Cruise.get_by_attrs2(
                object_session(self), {'expocode': self.expocode})
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
        return object_session(self).query(_Attr).get(self.attached_)

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
    """A parameter that is measured.

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
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'parameter',
    }
    @property
    def aliases(self):
        return self.get('aliases') or []

    @property
    def unit(self):
        return object_session(self).query(Unit).get(self.get('unit'))

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

Parameter.allow_attrs([
    ('name', Unicode, 'WOCE mnemonic'),
    ('aliases', TextList),
    ('full_name', Unicode),
    ('name_netcdf', Unicode, 'WOCE NetCDF name'),
    ('description', Unicode),
    ('format', Unicode, 'C format string'),
    ('bounds', DecimalList),
    ('unit', ID),
    ('in_groups_but_did_not_exist', Boolean), 
    ])


class Unit(Obj):
    """A unit for parameters.

    Attributes:
    name - The name for a unit
    mnemnoic - the WOCE mnemonic for the unit

    """
    __tablename__ = 'units'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'unit',
    }
    pass

Unit.allow_attrs([
    ('name', Unicode),
    ('mnemonic', Unicode),
    ])


class ParameterOrder(Obj):
    """Define the class that a Parameter of which it is a member.

    Attributes:
        name - the class
        order - the list of parameters in the order they should appear

    """
    __tablename__ = 'parameter_orders'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'parameter_order',
    }

    @property
    def order(self):
        order = self.get('order', [])
        return Parameter.all_by_ids(object_session(self), order)

ParameterOrder.allow_attrs([
    ('name', Unicode),
    ('order', IDList),
    ])


# Environment munging 

# Fix Postgis 2.0 bad function call for WKTSpatialElement. The function name
# changed from GeomFromText to ST_GeomFromText.
from geoalchemy.postgis import PGSpatialDialect
from geoalchemy.base import WKTSpatialElement
pg_funcs = PGSpatialDialect._PGSpatialDialect__functions
pg_funcs[WKTSpatialElement] = 'ST_GeomFromText'

@event.listens_for(mapper, 'after_configured')
def _after_mapper_configured_reorder_tables():
    """Change the order of tables so that Person ends up behind Obj."""
    _Change.__mapper__._sorted_tables = _sorted_tables(_Change.__mapper__)
