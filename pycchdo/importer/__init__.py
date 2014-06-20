import argparse
from pprint import pformat
from datetime import datetime, time
import logging
from contextlib import contextmanager
from os import (geteuid, seteuid, setegid)
from pwd import getpwnam
import sys

from pyramid.paster import get_appsettings

from sqlalchemy import engine_from_config
from sqlalchemy.orm import lazyload

from libcchdo.log import LOG as libcchdo_log
from libcchdo.datadir.dl import AFTP, SFTP, pushd, lock, su

from pycchdo.models.serial import (
    Change, Note,
    DBSession, reset_database, reset_fs, 
    log as model_log,
    )
from pycchdo.models.search import SearchIndex
from pycchdo.models.filestorage import FSStore
from pycchdo.util import guess_mime_type
from pycchdo.log import getLogger, color_console, DEBUG, INFO, WARN, ERROR


__all__ = [
    'db_session', 'su', 'guess_mime_type', 'conn_dl', '_ustr2uni',
    '_date_to_datetime', 'Updater', 'pushd', 'lock', 'ProgressLog',]


log = getLogger(__name__)


def _is_root():
    return geteuid() is 0


def _drop_permissions(user):
    """Drop effective privileges.
    Need to re-escalate later when importing files.

    """
    # Group must be set first while permissions are available
    setegid(user.pw_gid)
    seteuid(user.pw_uid)
    log.info(u'De-escalated to {0} ({1})'.format(user.pw_gid, user.pw_uid))


@contextmanager
def conn_dl(ssh_host, *args, **kwargs):
    sftp = SFTP()
    with su():
        sftp.connect(ssh_host, 
            username='root',
            known_hosts='import_assets/known_hosts',
            key_file='import_assets/root_ssh_key')
    downloader = AFTP(sftp, *args, **kwargs)
    yield downloader


@contextmanager
def db_session(session):
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ustr2uni(s):
    #log.debug('ustr2uni: {}'.format(s))
    if type(s) is unicode:
        s = s.encode('raw_unicode_escape')
        try:
            return unicode(s, 'utf8')
        except UnicodeDecodeError:
            try:
                return unicode(s, 'raw_unicode_escape')
            except UnicodeDecodeError:
                return s
    if not s:
        return s
    return unicode(s, 'raw_unicode_escape')


def _date_to_datetime(date):
    return datetime.combine(date, time(0))


class Updater:
    def __init__(self, importer):
        self.importer = importer

    def create_accept(self, klass):
        return klass.create(self.importer).obj

    def note(self, obj, note, data_type=None, signer=None, discussion=False, ctime=None):
        if not note:
            return
        if signer is None:
            signer = self.importer
        new_note = Note(signer, _ustr2uni(note), data_type=data_type,
                        discussion=discussion)
        if ctime:
            new_note.ts_c = ctime
        if new_note not in obj._notes:
            obj._notes.append(new_note)
        return new_note

    def attr(self, obj, key, value, accept=True, note=None,
             note_data_type=None, creation_time=None, attr=None):
        if attr is None:
            attr = obj.changes_query().filter(Change.attr == key).\
                order_by(Change.ts_c.desc()).first()

        if attr:
            log.debug(u'modifying {0} to match {1}'.format(attr, value))
            attr._set_value(value)
            attr.accepted = accept
            if not accept:
                attr.p_j = None
                attr.ts_j = None
        else:
            log.debug(u'setting {0} {1} to {2}'.format(obj, key, value))
            if accept:
                attr = obj.set(self.importer, key, value)
            else:
                attr = obj.sugg(self.importer, key, value)

        if creation_time is not None:
            attr.ts_c = creation_time
        if note is not None:
            self.note(attr, note, note_data_type)
        return attr


class ProgressLog(object):
    def __init__(self, items, batchnum=100):
        self.length = len(items)
        self.batchnum = batchnum
        self.count = 0

    def log(self):
        self.count += 1
        if self.count % self.batchnum == 0:
            log.info('{0:d}/{1:d} = {2:f}'.format(
                self.count, self.length, float(self.count) / self.length))


argparser = argparse.ArgumentParser(description='Import CCHDO/Seahunt data')
argparser.add_argument(
    'paste_config',
    help='A Paste config .ini file that contains application, database, and '
         'search index settings')
argparser.add_argument(
    '-T', '--tabula-rasa', action='store_true', default=False,
    help='Whether to reset the pycchdo database before rebuilding. Useful for '
         'full rebuilds.')
