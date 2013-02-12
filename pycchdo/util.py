from datetime import datetime
import socket
import mimetypes

from StringIO import StringIO as pyStringIO
import transaction
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO

from sqlalchemy import util
from sqlalchemy.sql import visitors
from sqlalchemy.util import topological


def flatten(l):
    return [item for sublist in l for item in sublist]


def str2uni(x):
    if type(x) is str:
        return unicode(x)
    return x


def guess_mime_type(filename):
    mime = mimetypes.guess_type(filename)[0]
    if not mime:
        mime = 'application/octet-stream'
    return mime


def listlike(x):
    try:
        len(x)
        x.append
        return True
    except (TypeError, AttributeError):
        return False


def timestamp_now():
    """Create a datetime.datetime representing Now."""
    return datetime.utcnow()


def re_flags_to_pg_op(regexp):
    """Basic conversion from RegExp flags to Postgresql regexp operators."""
    op = '~'
    if regexp.flags & re.IGNORECASE == re.IGNORECASE:
        op = '~*'
    return op


def is_valid_ipv4(ip):
    try:
        return socket.inet_pton(socket.AF_INET, ip)
    except AttributeError: # no inet_pton here, sorry
        try:
            return socket.inet_aton(ip)
        except socket.error:
            return False
    except TypeError:
        return False
    except socket.error:
        return False


def is_valid_ipv6(ip):
    try:
        return socket.inet_pton(socket.AF_INET6, ip)
    except TypeError:
        return False
    except socket.error:
        return False


def is_valid_ip(ip):
    return is_valid_ipv4(ip) or is_valid_ipv6(ip)


class FileProxyMixin(object):
    """A mixin class used to forward file methods to an underlaying file object.
    The internal file object has to be called "file"::

        class FileProxy(FileProxyMixin):
            def __init__(self, file):
                self.file = file

    Snagged from django.core.files.utils

    """

    encoding = property(lambda self: self.file.encoding)
    fileno = property(lambda self: self.file.fileno)
    flush = property(lambda self: self.file.flush)
    isatty = property(lambda self: self.file.isatty)
    newlines = property(lambda self: self.file.newlines)
    read = property(lambda self: self.file.read)
    readinto = property(lambda self: self.file.readinto)
    readline = property(lambda self: self.file.readline)
    readlines = property(lambda self: self.file.readlines)
    seek = property(lambda self: self.file.seek)
    softspace = property(lambda self: self.file.softspace)
    tell = property(lambda self: self.file.tell)
    truncate = property(lambda self: self.file.truncate)
    write = property(lambda self: self.file.write)
    writelines = property(lambda self: self.file.writelines)
    xreadlines = property(lambda self: self.file.xreadlines)

    @property
    def closed(self):
        try:
            return self.file.closed
        except AttributeError:
            return False

    def __iter__(self):
        return iter(self.file)


class MemFile(pyStringIO):
    def __init__(self, content, filename):
        pyStringIO.__init__(self, content)
        self.name = filename
        self.flush()

    @property
    def filename(self):
        return self.name

    @property
    def size(self):
        return len(self.getvalue())

    def __repr__(self):
        return u'MemFile({0!r:<10}, {1!r})'.format(self.getvalue(), self.name)


def _sorted_tables(self):
    """Override for sqlalchemy.orm.mapper.

    Make any changes in _sort_tables.

    This is a direct copy from sqlalchemy.orm.mapper with the only change being
    the call to _sort_tables to point to the one in this module. 
    TODO safely inject _sort_tables into sqlalchemy.orm.mapper to remove code
    duplication.

    """
    table_to_mapper = {}
    for mapper in self.base_mapper.self_and_descendants:
        for t in mapper.tables:
            table_to_mapper[t] = mapper

    sorted_ = _sort_tables(table_to_mapper.iterkeys())
    ret = util.OrderedDict()
    for t in sorted_:
        ret[t] = table_to_mapper[t]
    return ret


def _munge_sort_order(sorted_tables):
    """Swap _Change to come before Person.

    Make _Change come before Person in the foreign key ordering.

    """
    table_person = None
    table_obj = None
    for table in sorted_tables:
        if table.name == 'people':
            table_person = table
        if table.name == 'objs':
            table_obj = table
        if table_person is not None and table_obj is not None:
            break

    if table_person is None or table_obj is None:
        return

    i_person = sorted_tables.index(table_person)
    i_obj = sorted_tables.index(table_obj)
    if i_person < i_obj:
        sorted_tables.remove(table_person)
        sorted_tables.insert(i_obj, table_person)


def _sort_tables(tables):
    """Sort a collection of Table objects in order of their foreign-key dependency.

    This is a copy of sqlalchemy.sql.util.sort_tables with an additional call to
    _munge_sort_order.

    """
    tables = list(tables)
    tuples = []
    def visit_foreign_key(fkey):
        if fkey.use_alter:
            return
        parent_table = fkey.column.table
        if parent_table in tables:
            child_table = fkey.parent.table
            if parent_table is not child_table:
                tuples.append((parent_table, child_table))

    for table in tables:
        visitors.traverse(table, 
                            {'schema_visitor':True}, 
                            {'foreign_key':visit_foreign_key})

        tuples.extend(
            [parent, table] for parent in table._extra_dependencies
        )

    sorted_tables = list(topological.sort(tuples, tables))

    _munge_sort_order(sorted_tables)

    return sorted_tables
