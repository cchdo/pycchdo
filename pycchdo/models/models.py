from datetime import datetime
from string import capwords
import re
import os
import os.path
from shutil import rmtree
from traceback import format_exc

from webob.multidict import MultiDict

from sqlalchemy import (
    event, Column, ForeignKey, Table,
    )
from sqlalchemy.exc import StatementError, DataError, InvalidRequestError
from sqlalchemy.sql import (
    and_, not_,
    case, select, exists, distinct,
    )
from sqlalchemy.schema import Index
from sqlalchemy.orm import (
    backref, scoped_session, make_transient, sessionmaker, composite,
    relationship, reconstructor, mapper, joinedload, subqueryload,
    noload, dynamic_loader, joinedload_all, subqueryload_all,
    aliased, with_polymorphic, contains_eager, lazyload,
    remote, defer, undefer
    )
from sqlalchemy.orm.attributes import (
    flag_modified, set_committed_value, register_attribute,
    )
from sqlalchemy.orm.collections import (
    collection, attribute_mapped_collection,
    )
from sqlalchemy.ext.associationproxy import (
    association_proxy, AssociationProxy, _AssociationList)
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from sqlalchemy.ext.mutable import Mutable, MutableComposite
from sqlalchemy.ext.declarative import (
    declarative_base,
    declared_attr, 
    )

from zope.sqlalchemy import ZopeTransactionExtension

from geoalchemy import (
    GeometryColumn, LineString, GeometryDDL, 
    )
from geoalchemy.postgis import PGComparator

from shapely import wkb, wkt
from shapely.geometry import shape as sg_shape, linestring as sg_LineString

from geojson import LineString as gj_LineString

from libcchdo.fns import uniquify
from libcchdo.recipes.orderedset import OrderedSet

from pycchdo.util import (
    FileProxyMixin, listlike, is_valid_ip, _sorted_tables,
    timestamp_now, re_flags_to_pg_op, drop_everything
    )
from pycchdo.models import triggers
from pycchdo.models.types import *
from pycchdo.models.filestorage import (
    CachingFile, seek_size, DirFileSystemStorage,
    )
from pycchdo.models.file_types import (
    data_file_human_names, data_file_descriptions,
    )
from pycchdo.models import log


__all__ = [
    'timestamp_now',
    'data_file_human_names', 'data_file_descriptions',
    'reset_database', 'reset_fs', 
    'Session', 'DBSession', 'Base',
    'Stamp', 'Note', 'FSFile',
    'RequestFor', 'RequestForAttr',
    'Participants', 'Participant', 'ParameterInformation', 
    'Obj', 'Person', 'Cruise', 'Country', 'Institution', 'Ship', 'Collection',
    'ArgoFile', 'OldSubmission', 'Submission', 'Parameter', 'Unit',
    'ParameterOrder',
    '_Attr',
    'disjoint_load_obj', 'disjoint_load_list', 'batch_load_cruises',
    'preload_person', 'disjoint_load_collection_attrs',
    ]


Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)


use_cache = True


Base = declarative_base()


def reset_database(engine):
    """Clears the database and recreates schema."""
    drop_everything(engine)
    meta = Base.metadata
    meta.create_all(engine)


def reset_fs():
    fss_root = FSFile._fs.base_location
    for root, dirs, files in os.walk(fss_root):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            rmtree(os.path.join(root, d))


class Datacart(OrderedSet):
    """A Datacart contains files that are meant to be downloaded in bulk.

    Each file is refered to by attribute id.

    """
    def files(self):
        return _Attr.by_ids(list(self))

    @classmethod
    def is_file_type_allowed(cls, ftype):
        """Determine whether a data file of ftype is allowed in the data cart.

        """
        prefixes = ['btl', 'bot', 'ctd', 'doc', 'sum']
        for prefix in prefixes:
            if ftype.startswith(prefix):
                return True
        return False

    def cruise_files_in_cart(self, cruise):
        """Return a tuple of the number of files in cart and number of files.

        """
        file_attrs = cruise.file_attrs

        file_count = 0
        for ftype, fattr in file_attrs.items():
            if not self.is_file_type_allowed(ftype):
                continue
            if fattr.id in self:
                file_count += 1
        return (file_count, len(file_attrs))


