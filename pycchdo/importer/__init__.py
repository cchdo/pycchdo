import argparse
from datetime import datetime, time
import logging
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from os import getcwd, chdir, unlink, geteuid, getegid, seteuid, setegid
from pwd import getpwnam
import sys

from pyramid.paster import get_appsettings

import paramiko

from sqlalchemy import engine_from_config

from pycchdo import models
from pycchdo.models import DBSession, reset_database, _Attr, FSFile
from pycchdo.models.search import SearchIndex
from pycchdo.log import *


__all__ = [
    'implog', 'db_session', 'su', 'ssh_connect', 'ssh', 'sftp', 'sftp_dl',
    '_ustr2uni', '_date_to_datetime', 'copy_chunked', 'Updater', 'pushd',
    'lock', ]


implog = ColoredLogger(__name__)


def _is_root():
    return geteuid() is 0


def _drop_permissions(user):
    """Drop effective privileges.
    Need to re-escalate later when importing files.

    """
    implog.info(u'Drop permissions to {} {}'.format(user.pw_gid, user.pw_uid))
    # Group must be set first when permissions are available
    setegid(user.pw_gid)
    seteuid(user.pw_uid)


@contextmanager
def db_session(session):
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def pushd(dir):
    cwd = getcwd()
    chdir(dir)
    try:
        yield
    except Exception, e:
        implog.error('Error in pushd')
        implog.error(e)
    finally:
        chdir(cwd)


@contextmanager
def lock(lock=None):
    if lock:
        lock.acquire()
        implog.warn('lock acquired')
        try:
            yield
        finally:
            implog.warn('lock released')
            lock.release()
    else:
        yield


@contextmanager
def su(uid=0, gid=0, su_lock=None):
    """Temporarily switch effective uid and gid to provided values."""
    if su_lock:
        su_lock.acquire()
    try:
        seuid = geteuid()
        segid = getegid()
        if uid != 0 and seuid != 0:
            seteuid(0)
        setegid(gid)
        seteuid(uid)
    except OSError, e:
        implog.error('You must run this program as root because file '
                     'permissions need to be set.')
        argparser.exit(1)
    try:
        yield
    except Exception, e:
        implog.error(u'Error in su(%s, %s): %s' % (uid, gid, e))
    finally:
        if uid != 0:
            seteuid(0)
        setegid(segid)
        seteuid(seuid)
    if su_lock:
        su_lock.release()


def ssh_connect(ssh_host,
                known_hosts='import_assets/known_hosts',
                ssh_key_file='import_assets/root_ssh_key'):
    implog.info(u"Connecting (SSH) to %s" % ssh_host)
    ssh_client = paramiko.SSHClient()
    with su():
        try:
            ssh_client.load_host_keys(known_hosts)
        except IOError:
            implog.error(u'Need file %s with %s host key' % (known_hosts,
                                                             ssh_host))
            raise
        try:
            ssh_client.connect(ssh_host, username='root',
                               key_filename=ssh_key_file)
        except IOError:
            implog.error(u'Need file %s to SSH as remote root.' % ssh_key_file)
            implog.info(
                "Please generate an SSH key and put the public key in the "
                "remote host's root authorized keys. Remember that this will "
                "allow anyone with the generated private key to log in as the "
                "remote root so BE CAREFUL.")
            raise
    return ssh_client


@contextmanager
def ssh(ssh_host):
    ssh_client = None
    try:
        ssh_client = ssh_connect(ssh_host)
        yield ssh_client
    except paramiko.SSHException:
        implog.error(repr(e))
    finally:
        if ssh_client:
            ssh_client.close()


@contextmanager
def sftp(ssh_host):
    with ssh(ssh_host) as ssh_:
        sftp_ = None
        try:
            sftp_ = ssh_.open_sftp()
            yield (ssh_, sftp_)
        except paramiko.SSHException, e:
            implog.error(repr(e))
        finally:
            if sftp_:
                sftp_.close()


@contextmanager
def sftp_dl(sftp, filepath, dl_files=True):
    """Download a filepath from the remote server.

    Arguments:
    dl_files - denotes whether the file is actually downloaded

    """
    temp = NamedTemporaryFile(delete=False)
    downloaded = temp
    try:
        implog.info('Downloading %s' % filepath)
        if dl_files:
            sftp.get(filepath, temp.name)
        else:
            implog.info('Skipping download of %s' % filepath)
            downloaded = None
    except IOError, e:
        implog.warn("Unable to locate file on remote %s: %s" % (filepath, e))
        downloaded = None

    try:
        yield downloaded
    finally:
        try:
            unlink(temp.name)
        except OSError, e:
            implog.error('Unable to unlink tempfile: %s' % e)


