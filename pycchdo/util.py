from datetime import datetime
import socket
import mimetypes
from logging import getLogger

from StringIO import StringIO as pyStringIO
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO

import transaction

from sqlalchemy.engine import reflection
from sqlalchemy.schema import (
    MetaData,
    Table,
    DropTable, DropSchema,
    ForeignKeyConstraint,
    DropConstraint,
    )


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


def collapse_dict(d, n=None):
    """Collapses a dict recursively into the value n if it has no values that
    are not n."""
    if isinstance(d, dict):
        e = {}
        for k, v in d.items():
            # recurse into sub-dicts
            v = collapse_dict(v, n)
            if v != n:
                e[k] = v
        if len(e) < 1:
            return n
        return e
    elif isinstance(d, list):
        e = filter(lambda x: x != n, [collapse_dict(w, n) for w in d])
        if len(e) == 0:
            return n
        return e
    else:
        return d


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


def reenable_logs():
    """Renable logs that were disabled by paste fileConfig."""
    rloggers = getLogger().manager.loggerDict
    for logkey in rloggers.keys():
        if logkey.startswith('pycchdo.'):
            rloggers[logkey].disabled = 0


def patch_pyramid_exclog():
    """Patch pyramid_exclog to avoid logging url log."""
    try:
        import pyramid_exclog
    except ImportError:
        return

    _orig_exclog_tween_factory = pyramid_exclog.exclog_tween_factory
    def exclog_tween_factory(handler, registry):
        _orig_exclog_tween = _orig_exclog_tween_factory(handler, registry)
        def exclog_tween(request, **kwargs):
            try:
                request.path_info
            except UnicodeDecodeError:
                request.path_info = ''
            return _orig_exclog_tween(request, **kwargs)
        return exclog_tween
    pyramid_exclog.exclog_tween_factory = exclog_tween_factory


def drop_everything(engine):
    """Drop all tables.

    Copied from recipe 2013-09-04: 
    http://www.sqlalchemy.org/trac/wiki/UsageRecipes/DropEverything

    """
    conn = engine.connect()

    # the transaction only applies if the DB supports
    # transactional DDL, i.e. Postgresql, MS SQL Server
    trans = conn.begin()

    inspector = reflection.Inspector.from_engine(engine)

    # gather all data first before dropping anything.
    # some DBs lock after things have been dropped in 
    # a transaction.

    metadata = MetaData()

    illegal_tables = ['spatial_ref_sys']

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(
                ForeignKeyConstraint((),(),name=fk['name'])
                )
        if table_name not in illegal_tables:
            t = Table(table_name,metadata,*fks)
            tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    DropSchema(metadata.schema)

    trans.commit()