class Stamp(MutableComposite):
    def __init__(self, person_id, timestamp=None, allow_blank=True):
        """Create a Stamp representing a Person and a time.

        Arguments::
        person_id -- the Person id
        timestamp -- the time (default: now)
        allow_blank -- allows the Stamp to be created with neither person nor
            timestamp. This is the default because Stamps are created when
            SQLAlchemy loads the instance.

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
        else:
            if not allow_blank:
                raise ValueError(u'Stamp must have at least a Person')

    def __composite_values__(self):
        return [self.person_id, self.timestamp, ]

    def __setattr__(self, key, value):
        """Intercept set events and alert parents to change."""
        object.__setattr__(self, key, value)
        self.changed()

    def __nonzero__(self):
        return not (self.person_id is None and self.timestamp is None)

    def __eq__(self, other):
        if other is None:
            return not bool(self)
        if type(other) is not Stamp:
            return False
        return (
            self.person_id == other.person_id and 
            self.timestamp == other.timestamp)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __unicode__(self):
        if not self:
            return u'Stamp(empty)'
        if not self.timestamp:
            return u'Stamp({0})'.format(self.person_id)
        return u"Stamp({0}, {1})".format(
            self.person_id, self.timestamp.strftime('%FT%T'))

    def __repr__(self):
        return unicode(self)


class StampedCreation(object):
    """Mixin to store the creation time and person."""
    @hybrid_property
    def ctime(cls):
        return cls.creation_timestamp


class StampedModeration(object):
    """Mixin to store the pending and judgment time and person."""
    pass


class DBQueryable(object):
    """Mixin to obtain query on this class for global database session."""
    @classmethod
    def query(cls, *args):
        """Return a query for this class on the global database session."""
        if args:
            return DBSession.query(*args)
        return DBSession.query(cls)


class Notable(object):
    """Mixin to store notes."""
    @declared_attr
    def notes(cls):
        if cls.__name__ == 'Person':
            fk = Note.person_id
        else:
            fk = Note.change_id
        return relationship(
            'Note', primaryjoin=fk == cls.id,
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


class Note(StampedCreation, DBQueryable, Base):
    """A Note that can be attached to any _Change.

    A _Change may have many Notes.

    Parameters::

    body - the actual note
    action - the action taken
    data_type - the type of data that was changed
    subject - a nice summary
    discussion - Setting this True makes the note only visible for mergers.
                     
    """
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True)

    creation_timestamp = Column(DateTime, default=timestamp_now)
    creation_person_id = Column(Integer, ForeignKey('people.id',
        use_alter=True, name='fk_note_person'))
    creation_person = relationship(
        'Person', primaryjoin='Note.creation_person_id == Person.id')
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

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        try:
            return u'Note({0}, {1})'.format(self.id, self.subject)
        except AttributeError:
            return u'Note({0})'.format(self.id)


@event.listens_for(Note, 'after_insert')
@event.listens_for(Note, 'after_update')
def _saved_note(mapper, connection, target):
    triggers.saved_note(target)


@event.listens_for(Note, 'after_delete')
def _deleted_note(mapper, connection, target):
    triggers.deleted_note(target)


class _Change(StampedCreation, StampedModeration, Notable, DBQueryable, Base):
    """A Change to the dataset.

    Changes will be recorded along with the time and person who changed it.

    Changes may be accepted or rejected. Changes may also have attached notes
    which may be individually public or for dicussion purposes only.

    """
    __tablename__ = 'changes'
    id = Column(Integer, primary_key=True)
    obj_type = Column(String, nullable=False)

    creation_timestamp = Column(DateTime, default=timestamp_now)
    creation_person_id = Column(Integer, ForeignKey('people.id'))
    creation_stamp = composite(Stamp, creation_person_id, creation_timestamp)
    creation_person = relationship(
        'Person', primaryjoin="_Change.creation_person_id==Person.id")

    __mapper_args__ = {
        'polymorphic_on': obj_type,
        'polymorphic_identity': 'change',
        }

    __table_args__ = (
        Index('idx_changes_judgment_timestamp', 'judgment_timestamp'),
        Index('idx_changes_obj_type', 'obj_type'),
        Index('idx_changes_accepted', 'accepted'),
        )

    def __init__(self, person, note=None, allow_blank=False, *args, **kwargs):
        super(_Change, self).__init__(*args, **kwargs)
        self._preload_objs = {}
        self.creation_stamp = Stamp(person.id, allow_blank=allow_blank)
        if note:
            self.notes.append(note)

    @reconstructor
    def __reconstructor__(self):
        self._preload_objs = {}

    def __unicode__(self):
        return u'{}({})'.format(type(self).__name__, self.id)

    def __repr__(self):
        return unicode(self)

    # Moderation attributes

    pending_timestamp = Column(DateTime)
    pending_person_id = Column(Integer, ForeignKey('people.id'))
    pending_stamp = composite(
        Stamp, pending_person_id, pending_timestamp)
    pending_person = relationship(
        'Person', primaryjoin="_Change.pending_person_id==Person.id")

    judgment_timestamp = Column(DateTime)
    judgment_person_id = Column(Integer, ForeignKey('people.id'))
    judgment_stamp = composite(
        Stamp, judgment_person_id, judgment_timestamp)
    judgment_person = relationship(
        'Person', primaryjoin="_Change.judgment_person_id==Person.id")

    accepted = Column(Boolean, default=False)

    def is_judged(self):
        return bool(self.judgment_stamp)

    def is_acknowledged(self):
        return bool(self.pending_stamp)

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

    @classmethod
    def get_id(cls, id):
        return cls.query().get(id)

    @classmethod
    def by_ids(cls, ids):
        if ids:
            return cls.query().filter(cls.id.in_(ids))
        return cls.query().filter(False)

    @classmethod
    def only_if_accepted_is(cls, accepted=True):
        """Return a query for this class only when accepted or not."""
        return cls.query().filter(cls.accepted == accepted)


class RequestFor(DBQueryable, Base):
    """Information about HTTP request of another object."""
    __tablename__ = 'requests_for'

    id = Column(Integer, primary_key=True)
    type = Column(String)

    dt = Column(DateTime)
    ua = Column(String)
    ip = Column(String)

    def __init__(self, request):
        """Takes a webob.Request and stores information relevant to tracking.

        Parameters:
        request - the webob.Request

        """
        try:
            self.dt = request.date
            self.ip = request.remote_addr
            self.ua = request.user_agent
            if not type(self.dt) is datetime:
                raise ValueError()
            if not is_valid_ip(self.ip):
                raise ValueError()
        except (AttributeError, ValueError):
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


class FSFile(FileProxyMixin, DBQueryable, Base):
    """A file record that points to the filesystem file."""
    __tablename__ = 'fsfile'

    id = Column(Integer, primary_key=True)
    fsid = Column(Unicode)
    name = Column(Unicode)
    content_type = Column(Unicode)
    upload_date = Column(DateTime, default=timestamp_now)

    # Stores information used by pycchdo.importer.cchdo to correlate ArgoFiles
    # with Documents and QueueFiles with QueueFiles.
    import_id = Column(Unicode)
    import_path = Column(Unicode)

    _fs = None
    _fs_kwargs = None

    def __init__(self, file=None, filename=None, contentType=None):
        self._fsid_dirty = True
        self.file = file
        self.name = unicode(filename)
        self.content_type = unicode(contentType)

    @reconstructor
    def init_on_load(self):
        self._fsid_dirty = False

    @property
    def size(self):
        file = self.file
        # Attempt to set file._size appropriately for Django FS to work.
        if not hasattr(file, '_size'):
            if hasattr(file, 'size'):
                file._size = file.size
            else:
                try:
                    fname = file.name
                    if fname and os.path.exists(fname):
                        file._size = os.path.getsize(fname)
                    else:
                        raise AttributeError()
                except AttributeError:
                    file._size = seek_size(file)
        return file._size

    @classmethod
    def fs(cls):
        if not cls._fs:
            cls.fs_setup()
        return cls._fs

    @classmethod
    def fs_setup(cls, **kwargs):
        cls._fs = DirFileSystemStorage(**kwargs)

    @staticmethod
    def from_fieldstorage(fs):
        file = fs.file
        filename = fs.filename
        content_type = fs.type
        if not content_type:
            content_type = 'application/octet-stream'
        fsfile = FSFile(file, filename, content_type)

        # Call size while file is still in scope to cache size
        fsfile.size
        return fsfile

    @property
    def file(self):
        try:
            return self.file_
        except AttributeError:
            try:
                self.file_ = self.fs().open(self.fsid)
            except IOError, e:
                log.error(
                    u'Unable to open FSFile({0}): {1}'.format(self.id, e))
                self.file_ = None
            return self.file_

    @file.setter
    def file(self, f):
        if f:
            if type(f) != CachingFile:
                self.file_ = CachingFile(f)
            else:
                self.file_ = f
        else:
            self.file_ = None
        flag_modified(self, 'fsid')
        self._fsid_dirty = True
        log.debug('set file for {0!r} to {1!r}'.format(self, self.file_))

    @classmethod
    def attr_by_import_id(cls, import_id):
        """Return _Attr matching FSFile import_id.

        """
        return _Attr.query().join(_AttrValueFile).join(FSFile).\
            filter(FSFile.import_id == import_id).first()


@event.listens_for(FSFile, 'before_insert')
@event.listens_for(FSFile, 'before_update')
def _saved_file(mapper, connection, target):
    log.debug(u'Saving file {0} {1}'.format(target, target.file))
    save_me = target.file

    if not target._fsid_dirty:
        log.debug(u'no actual change. skipping file save')
        return

    # Delete the old file
    _deleted_file(mapper, connection, target)

    if save_me is None:
        return

    # Attempt to set file._size appropriately for Django FS to work.
    if not hasattr(save_me, '_size'):
        if hasattr(save_me, 'size'):
            save_me._size = save_me.size
        else:
            try:
                fname = save_me.name
                if fname and os.path.exists(fname):
                    save_me._size = os.path.getsize(fname)
            except AttributeError:
                save_me._size = seek_size(save_me)

    cpos = save_me.tell()
    # Do not use the same name for every file or this method will become *very*
    # slow.
    available_name = target.fs().get_available_name(str(hash(save_me)))
    try:
        target.fsid = unicode(target.fs().save(available_name, save_me))
    except (IOError, OSError), e:
        log.error(u'Unable to save file {0!r} {1!r} to {2!r}:\n{3}'.format(
            target, save_me, available_name, format_exc()))
        raise e
    save_me.seek(cpos)

    log.debug(u'saved file {0!r}'.format(save_me))
    target._fsid_dirty = False

    # delete this reference to the file cache
    del target.file_


@event.listens_for(FSFile, 'after_delete')
def _deleted_file(mapper, connection, target):
    target.fs().delete(target.fsid)


class _AttrValue(DBQueryable, Base):
    """A value stored by _Attr.

    Meant to be abstract but has a concrete table because it contains the
    reference to the _Attr that helps with polymorphic querying.

    """
    __tablename__ = 'av'
    id = Column(Integer, primary_key=True)
    type = Column(String)

    accepted = Column(Boolean, default=False)
    attr_id = Column(Integer, ForeignKey('attrs.id'))

    #attr = relationship(
    #    '_Attr', primaryjoin='_AttrValue.attr_id == _Attr.id',
    #    single_parent=True,
    #    backref=backref('vs',
    #        lazy='joined',
    #        collection_class=attribute_mapped_collection('accepted'),
    #    ), cascade='all, delete, delete-orphan')

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

    __table_args__ = (
        Index('idx_attrvalue', 'attr_id', 'accepted'),
        )

    @hybrid_property
    def value(self):
        raise ValueError('_AttrValue is not a valid storage container.')

    @value.expression
    def value(cls):
        return u'{}.{}'.format(cls.__name__, 'value')

    def __repr__(self):
        return u'{}({}, {})'.format(type(self).__name__, self.id, self.value)


class _AttrValueInteger(_AttrValue):
    value = Column('v_i', Integer)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        try:
            return int(value)
        except Exception:
            raise TypeError('{0!r} is not coerceable to int'.format(value))


event.listen(_AttrValueInteger.value, 'set', _AttrValueInteger._coerce)


class _AttrValueBoolean(_AttrValue):
    value = Column('v_b', Boolean)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        try:
            return bool(value)
        except Exception:
            raise TypeError('{0!r} is not coerceable to bool'.format(value))


event.listen(_AttrValueBoolean.value, 'set', _AttrValueBoolean._coerce)


class _AttrValueUnicode(_AttrValue):
    value = Column('v_u', Unicode)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        if type(value) is datetime:
            raise TypeError('{0!r} is not a string'.format(value))
        try:
            return unicode(value)
        except Exception:
            raise TypeError('{0!r} is not coerceable to unicode'.format(value))


event.listen(
    _AttrValueUnicode.value, 'set', _AttrValueUnicode._coerce, retval=True)


class _AttrValueDatetime(_AttrValue):
    value = Column('v_dt', DateTime)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        if type(value) is not datetime:
            raise TypeError('{0!r} is not a datetime'.format(value))
        return value


event.listen(_AttrValueDatetime.value, 'set', _AttrValueDatetime._coerce)


class _AttrValueLineString(_AttrValue):
    value_ = GeometryColumn(
        'v_ls', LineString(2, spatial_index=False), comparator=PGComparator)

    @property
    def value(self):
        if self.value_ is None:
            return None
        try:
            return wkb.loads(str(self.value_.geom_wkb))
        except AttributeError, e:
            return sg_LineString.LineString(
                self.value_.coords(DBSession))

    @value.setter
    def value(self, x):
        self.value_ = x.wkt

    def _verify_and_normalize_linestring(self, value):
        """Convert value into a Shapely LineString."""
        if type(value) is sg_LineString.LineString:
            pass
        elif type(value) is gj_LineString:
            value = sg_shape(value)
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
                        'Coordinate list must contain numbers. Element {0} '
                        'does not'.format(i))
            value = sg_LineString.LineString(value)
        return value

    def __init__(self, value, *args, **kwargs):
        super(_AttrValueLineString, self).__init__(*args, **kwargs)
        self.value = self._verify_and_normalize_linestring(value)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        try:
            return wkt.loads(value)
        except Exception:
            raise TypeError('{0!r} is not a WKT LineString'.format(value))


event.listen(_AttrValueLineString.value_, 'set', _AttrValueLineString._coerce)


GeometryDDL(_AttrValueLineString.__table__)


class _AttrValueFile(_AttrValue):
    value_ = Column('v_fsid', ForeignKey('fsfile.id'))
    value = relationship(
        'FSFile', primaryjoin='FSFile.id == _AttrValueFile.value_',
        lazy='joined', backref=backref('av', single_parent=True, uselist=False),
        cascade='all, delete',
        )

    def __init__(self, value, *args, **kwargs):
        """Create an _AttrValueFile reference to an FSFile from a FieldStorage.

        """
        super(_AttrValueFile, self).__init__(*args, **kwargs)
        self.value = FSFile(value.file, value.filename)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        if type(value) is not FSFile:
            try:
                return FSFile(value)
            except AttributeError:
                raise TypeError(
                    '{0!r} could not be coerced into a FSFile'.format(value))
        return value

event.listen(_AttrValueFile.value, 'set', _AttrValueFile._coerce)


class Participant(DBQueryable, Base):
    """A participant consisting of role, person, and optionally institution."""
    __tablename__ = 'participants'
    id = Column(Integer, primary_key=True)
    attrvalue_id = Column(Integer, ForeignKey('av.id'))
    role = Column(Unicode, nullable=False)
    person_id = Column(ForeignKey('people.id'), nullable=False)
    person = relationship('Person', lazy='joined')
    institution_id = Column(Integer, ForeignKey('institutions.id'))
    institution = relationship('Institution', lazy='joined')

    __table_args__ = (
        Index('idx_participant_av_role_person', 'attrvalue_id', 'role',
              'person_id'),
        )

    def __init__(self, role, person, institution=None):
        self.role = role
        self.person = person
        if institution:
            self.institution = institution
    
    def __eq__(self, other):
        if (    hash(self) == hash(other) and
                self.institution == other.institution):
            return True
        return False

    def __hash__(self):
        return hash(u'{0}_{1}_{2}'.format(
            self.attrvalue_id, self.role, self.person))

    def __repr__(self):
        return u'Participant({0}, {1}, {2})'.format(
            self.role, self.person, self.institution)
        

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
        """Appends a participant to the map under the given role."""
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

    def _replace(self, items):
        self.data = items

    def __len__(self):
        return len(self.data)

    def append_(self, cruise, signer, participant):
        """Return suggestion with participant appended.

        This function tracks history.

        """
        p = Participants(self)
        p._append(participant)
        return cruise.set('participants', p, signer)

    def extend_(self, cruise, signer, *participants):
        """Return suggestion with participants appended.

        This function tracks history.

        """
        p = Participants(self)
        p._extend(participants)
        return cruise.set('participants', p, signer)

    def remove_(self, cruise, signer, *participants):
        """Return suggestion with participants removed.

        This function tracks history.

        """
        p = Participants(self)
        for participant in participants:
            p._remove(participant)
        return cruise.set('participants', p, signer)

    def clear_(self, cruise, signer):
        """Return suggestion with no participants.

        This function tracks history.

        """
        p = Participants(self)
        p._clear()
        return cruise.set('participants', p, signer)

    def replace_(self, cruise, signer, *participants):
        """Return suggestion with participants replaced.

        This function tracks history.

        """
        p = Participants(self)
        p._clear()
        p._extend(participants)
        return cruise.set('participants', p, signer)

    def with_role(self, role):
        """Return Participants for role."""
        return filter(lambda p: p.role == role, self.data)

    def __getitem__(self, *args, **kwargs):
        return self.data.__getitem__(*args, **kwargs)

    def pop(self, *args, **kwargs):
        return self.data.pop(*args, **kwargs)

    @property
    def roles(self, role=None):
        """Pairs of Persons and roles present in the map."""
        if role is None:
            participants = self.data
        else:
            participants = self[role]
        return [(p.person, p.role) for p in participants]

    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return u'Participants({0!r})'.format(self.data)
        

class _AttrValueParticipants(_AttrValue):
    values = relationship(
        'Participant', collection_class=Participants, backref='attrvalue',
        cascade='all, delete-orphan')

    def __init__(self, value, *args, **kwargs):
        super(_AttrValueParticipants, self).__init__(*args, **kwargs)
        self.values = value

    @property
    def value(self):
        return self.values

    @value.setter
    def value(self, x):
        self.values = x

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        if type(value) is not Participant:
            raise TypeError('{0!r} is not a Participant'.format(value))
        return value

    @declared_attr
    def __mapper_args__(cls):
        return {
            'polymorphic_identity': cls.__name__,
        }


class _AttrValueElem(DBQueryable, Base):
    """Base for _AttrValueList elements."""
    __tablename__ = 'ave'

    @declared_attr
    def attrvalue_id(cls):
        return Column(Integer, ForeignKey('av.id'))

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
    value = Column('ave_id', ID)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        return _AttrValueInteger._coerce(target, value)


event.listen(_AttrValueElemID.value, 'set', _AttrValueElemID._coerce)


class _AttrValueElemText(_AttrValueElem):
    value = Column('ave_u', Unicode)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        return _AttrValueUnicode._coerce(target, value)


event.listen(_AttrValueElemText.value, 'set', _AttrValueElemText._coerce)


class _AttrValueElemDecimal(_AttrValueElem):
    value = Column('ave_d', DECIMAL)

    @staticmethod
    def _coerce(target, value, oldvalue=None, initiator=None):
        try:
            # TODO don't use float?
            return float(value)
        except Exception:
            raise TypeError('{0!r} is not coerceable to float'.format(value))


event.listen(_AttrValueElemText.value, 'set', _AttrValueElemText._coerce)


class ParameterInformation(_AttrValueElem):
    """Metadata about a parameter.

    Columns:

    parameter - the parameter
    status - the status of the parameter; one of the following: online,
        reformatted, submitted, not_measured, proposed, no_information
    pi - the principal investigator for the parameter on the cruise
    inst - the institution that the pi was operating for
    ts - some date attached to the status and PI of the parameter

    """
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
        return u'ParameterInformation({}, {}, {}, {}, {})'.format(
            self.parameter_id, self.status, self.pi_id,
            self.inst_id, self.ts)


class _AttrValueList(object):
    # TODO figure out why value must be declared for each list type rather than
    # inherited
    @declared_attr
    def __mapper_args__(cls):
        return {
            'polymorphic_identity': cls.__name__,
        }


class _AttrValueListID(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemID
    values = relationship(
        __elem_class__,
        cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListText(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemText
    values = relationship(
        __elem_class__,
        cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListDecimal(_AttrValueList, _AttrValue):
    __elem_class__ = _AttrValueElemDecimal
    values = relationship(
        __elem_class__,
        cascade='all, delete, delete-orphan')
    value = association_proxy('values', 'value')


class _AttrValueListParameterInformation(_AttrValueList, _AttrValue):
    __elem_class__ = ParameterInformation
    value = relationship(
        __elem_class__, 
        uselist=True, cascade='all, delete, delete-orphan')


@event.listens_for(_AttrValueListID, 'before_delete')
@event.listens_for(_AttrValueListText, 'before_delete')
@event.listens_for(_AttrValueListDecimal, 'before_delete')
@event.listens_for(_AttrValueListParameterInformation, 'before_delete')
def _delete_list_elems_first(mapper, connection, target):
    elemclass = target.__class__.__elem_class__
    delete_stmt = elemclass.__table__.delete(
        elemclass.attrvalue_id == target.id)
    connection.execute(delete_stmt)


class _AttrPermission(DBQueryable, Base):
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

    vs = relationship(
        '_AttrValue', primaryjoin='_AttrValue.attr_id == _Attr.id',
        lazy='joined',
        collection_class=attribute_mapped_collection('accepted'),
        backref=backref('attr', lazy='noload'),
        cascade='all, delete, delete-orphan'
    )


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

    def __init__(self, obj, person, key, attr_type, value=None, note=None,
                 deleted=False):
        """Create an _Attr _Change state.

        Arguments::
        person -- the person who performed the change
        key -- the attribute name that this change is for
        attr_type -- the type(s) of value that this _Attr stores. This
            should be an sqlalchemy type or a list of sqlalchemy types.
        
        Keyword arguments::
        value -- the value to store
        note -- a note to add during creation; syntactic sugar
        deleted -- whether this _Attr's new state is deleted. If this is True,
            the _Attr's value is disregarded.

        """
        super(_Attr, self).__init__(person)

        self.obj = obj

        self.key = key
        self._attr_type = attr_type

        self.deleted = deleted
        if not deleted:
            self._set(value)

        if note is not None:
            self.notes.append(note)

    @property
    def _attr_type(self):
        return self._attr_types

    @_attr_type.setter
    def _attr_type(self, attr_types):
        self._attr_types = attr_types
        self._constructors = _AttrMgr.value_class(self._attr_types)

    @reconstructor
    def reconstructor(self):
        """Reconstruct state on _Attr when loading from database.

        The loaded _attr_types and constructors allow for further modification
        to the _Attr.

        """
        try:
            self._attr_type = self.obj.attr_type(self.key)
        except AttributeError:
            pass

    def _av(self, *args, **kwargs):
        """Create the _AttrValue use to store the value.

        """
        log.debug(u'Constructing _AttrValue for {0} {1}'.format(args, kwargs))
        attr_types = self._attr_type
        constructors = self._constructors
        if type(attr_types) is not list:
            attr_types = [attr_types]
        if type(constructors) is not list:
            constructors = [constructors]

        for constructor, attr_type in zip(constructors, attr_types):
            try:
                v = constructor(*args, **kwargs)
                self.str_type = _AttrMgr.attr_type_to_str(attr_type)
                return v
            except Exception, e:
                log.debug(
                    u'Construct failed for {}: {}'.format(constructor, e))
        raise TypeError(
            u'No constructors {0!r} for {1!r} matched {2!r} ({3!r})'.format(
                constructor, self.key, type(kwargs['value']), kwargs['value']))

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
            list) in the 'track' attribute.
        accepted -- whether to set the value for the original or accepted state

        """
        if value is None and self.str_type == 'ID':
            raise ValueError(
                'IDs should not be None. Is the object persisted?')

        cannot_be_stored_error = TypeError(
            u'{} cannot be stored as {}'.format(value, self._constructors))

        try:
            # there are two possibilities for storage based on the accepted bit
            # of the _AttrValue. Replace if it exists, otherwise add.
            av = self._av(value=value, accepted=accepted)
            self.vs[accepted] = av
        except StatementError:
            raise cannot_be_stored_error

        if self.obj:
            self.obj._recache(key=self.key)

    def accept(self, person):
        if not self.obj:
            raise ValueError(
                'Cannot accept _Attr for no Obj. Check that the Obj is in the '
                'current session and has an id. The Obj must be flushed.')
        super(_Attr, self).accept(person)
        self.obj._recache(key=self.key)

    def acknowledge(self, person):
        if not self.obj:
            raise ValueError(
                'Cannot acknowledge _Attr for no Obj. Check that the Obj is in '
                'the current session and has an id. The Obj must be flushed.')
        super(_Attr, self).acknowledge(person)
        self.obj._recache(clear_first=False)

    def reject(self, person):
        if not self.obj:
            raise ValueError(
                'Cannot rejct _Attr for no Obj. Check that the Obj is in the '
                'current session and has an id. The Obj must be flushed.')
        super(_Attr, self).reject(person)
        self.obj._recache(key=self.key)

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

        try:
            return self.vs[True]
        except KeyError:
            pass
        try:
            return self.vs[False]
        except KeyError, e:
            log.error('Somehow _Attr({0}, {1}) has no _AttrValue'.format(
                self.id, self.key))
            log.error(repr(self.vs))
            raise e

        #if self.v_accepted:
        #    return self.v_accepted
        #return self.v

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
        attr_value = self.attr_value
        if attr_value:
            return attr_value.value
        return None

    @hybrid_property
    def value_original(self):
        """Return the original value of the _Attr."""
        return self.attr_value_original.value

    def __repr__(self):
        try:
            mapping = u'{0}, {1}'.format(repr(self.key), repr(self.value))
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
        elif self.pending_stamp:
            state = 'ACK'

        obj_id = self.obj_id
        id = self.id or '?'
        return u"_Attr({0}, {1}, {2}, obj_id={3}, id={4})".format(
            mapping, state, self.str_type, obj_id, id)

    @classmethod
    def all_data(cls):
        return _Attr.query().filter(_Attr.str_type == 'File').all()

    @classmethod
    def all_track(cls):
        return _Attr.query().filter(_Attr.str_type == 'LineString').all()

    @classmethod
    def pending(cls):
        return _Attr.query().filter(_Change.judgment_stamp == None).all()