def _ustr2uni(s):
    #implog.debug('ustr2uni: {}'.format(s))
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


def copy_chunked(infile, outfile, chunk=2**9):
    """Copies the file-like in to out in chunks."""
    data = infile.read(chunk)
    while data:
        outfile.write(data)
        data = infile.read(chunk)
    outfile.flush()
    outfile.seek(0)


class Updater:
    def __init__(self, importer):
        self.importer = importer

    def create_accept(self, klass):
        obj = klass(self.importer)
        obj.accept(self.importer)
        DBSession.add(obj)
        DBSession.flush()
        return obj

    def note(self, obj, note, data_type=None):
        if not note:
            return
        matched_note = False
        for n in obj.notes:
            if n.body == note:
                matched_note = True
                break
        implog.debug(self.importer)
        if not matched_note:
            obj.notes.append(
                models.Note(
                    self.importer, _ustr2uni(note), data_type=data_type))

    def attr(self, obj, key, value, accept=True, note=None,
             note_data_type=None, creation_time=None):
        DBSession.flush()
        attr = obj.attrsq(key, accepted_only=False).\
            order_by(_Attr.creation_timestamp).first()
        if attr:
            attr._set(value)
            attr.accepted = accept
        else:
            if accept:
                attr = obj.set_accept(key, value, self.importer)
            else:
                attr = obj.set(key, value, self.importer)
        if creation_time is not None:
            attr.creation_timestamp = creation_time
        if attr and note is not None:
            self.note(attr, note, note_data_type)
        return attr


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
    '-u', '--username', type=str, default='_www',
    help='The webserver username for import permissions (default: _www)')
argparser.add_argument(
    '-v', '--verbose', action='count', default=0,
    help='Verbosity by logging level.')
argparser.set_defaults(app_entry='app:pycchdo', sqlalchemy_echo=False)


def _read_config(args):
    args.settings = get_appsettings(args.paste_config + '#pycchdo')
    args.db_search_index_path = args.settings['db_search_index_path']


def do_import():
    from pycchdo.importer import cchdo, seahunt

    args = argparser.parse_args()

    try:
        wwwuser = getpwnam(args.username)
    except Exception:
        implog.error('No such user {}'.format(username))
        argparser.exit(1)

    if args.verbose >= 0:
        implog.setLevel(WARN)
    if args.verbose >= 1:
        implog.setLevel(INFO)
    if args.verbose >= 2:
        implog.setLevel(DEBUG)
    if args.verbose >= 3:
        args.sqlalchemy_echo=True

    if not args.skip_downloads:
        if _is_root():
            _drop_permissions(wwwuser)
        else:
            implog.error('{} must be run as root in order to import correct '
                         'file ownerships. Alternatively, supply the '
                         '-D/--skip_downloads flag.'.format(sys.argv[0]))
            argparser.exit(1)
    elif _is_root():
        _drop_permissions(wwwuser)

    try:
        _read_config(args)
    except KeyError:
        implog.error(
            'importer requires an .ini file with sqlalchemy.url and '
            'db_search_index_path defined for {}'.format(args.app_entry))
        argparser.exit(1)

    implog.info('importing with options %s' % args)

    implog.info("connect to pycchdo (%s)" % args.settings['sqlalchemy.url'])
    engine = engine_from_config(args.settings, echo=args.sqlalchemy_echo)
    DBSession.configure(bind=engine)
    implog.info('fs root: {}'.format(args.settings['fs_root']))
    FSFile.reconfig_fs_storage(args.settings['fs_root'])

    if not args.search_index_only:
        if args.tabula_rasa:
            implog.info('resetting database')
            models.reset_database(engine)

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(wwwuser.pw_gid, dl_files=not args.skip_downloads,
                          files_only=args.files_only)

        if not args.skip_seahunt:
            seahunt.import_(dl_files=not args.skip_downloads,
                            files_only=args.files_only)

    if not args.skip_search_index:
        SearchIndex(args.db_search_index_path).rebuild_index(
            clear=args.tabula_rasa)

    implog.info("finished import.")
    return 0