argparser.add_argument(
    '--clear-index', action='store_true', default=False,
    help='Whether to clear the index.')
argparser.add_argument(
    '--clear-filesystem', action='store_true', default=False,
    help='Whether to reset the pycchdo file system before rebuilding. Useful '
         'for partial rebuilds.')
argparser.add_argument(
    '-C', '--skip_cchdo', action='store_true', default=False,
    help='Skip importing CCHDO data')
argparser.add_argument(
    '-S', '--skip_seahunt', action='store_true', default=False,
    help='Skip importing Seahunt data')
argparser.add_argument(
    '-I', '--skip_search_index', action='store_true', default=False,
    help='Skip building the search index')
argparser.add_argument(
    '-i', '--search_index_only', action='store_true', default=False,
    help='Only build the serach index')
argparser.add_argument(
    '-D', '--skip_downloads', action='store_true', default=False,
    help='Skip downloading files')
argparser.add_argument(
    '-X', '--clear_seahunt', action='store_true', default=False,
    help='Clear seahunt imports and exit.')
argparser.add_argument(
    '-F', '--files_only', action='store_true', default=False,
    help='Only import items that have files')
argparser.add_argument(
    '-G', '--no-files', action='store_true', default=False,
    help='Skip file imports')
argparser.add_argument(
    '-u', '--username', type=str, default='_www',
    help='The webserver username for import permissions (default: _www)')
argparser.add_argument(
    '-v', '--verbose', action='count', default=0,
    help='Verbosity by logging level.')
argparser.set_defaults(
    app_entry='app:pycchdo', sqlalchemy_pool_echo=False,sqlalchemy_echo=False)


def _read_config(args):
    args.settings = get_appsettings(args.paste_config + '#pycchdo')
    args.search_index_path = args.settings['search_index_path']


def do_import():
    # Import here because this module __init__ has to do some setup first.
    from pycchdo.importer import cchdo, seahunt
    args = argparser.parse_args()

    try:
        wwwuser = getpwnam(args.username)
    except Exception:
        log.error('No such user {}'.format(username))
        argparser.exit(1)

    libcchdo_log.setLevel(WARN)
    log.setLevel(ERROR)
    if args.verbose >= 0:
        log.setLevel(WARN)
    if args.verbose >= 1:
        log.setLevel(INFO)
    if args.verbose >= 2:
        log.setLevel(DEBUG)
    if args.verbose >= 3:
        args.sqlalchemy_pool_echo=True
    if args.verbose >= 4:
        args.sqlalchemy_echo=True
    if args.verbose >= 5:
        model_log.setLevel(DEBUG)

    if not args.skip_downloads:
        if _is_root():
            _drop_permissions(wwwuser)
        else:
            log.error(
                u'{0} must be run as root in order to import correct file '
                'ownerships. Alternatively, supply the -D/--skip_downloads '
                'flag.'.format(sys.argv[0]))
            argparser.exit(1)
    elif _is_root():
        _drop_permissions(wwwuser)

    try:
        _read_config(args)
    except KeyError:
        log.error(
            'importer requires an .ini file with sqlalchemy.url and '
            'search_index_path defined for {}'.format(args.app_entry))
        argparser.exit(1)

    log.info(u'importing with options\n{0}'.format(pformat(vars(args))))

    log.info(u"connecting (%s)" % args.settings['sqlalchemy.url'])
    pool_size = 10
    engine = engine_from_config(args.settings, echo=args.sqlalchemy_echo,
        pool_size=pool_size, max_overflow=0, pool_timeout=4,
        strategy='threadlocal')

    if args.sqlalchemy_pool_echo:
        pool_logger = logging.getLogger('sqlalchemy.pool')
        pool_logger.addHandler(log.handlers[0])
        pool_logger.setLevel(DEBUG)

    DBSession.configure(bind=engine)
    fsstore = FSStore(
        path=args.settings['file_system_path'],
        base_url='/',
    )

    if not args.search_index_only:

        if args.tabula_rasa:
            log.info('resetting db')
            reset_database(engine)

        if args.tabula_rasa or args.clear_filesystem:
            log.info(u'resetting fs')
            with su():
                reset_fs(fsstore)

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(wwwuser.pw_gid, pool_size, fsstore, args)

        if not args.skip_seahunt:
            seahunt.import_(wwwuser.pw_gid, fsstore, args)

    if not args.skip_search_index:
        log.info("indexing...")
        SearchIndex(args.search_index_path).rebuild_index(
            clear=args.tabula_rasa or args.clear_index)

    log.info("finished import.")
    return 0