class CacheObjAttrs(DBQueryable, Base):
    __tablename__ = 'cache_av'
    obj_id = Column(Integer, ForeignKey('objs.id'), primary_key=True)
    obj = relationship(
        'Obj',
        backref=backref('cache_obj_avs',
            collection_class=attribute_mapped_collection('key'),
            cascade='all, delete, delete-orphan',
        ))
    key = Column(Unicode, primary_key=True)
    attrvalue_id = Column(Integer, ForeignKey('av.id', ondelete='cascade'))
    attrvalue = relationship('_AttrValue', lazy='joined',
        backref=backref('cacheavs', cascade='all, delete, delete-orphan'))

    __table_args__ = (
        Index('idx_cache_obj_avs', 'attrvalue_id', 'obj_id', 'key'),
    )

    def __init__(self, key, attrvalue):
        super(CacheObjAttrs, self).__init__()
        self.key = key
        self.attrvalue = attrvalue

    @property
    def value(self):
        return self.attrvalue.value

    def __unicode__(self):
        return u'{0}({1}, {2}, {3})'.format(
            type(self).__name__, self.obj_id, self.key, self.attrvalue)

    @classmethod
    def cache(cls, obj, key=None):
        # TODO only cache the given key if one is specified
        log.debug('caching {0} {1}'.format(type(obj).__name__, obj.id))
        attrs_current = obj.attrs_current

        for key, attr in attrs_current.items():
            try:
                obj.cache_obj_avs[key]
            except KeyError:
                pass
            obj.cache_obj_avs[key] = cls(key, attr.attr_value)

        deleted_keys = \
            set(obj.cache_obj_avs.keys()) - set(attrs_current.keys())
        for key in deleted_keys:
            del obj.cache_obj_avs[key]

    @classmethod
    def check(cls, force_recache=False):
        log.info('checking cache staleness')
        # TODO
        stale = False
        if force_recache or stale:
            objs = Obj.query().all()
            for obj in objs:
                cls.cache(obj)


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

    It could be best to construct a connection table with _Attr like attributes.
    However, does this consider the case of non-relational values?

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

    # Relationship cannot be declared on _AttrMgr.
    @declared_attr
    def attrs(cls):
        return relationship(
            '_Attr', primaryjoin='_Attr.obj_id == Obj.id',
            backref='obj',
            order_by=_Change.judgment_timestamp.desc,
            cascade='all, delete, delete-orphan',
            )

    @declared_attr
    def attrs_accepted(cls):
        return relationship(
            '_Attr',
            primaryjoin=and_(
                remote(_Attr.obj_id) == cls.id,
                _Change.accepted == True),
            order_by=_Change.judgment_timestamp.desc,
            cascade='all, delete, delete-orphan')

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
        if type == String:
            return _AttrValueUnicode
        elif type == Unicode:
            return _AttrValueUnicode
        elif type == Integer:
            return _AttrValueInteger
        elif type == Boolean:
            return _AttrValueBoolean
        elif type == DateTime:
            return _AttrValueDatetime
        elif type == ID:
            return _AttrValueInteger
        elif type == IDList:
            return _AttrValueListID
        elif type == TextList:
            return _AttrValueListText
        elif type == DecimalList:
            return _AttrValueListDecimal
        elif type == File:
            return _AttrValueFile
        elif type == LineString:
            return _AttrValueLineString
        elif type == ParticipantsType:
            return _AttrValueParticipants
        elif type == ParameterInformations:
            return _AttrValueListParameterInformation
        raise TypeError(
            u'Unknown type {0} cannot be stored in _Attr system.'.format(type))

    @classmethod
    def value_class(cls, attr_type):
        """Get the _AttrValue class corresponding to the type."""
        if type(attr_type) == list:
            return map(cls._value_class, attr_type)
        return cls._value_class(attr_type)

    @classmethod
    def attr_class(cls, key):
        """Return the class for the type allowed for key."""
        return cls.value_class(cls.attr_type(key))

    def attrsq(self, key=None, accepted_only=True):
        """Return a query for _Attrs in the _AttrMgr with key.

        Arguments::
        key -- the key (default: None)
        accepted_only -- whether to limit the query to accepted _Attrs (default:
            True)

        """
        attrs = _Attr.query().filter(_Attr.obj_id == self.id).\
            order_by(_Change.judgment_timestamp.desc())
        if key:
            attrs = attrs.filter(_Attr.key == key)
        if accepted_only:
            attrs = attrs.filter(_Change.accepted == True)
        return attrs

    def get_attr(self, key):
        """Return the most recent accepted _Attr for key."""
        key = unicode(key)
        try:
            return self.attrs_current[key]
        except KeyError:
            log.debug('_Attr for {0!r} is not in {1!r}'.format(
                key, self.attrs_current))
            raise KeyError(u"No accepted _Attr for {0!r}".format(key))

    def get_attr_or(self, key, default=None):
        """Return the most recent accepted _Attr for key or default."""
        try:
            return self.get_attr(key)
        except KeyError:
            return default

    def get(self, key, default=None):
        """Return the value of the most recent accepted _Attr for key.

        Arguments::
        key -- the key to fetch the _Attr for
        default -- if the key is not defined, return this (default: None)

        """
        if use_cache:
            try:
                return self.cache_obj_avs[key].value
            except KeyError:
                return default
        try:
            attr = self.get_attr(key)
            value = attr.value
            log.debug('{0}.{1!r} = {2!r}'.format(self.id, key, value))
            if type(value) is _AssociationList:
                # AssociationList goes out of scope after return; get value now
                # and copy to list
                return list(value)
            return value
        except (AttributeError, KeyError), e:
            log.debug(
                '{0}.{1!r} defaulted: {2!r} ({3!r})'.format(
                    self.id, key, default, e))
            return default

    def set(self, key, value, person, note=None):
        """Set the value for key.

        Raises:
            ValueError when the key is not allowed.

        """
        attr_type = self.attr_type(key)
        attr = _Attr(self, person, key, attr_type, value, note)
        self.attrs.append(attr)
        return attr

    def delete(self, key, person, note=None):
        """Delete the value for key."""
        attr_type = self.attr_type(key)
        attr = _Attr(self, person, key, attr_type, note=note, deleted=True)
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

    def _recache(self, key=None, clear_first=True):
        """Clear the cached current attrs if specified and recache.

        If key is specified, only recache that key.

        If _cache_off is True, caching is skipped. Use this to manually cache
        objs when performing many edits at once.

        """
        try:
            if self._cache_off:
                return
        except AttributeError:
            pass

        # Make sure obj ids are populated
        DBSession.flush()

        if clear_first:
            if key:
                self.recache_attr_current(key)
            else:
                self._clear_cache_attrs_current()
        CacheObjAttrs.cache(self, key=key)

    def _clear_cache_attrs_current(self, expire=True):
        try:
            del self._cache_attrs_current
        except AttributeError:
            pass
        if expire:
            DBSession.expire(self, ['attrs', 'attrs_accepted'])

    def _attr_current(self, key):
        """Return the most current _Attr on the _AttrMgr for key."""
        attrs_accepted_for_key = _Attr.query().\
            filter(and_(_Attr.accepted == True, _Attr.obj_id == self.id,
                _Attr.key == key)).\
            options(subqueryload(_Attr.vs.of_type(_AttrValueUnicode))).\
            order_by(_Change.judgment_timestamp.desc()).all()
        for attr in attrs_accepted_for_key:
            if attr.deleted:
                return None
            return attr
        return None

    def recache_attr_current(self, key):
        # Make sure the attr cache is available before fiddling with it
        self.attrs_current

        # Update the attr cache before trying to get the attrvalue
        attr = self._attr_current(key)
        if attr:
            try:
                self._cache_attrs_current[key] = attr
            except AttributeError:
                self._cache_attrs_current = {key: attr}
        else:
            try:
                del self._cache_attrs_current[key]
            except (AttributeError, KeyError):
                pass

    @property
    def attrs_current(self):
        """Return a map of the most current _Attrs on the _AttrMgr by key."""
        try:
            return self._cache_attrs_current
        except AttributeError:
            pass
            
        curr = {}
        deleted = set()
        attrs = self.attrs_accepted
        for attr in attrs:
            k = attr.key
            if k not in curr and k not in deleted:
                if attr.deleted:
                    deleted.add(k)
                else:
                    curr[k] = attr

        self._cache_attrs_current = curr
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
        return self.attrsq(accepted_only=False)

    @hybrid_property
    def tracked_data(self):
        return self.tracked.filter(_Attr.str_type == 'File')

    @hybrid_property
    def unjudged_tracked(self):
        return self.tracked.filter(_Change.judgment_timestamp == None).\
            filter(_Change.judgment_person_id == None)

    @hybrid_property
    def unjudged_tracked_not_data(self):
        return self.unjudged_tracked.filter(_Attr.str_type != 'File')

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
    def _filter_by_value_scalar(cls, expect_list, query, attr_class, value):
        """Produce filter for the given scalar value and attr_class."""
        if use_cache:
            query = query.\
                filter(CacheObjAttrs.attrvalue_id == attr_class.id)
        else:
            query = query.\
                filter(_Attr.id == attr_class.attr_id).\
                filter(_AttrValue.id == attr_class.id)
        if expect_list:
            elem_class = attr_class.__elem_class__
            # Only return obj ids whose _Attr.value matches.
            # This means that at least one of the List (attr_class) values must
            # match
            query = query.filter(attr_class.id == elem_class.attrvalue_id)
            try:
                value.match
                query = query.filter(
                    elem_class.value.op(
                        re_flags_to_pg_op(value))(value.pattern))
            except AttributeError:
                query = query.filter(elem_class.value == value)
        else:
            try:
                v = attr_class._coerce(None, value)
            except TypeError, e:
                log.debug('Failed to coerce: {}'.format(e))
                raise e
            if v != value:
                raise TypeError(
                    u'Coerced value {!r} for {} != {!r}'.format(
                        v, attr_class, value))
            try:
                value.match
                query = query.filter(
                    attr_class.value.op(
                        re_flags_to_pg_op(value))(value.pattern))
            except AttributeError:
                query = query.filter(attr_class.value == value)
        return query

    @classmethod
    def _filter_by_key_value(cls, query, attr_class, key, value):
        """Return filter of Obj.ids for _Attrs with given value and attr_class.

        """
        log.debug(u'filtering for {0!r} {1!r} = {2!r}'.format(
            attr_class, key, value))

        expect_list = type(attr_class.value) == AssociationProxy

        if use_cache:
            q = query.filter(CacheObjAttrs.key == key)
        else:
            q = query.filter(_Attr.key == key)
        if type(value) is list:
            # Match all the values in the list
            filters = []
            for v in value:
                try:
                    filters.append(
                        cls._filter_by_value_scalar(
                            expect_list, q, attr_class, v))
                except TypeError, e:
                    log.debug(e)
            if filters:
                q = filters[0].union(*filters[1:])
        else:
            try:
                q = cls._filter_by_value_scalar(
                    expect_list, q, attr_class, value)
            except TypeError, e:
                log.debug(e)
                return None
        return q

    @classmethod
    def filter_by_key_value(cls, query, key, value):
        """Return filter of Obj.ids for _Attr key and value."""
        attrclass = cls.attr_class(key)

        # If there are multiple possible types for the key, match for any one of
        # those types
        if type(attrclass) is list:
            filters = []
            for attr_class in attrclass:
                filters.append(
                    cls._filter_by_key_value(query, attr_class, key, value))
            filters = filter(None, filters)
            if filters:
                return filters[0].union(*filters[1:])
        return cls._filter_by_key_value(query, attrclass, key, value)

    @classmethod
    def _true_match(cls, obj_v, v):
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
    def get_by_attrs_true_match(cls, obj, dict, accepted_only=True):
        """Test resulting objs to ensure the most current values match."""
        if accepted_only:
            accepted = 'accepted'
        else:
            accepted = 'suggested or accepted'
        log.debug(
            u'verify {0} {1!r} match {2!r}'.format(accepted, obj, dict))
        if obj is None or (accepted_only and not obj.accepted):
            return False
            
        for key, v in dict.items():
            if key.find('.') >= 0:
                key, subkey = key.split('.', 1)
                obj_v = obj.get(key)

                if type(obj_v) == Participants:
                    for p in obj_v:
                        if vars(p)[subkey] == v:
                            return True
                return False
            else:
                obj_v = obj.get(key)
                if not cls._true_match(obj_v, v):
                    return False
        return True
    
    @classmethod
    def get_by_attrs_query(cls, dict={}, accepted_only=True):
        """Return query for cls instances that have _Attr state matching dict.

        When querying accepted_only state, the CacheObjAttrs can be used.

        """
        # TODO this should become an attribute on the mapped object so query
        # works normally
        base_query = cls.query()
        if accepted_only:
            base_query = base_query.filter(_Change.accepted == True)

        # filter the base query results for matching the given _Attr keys and
        # values
        if use_cache:
            base_filter_query = DBSession.query(CacheObjAttrs.obj_id)
        else:
            base_filter_query = DBSession.query(_Attr.obj_id)
        filters = []
        for k, v in dict.items():
            filters.append(cls.filter_by_key_value(base_filter_query, k, v))
        filters = filter(None, filters)
        if filters:
            log.debug(map(str, filters))
            intersection = filters[0].intersect(*filters[1:])
            query = base_query.filter(_Change.id.in_(intersection))
        else:
            query = base_query
        return query

    @classmethod
    def _get_all_by_attrs(cls, dict={}, accepted_only=True,
                          options=[], hook_objs=None):
        query = cls.get_by_attrs_query(dict, accepted_only)
        query = query.options(*options)
        objs = query.all()

        if hook_objs:
            hook_objs(objs)

        str_accepted_only = 'any accepted state'
        if accepted_only:
            str_accepted_only = 'accepted only'
        log.debug('found {0} {1} objs that match {2!r}'.format(
            len(objs), str_accepted_only, dict))
        if len(objs) > 4:
            log.warn(
                u'{} {} found with attrs query {}. True match will take '
                'a long time. Something is probably wrong the query produced '
                'by get_by_attrs_query.'.format(len(objs), cls, dict))
            log.debug(u'{!r}'.format(objs))
        return objs

    @classmethod
    def get_one_by_attrs(cls, dict={}, accepted_only=True, options=[],
                         hook_objs=None):
        """Return _AttrMgr whose _Attrs values match the given dictionary.

        accepted_only -- (bool) limits the returned _AttrMgrs to ones whose were
            accepted.

        """
        objs = cls._get_all_by_attrs(
            dict, accepted_only,
            options + [joinedload_all(
                'cache_obj_avs',
                CacheObjAttrs.attrvalue.of_type(_AttrValueUnicode),
            )], hook_objs)
        log.debug('got {0} objs by attrs'.format(len(objs)))
        for obj in objs:
            if cls.get_by_attrs_true_match(obj, dict, accepted_only):
                return obj
        return None

    @classmethod
    def get_all_by_attrs(
            cls, dict={}, accepted_only=True, options=[], hook_objs=None):
        """Return _AttrMgrs whose _Attrs values match the given dictionary.

        accepted_only -- (bool) limits the returned _AttrMgrs to ones whose were
            accepted.

        """
        objs = cls._get_all_by_attrs(
            dict, accepted_only,
            options + [joinedload_all(
                'cache_obj_avs',
                CacheObjAttrs.attrvalue.of_type(_AttrValueUnicode),
            )], hook_objs)
        return filter(
            lambda o: cls.get_by_attrs_true_match(
                o, dict, accepted_only), objs)


class _IDAttrMgr(_AttrMgr):
    """Mixin of _Attr tracking and id related methods.

    This is mixed in for Obj and Person because linking Person to changes causes
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
    def get_by_id(cls, id):
        try:
            return cls.query().filter(cls.id == id).first()
        except DataError, e:
            raise ValueError(unicode(e))

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

    @classmethod
    def query(cls, *args):
        """Return a query for this class on the global database session."""
        return super(Obj, cls).query(*args)

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

    Parameters::
    basin - imported from "internal"

    """
    __tablename__ = 'cruises'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'cruise',
    }

    @property
    def uid(self):
        expo = self.expocode
        if (not expo or not self.accepted or ' ' in expo or '/' in expo
                or '-' in expo):
            return super(Cruise, self).uid
        return expo

    @property
    def expocode(self):
        return self.get('expocode', None)

    @property
    def link(self):
        return self.get('link', None)

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
    def ports(self):
        return self.get('ports', [])

    @property
    def preliminary(self):
        """Tell whether the cruise is preliminary for the purposes of displaying
        a warning.

        A cruise may either be completely marked preliminary or preliminary
        attributes may cause it to be considered preliminary as well.

        """
        for attr in self.attrs_current.values():
            if attr.key.endswith('_status'):
                if 'preliminary' in attr.value:
                    return True
        return 'preliminary' in self.get('statuses', []) 

    @property
    def collections(self):
        try:
            return self._preload_objs['collections']
        except KeyError:
            collection_ids = self.get('collections', [])
            collections = preload_cached_avs(
                Collection, Collection.by_ids(collection_ids)).all()
            if not collections:
                collections = []
            self._preload_objs['collections'] = collections
            return collections

    @property
    def institutions(self):
        """These are institutions that are directly attached to the cruise.

        Application: Suppose a cruise were to be done by an institution but the
        PI was from a different one.

        """
        try:
            return self._preload_objs['institutions']
        except KeyError:
            institution_ids = self.get('institutions', [])
            institutions = preload_cached_avs(
                Institution, Institution.by_ids(institution_ids)).all()
            if not institutions:
                institutions = []
            self._preload_objs['institutions'] = institutions
            return institutions

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
        try:
            return self._preload_objs['ship']
        except KeyError:
            id = self.get('ship', None)
            ship = None
            if id:
                ship = Ship.query().get(id)
            self._preload_objs['ship'] = ship
            return ship

    @property
    def country(self):
        try:
            return self._preload_objs['country']
        except KeyError:
            id = self.get('country', None)
            country = None
            if id:
                country = Country.query().get(id)
            self._preload_objs['country'] = country
            return country

    @property
    def file_attrs(self):
        file_attrs = {}
        file_types = data_file_descriptions.keys()
        for ft in file_types:
            try:
                v = self.get_attr(ft)
                file_attrs[ft] = v
            except KeyError:
                pass
        return file_attrs

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
        if participants is None:
            # TODO unfortunately, this participants collection can't be directly
            # edited.
            return Participants()
        return participants

    @property
    def chief_scientists(self):
        try:
            return self.participants.with_role('Chief Scientist')
        except KeyError:
            return []

    @property
    def track(self):
        return self.get('track', None)

    @classmethod
    def filter_geo(cls, fn, cruises):
        return filter(lambda x: x.track and fn(x.track), cruises)

    @classmethod
    def get_all_by_expocode(cls, expocode):
        """Return all Cruises that match expocode.

        Multiple Cruises *may* have the same expocode. *Yes* it has happened.

        """
        return Cruise.get_all_by_attrs({'expocode': expocode})

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
            attrs = _Attr.query().\
                filter(_Attr.accepted==True).\
                filter(_Attr.key.in_(file_types)).\
                order_by(_Attr.judgment_timestamp.desc()).\
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
                _Attr.query(_Attr.obj_id).\
                    filter(_Attr.key == 'date_start').\
                    filter(_Attr.accepted)
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

    ('participants', [ParticipantsType, TextList]),

    ('parameter_informations', ParameterInformations), 

    ('data_suggestion', File, 'Data suggestion'),

    ('data_dir', Unicode, 'Import data directory'),
    ('archive', File, 'Import archive'),
    ]
for key, name in data_file_human_names.items():
    __cruise_allow_attrs.extend([
        (key, File, name),
        ('{0}_status'.format(key), TextList),
        ])
Cruise.allow_attrs(__cruise_allow_attrs)


class CruiseAssociate(object):
    """Mixin that provides a way to get the cruises associated with Obj."""

    # Cruise associate key is the _Attr key of Cruise on which the
    # CruiseAssociate ids are stored.
    cruise_associate_key = ''

    def _cruise_query_dict(self):
        return {self.cruise_associate_key: self.id}

    def _cruises_query(self, accepted_only=True):
        kvs = self._cruise_query_dict()
        query = Cruise.get_by_attrs_query(kvs, accepted_only)
        return (query, kvs)

    def cruises(self, limit=0, accepted_only=True):
        try:
            return self._preload_objs['cruises']
        except KeyError:
            pass
        query, kvs = self._cruises_query(accepted_only)
        order_by = Cruise.creation_timestamp
        if accepted_only:
            order_by = Cruise.judgment_timestamp
        query = query.order_by(order_by)
        if limit:
            query = query.limit(limit)

        cruises = preload_cached_avs(Cruise, query).all()
        disjoint_load_cruise_attrs(cruises)
        log.debug(kvs)
        log.debug(len(cruises))

        if len(cruises) > 500:
            log.error('Too many cruises')
            cruises = []

        cruises = filter(
            lambda c: Cruise.get_by_attrs_true_match(c, kvs, accepted_only),
            cruises)
        self._preload_objs['cruises'] = cruises
        return cruises

    def merge(self, signer, *mergees):
        """Merge this CruiseAssociate with other associates."""
        if not issubclass(type(signer), Person):
            raise TypeError('Signer is not a Person')
        if not all(issubclass(type(m), self.__class__) for m in mergees):
            raise TypeError('Not all mergees are %s' % self.__class__)

        self.merge_(signer, *mergees)

    def _mergee_cruises(self, *mergees):
        cruises = set()
        for mergee in mergees:
            mergee_cruises = set(mergee.cruises(accepted_only=False))
            cruises = cruises.union(mergee_cruises)
        log.debug(u'cruises with mergees: {0!r}'.format(cruises))
        return cruises

    def merge_(self, signer, *mergees):
        raise NotImplementedError()


class CruiseParticipantAssociate(CruiseAssociate):
    """Mixin that provides a way to get the cruises associated with 
    Participant.

    These are people or institutions.

    cruise_participant_associate_key should be set to 'person' or 'institution'
    by the subclass.

    """
    cruise_associate_key = 'participants'
    cruise_participant_associate_key = None

    def _cruise_query_dict(self):
        key = '{0}.{1}'.format(
            self.cruise_associate_key, self.cruise_participant_associate_key)
        return {key: self.id}

    def _cruises_query(self, accepted_only=True):
        kvs = self._cruise_query_dict()
        query = Cruise.get_by_attrs_query({}, accepted_only)
        attrvalue_ids = Participant.query(distinct(Participant.attrvalue_id)).\
            filter(Participant.__dict__[
                       self.cruise_participant_associate_key] == self.id)
        attr_ids = _AttrValue.query(_AttrValue.attr_id).\
            filter(_AttrValue.id.in_(attrvalue_ids))
        query = query.\
            filter(_Attr.obj_id == Obj.id).\
            filter(_Attr.id.in_(attr_ids))
        return (query, kvs)


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
        if not alpha or alpha == 2:
            return self.iso_3166_1_alpha_2
        elif alpha == 3:
            return self.iso_3166_1_alpha_3
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

    @property
    def people(self):
        return Person.get_all_by_attrs({'country': self.id})

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

    def __unicode__(self):
        try:
            return u'Country("{name}", {id})'.format(
                name=self.name, id=self.id)
        except AttributeError:
            return u'Country()'

    def to_nice_dict(self):
        """Returns a dict representation of the Country."""
        rep = super(Country, self).to_nice_dict()
        rep.update({
            'name': self.name,
            'iso_3166-1_alpha-2': self.iso_code(),
            'iso_3166-1_alpha-3': self.iso_code(3),
        })
        return rep


class _PersonPermissions(DBQueryable, Base):
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
        lazy='joined',
        cascade='all, delete, delete-orphan')
    permissions = association_proxy('permissions_', 'permission')

    # Legacy name parts
    name_last = Column(Unicode)
    name_first = Column(Unicode)

    cruise_participant_associate_key = 'person_id'

    __mapper_args__ = {
        'polymorphic_identity': 'person',
    }

    def __init__(self, **kwargs):
        super(Person, self).__init__(self, allow_blank=True, **kwargs)
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
        try:
            return self._preload_objs['institution']
        except KeyError:
            id = self.get('institution', None)
            institution = None
            if id:
                institution = Institution.query().get(id)
            self._preload_objs['institution'] = institution
            return institution

    @property
    def country(self):
        try:
            return self._preload_objs['country']
        except KeyError:
            id = self.get('country', None)
            country = None
            if id:
                country = Country.query().get(id)
            self._preload_objs['country'] = country
            return country

    def merge_(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]
        cs = _Change.query().\
            filter(_Change.creation_person_id.in_(mergee_ids)).all()
        for c in cs:
            c.creation_person_id = self.id
        cs = _Change.query().\
            filter(_Change.pending_person_id.in_(mergee_ids)).all()
        for c in cs:
            c.pending_person_id = self.id
        cs = _Change.query().\
            filter(_Change.judgment_person_id.in_(mergee_ids)).all()
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

    def __unicode__(self):
        return u'Person(identifier={0!r}, name={1!r})'.format(
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

    def __repr__(self):
        try:
            return u'{klass} ({names!r}, {id})'.format(
                klass=self.__class__.__name__,
                names=self.names, id=self.id)
        except AttributeError:
            return u'{klass} ()'.format(klass=self.__class__.__name__)
    

class Institution(CruiseParticipantAssociate, Obj):
    __tablename__ = 'institutions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'institution',
    }

    cruise_participant_associate_key = 'institution_id'

    @property
    def name(self):
        return self.get('name', None)

    def people(self):
        return Person.get_all_by_attrs({'institution': self.id})

    @property
    def country(self):
        try:
            return self._preload_objs['country']
        except KeyError:
            id = self.get('country', None)
            country = None
            if id:
                country = Country.query().get(id)
            self._preload_objs['country'] = country
            return country

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

    def __repr__(self):
        try:
            return u'Institution ({name!r})'.format(name=self.name)
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

    def merge_(self, signer, *mergees):
        mergee_ids = [m.id for m in mergees]

        attrs = _Attr.query().filter(_Attr.obj_id.in_(mergee_ids)).all()
        for attr in attrs:
            attr.obj_id = self.id

        for mergee in mergees:
            DBSession.delete(mergee)

    def __unicode__(self):
        return u'Ship({0})'.format(self.name)

    def to_nice_dict(self):
        """Returns a dict representation of the Ship."""
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

    __mapper_args__ = {
        'polymorphic_identity': 'collection',
    }

    cruise_associate_key = 'collections'

    @property
    def type(self):
        return self.get('type', None)

    @property
    def basins(self):
        return self.get('basins', [])

    def __repr__(self):
        try:
            return (u'{klass}({id}, names={names!r}, type={type!r}, '
                    'basins={basins!r})').format(
                klass=self.__class__.__name__, names=self.names,
                type=self.type, basins=self.basins, id=self.id)
        except AttributeError:
            return u'{klass}({id})'.format(
                klass=self.__class__.__name__, id=self.id)

    @classmethod
    def get_all_by_name(cls, name):
        """Returns all collections that match the given name.

        Parameters:
            name - either a string or a regular expression object
        
        """
        return self.get_all_by_attrs({'names': name})

    @classmethod
    def get_all_by_name(cls, name):
        return filter(
            lambda c: c.name == name,
            cls.get_all_by_attrs({'names': name}))

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
    """When AutoAcceptingObjs are saved, they are also accepted.

    The Obj will use the creator as the signer, obviating the step of accepting
    known good changes.

    """
    pass


@event.listens_for(AutoAcceptingObj, 'after_insert')
def _saved_auto_accepting_obj(mapper, connection, target):
    target.accept(target.creation_person)


argo_file_requests_for = Table('argo_file_requests_for', Base.metadata,
    Column('argo_file_id', ForeignKey('argo_files.id')),
    Column('request_for_id', ForeignKey('requests_for.id')),
    )


class ArgoFile(AutoAcceptingObj):
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

    file__id = Column('file_id', Integer, ForeignKey('fsfile.id'))
    file_ = relationship('FSFile', cascade='all, delete')

    link_cruise_id = Column(Integer, ForeignKey('cruises.id'))
    link_cruise = relationship(
        'Cruise', primaryjoin='ArgoFile.link_cruise_id == Cruise.id')
    link_attr_key = Column(Unicode)

    request_for_id = Column(Integer, ForeignKey('requests_for.id'))
    requests_for = relationship(
        'RequestFor', secondary=argo_file_requests_for, single_parent=True,
        uselist=True, cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'argo_file',
    }

    @property
    def file(self):
        """Return the file that the ArgoFile refers to."""
        if self.link_cruise:
            return self.link_cruise.get(self.link_attr_key, None)
        return self.file_

    @file.setter
    def file(self, f):
        self.file_ = f

    value = file

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
    
    Columns::

    date - the date of the submission
    stamp - unknown
    submitter - the name of the submitter. Format varies.
    line - the WOCE line number of the submission. May be other things.
    folder - the original folder name of the submission. This is mainly used to
        group the submission files together during import.
    files - a list of fs ids that store the actual files of the submission.
        Each file will have the original filename stored along with an attribute
        "old_submission" marked True.

    """
    __tablename__ = 'old_submissions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    date = Column(DateTime)
    stamp = Column(String(6))
    submitter = Column(Unicode)
    line = Column(Unicode)
    folder = Column(Unicode)
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

        # TODO this special case should never happen.
        SPECIAL CASE: This is set to True during legacy import because there
        is no way to determine it without human help.

    """
    __tablename__ = 'submissions'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    expocode = Column(Unicode)
    ship_name = Column(Unicode)
    line = Column(Unicode)
    action = Column(Unicode)
    cruise_date = Column(DateTime)
    type = Column(Unicode)
    attached_id = Column(Integer, ForeignKey('attrs.id'))
    attached = relationship('_Attr')

    file_id = Column('file_id', Integer, ForeignKey('fsfile.id'))
    file = relationship('FSFile', cascade='all, delete')

    request_for_id = Column(Integer, ForeignKey('requests_for.id'))
    request_for = relationship(
        'RequestFor', uselist=False, single_parent=True,
        cascade='all, delete, delete-orphan')

    __mapper_args__ = {
        'polymorphic_identity': 'submission',
    }

    @property
    def identifier(self):
        return self.expocode

    @property
    def value(self):
        return self.file

    @value.setter
    def value(self, o):
        self.file = o

    def cruises_from_identifier(self):
        try:
            return Cruise.get_all_by_expocode(self.expocode)
        except AttributeError:
            pass
        return []

    def attach(self, attr, signer):
        """Attaches the submission to a new _Attr and accepts the submission.

        """
        self.attached = attr
        self.accept(signer)

    @classmethod
    def unacknowledged(cls):
        """Return Submissions that have not yet been reviewed."""
        # TODO
        return []


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

    __mapper_args__ = {
        'polymorphic_identity': 'parameter',
    }

    @property
    def aliases(self):
        return self.get('aliases') or []

    @property
    def unit(self):
        try:
            return self._preload_objs['unit']
        except KeyError:
            id = self.get('unit')
            unit = None
            if id:
                unit = preload_cached_avs(Unit, Unit.query()).get(id)
            self._preload_objs['unit'] = unit
            return unit

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

    Attributes::

    name - The name for a unit
    mnemnoic - the WOCE mnemonic for the unit

    """
    __tablename__ = 'units'
    id = Column(Integer, ForeignKey('objs.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'unit',
    }


Unit.allow_attrs([
    ('name', Unicode),
    ('mnemonic', Unicode),
    ])


class ParameterOrder(Obj):
    """Define the class that a Parameter of which it is a member.

    Attributes::

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
        try:
            return self._preload_objs['order']
        except KeyError:
            ids = self.get('order', [])
            order = preload_cached_avs(Parameter, Parameter.by_ids(ids)).all()
            self._preload_objs['order'] = order
            return order


ParameterOrder.allow_attrs([
    ('name', Unicode),
    ('order', IDList),
    ])


def disjoint_load_list(objs, *attrs):
    """Disjointly load a list attribute after loading the objs.

    Similar in concept to
    http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DisjointEagerLoading

    """
    objs = filter(None, objs)

    avclass = None
    cache_avids = {}
    ids = set()
    for o in objs:
        if not o:
            continue
        if avclass is None:
            avclasses = set()
            for attr in attrs:
                avclass = o.attr_class(attr)
                if type(avclass) is list:
                    avclass = avclass[0]
                avclasses.add(avclass)
            if len(avclasses) > 1:
                raise TypeError(
                    u'attr classes must be the same to use the same load')
            avclass = avclasses.pop()
        for attr in attrs:
            try:
                cache = o.cache_obj_avs[attr]
            except KeyError:
                continue
            id = cache.attrvalue_id
            cache_avids[cache] = id
            ids.add(id)

    if avclass is None:
        return

    if not ids:
        return

    ids = sorted(list(ids))

    # TODO it may be faster to not filter on ids???
    avs_query = avclass.query().with_polymorphic('*').\
        filter(avclass.id.in_(ids))
    try:
        avs_query = avs_query.options(joinedload(avclass.values))
    except AttributeError:
        pass
    avs = avs_query.all()
    avs = dict([(a.id, a) for a in avs])

    for o in objs:
        for attr in attrs:
            try:
                cache = o.cache_obj_avs[attr]
            except KeyError:
                continue
            avid = cache_avids[cache]
            try:
                set_committed_value(cache, 'attrvalue', avs[avid])
            except KeyError:
                log.warn(u'Missing attrvalue {0} for {1}'.format(avid, o))


def disjoint_load_obj(objs, attr, klass, single=True):
    """Disjointly load attribute representing relationship for multiple Objs.

    Parameters::

    single - hints at whether the attr is a singular id or a list of ids for the
        object type.

    Similar in concept to
    http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DisjointEagerLoading
    but used for history tracking Obj's.

    """
    objs = filter(None, objs)

    obj_subobj_ids = {}
    ids = set()
    for o in objs:
        id = o.get(attr)
        obj_subobj_ids[o.id] = id
        if not id:
            continue
        if single:
            ids.add(id)
        else:
            ids |= set(id)
    ids = filter(None, ids)
    if not ids:
        return

    query = klass.query(klass.id, klass).filter(klass.id.in_(ids))
    subobjs = dict(preload_cached_avs(klass, query).all())

    for o in objs:
        subobj_ids = obj_subobj_ids[o.id]
        if subobj_ids is None:
            o._preload_objs[attr] = None
        else:
            if single:
                try:
                    objs = subobjs[subobj_ids]
                except KeyError:
                    objs = None
            else:
                objs = []
                for i in subobj_ids:
                    try:
                        objs.append(subobjs[i])
                    except KeyError:
                        # Don't load objects that don't exist
                        pass
            o._preload_objs[attr] = objs


known_subtypes = {
    Cruise: [
        _AttrValueUnicode, _AttrValueInteger, _AttrValueDatetime,
        _AttrValueListText, 
    ],
    Country: [
    ],
    Parameter: [
        _AttrValueUnicode, _AttrValueInteger,
        _AttrValueListDecimal, _AttrValueListText,
    ],
    Ship: [
        _AttrValueUnicode, _AttrValueInteger,
    ],
    Collection: [
        _AttrValueUnicode, _AttrValueListText, 
    ],
    Institution: [
        _AttrValueUnicode, _AttrValueInteger,
    ],
    Unit: [
        _AttrValueUnicode,
    ],
}


def preload_cached_avs(cls, query, subtypes=None, subquery=False):
    if subtypes is None:
        try:
            subtypes = known_subtypes[cls]
        except KeyError:
            subtypes = [] 
    av_alias = with_polymorphic(_AttrValue, subtypes, aliased=True)
    if subquery:
        options = [
            subqueryload_all(
                cls.cache_obj_avs,
                CacheObjAttrs.attrvalue.of_type(av_alias),
            ),
        ]
    else:
        options = [
            joinedload_all(
                cls.cache_obj_avs,
                CacheObjAttrs.attrvalue.of_type(av_alias),
            ),
        ]
    return query.options(*options)


def preload_person(cls, query):
    return query.options(
            noload(cls.cache_obj_avs),
            noload(cls.attrs),
            noload(cls.attrs_accepted),
        )
    

def disjoint_load_collection_attrs(collections):
    disjoint_load_list(collections, 'names')


def disjoint_load_cruise_attrs(cruises):
    disjoint_load_list(cruises, 'aliases')
    disjoint_load_list(cruises, 'track')
    disjoint_load_list(cruises, 'collections')
    disjoint_load_obj(cruises, 'collections', Collection, single=False)
    collections = set()
    for cruise in cruises:
        collections |= set(cruise.collections or [])
    disjoint_load_collection_attrs(collections)
    disjoint_load_list(cruises, 'participants')
    disjoint_load_obj(cruises, 'ship', Ship)
    disjoint_load_obj(cruises, 'country', Country)


def batch_load_cruises(cls, colls):
    cid_colls = dict([(coll.id, coll) for coll in colls])
    cids = cid_colls.keys()
    coll_cruises = {}
    # look in ID lists for these ids
    query = Cruise.query(Cruise).join(CacheObjAttrs).join(_AttrValueListID).\
        join(_AttrValueElemID).filter(_AttrValueElemID.value.in_(cids))
    cruises = preload_cached_avs(Cruise, query).all()
    disjoint_load_cruise_attrs(cruises)
    for cruise in cruises:
        for cid in cruise.get('collections'):
            if cid in cids:
                try:
                    coll_cruises[cid_colls[cid]].append(cruise)
                except KeyError:
                    coll_cruises[cid_colls[cid]] = [cruise]
    return coll_cruises


# Environment munging 

# Fix Postgis 2.0 bad function call for WKTSpatialElement. The function name
# changed from GeomFromText to ST_GeomFromText.
from geoalchemy.postgis import PGSpatialDialect
from geoalchemy.base import WKTSpatialElement, WKBSpatialElement
pg_funcs = PGSpatialDialect._PGSpatialDialect__functions
pg_funcs[WKTSpatialElement] = 'ST_GeomFromText'
pg_funcs[WKBSpatialElement] = 'ST_GeomFromBinary'

@event.listens_for(mapper, 'after_configured')
def _after_mapper_configured_reorder_tables():
    """Change the order of tables so that Person ends up behind Obj."""
    _Change.__mapper__._sorted_tables = _sorted_tables(_Change.__mapper__)
    CacheObjAttrs.check()
