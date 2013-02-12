import argparse
from pprint import pformat
from datetime import datetime, time
import logging
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
import shutil
import stat
from os import (
    getcwd, chdir, unlink, geteuid, getegid, seteuid, setegid, lstat,
    listdir, readlink, mkdir, chmod, chown, utime, link
    )
import os.path
from pwd import getpwnam
import sys
from threading import current_thread

from pyramid.paster import get_appsettings

import paramiko

from sqlalchemy import engine_from_config
from sqlalchemy.orm import lazyload

from pycchdo import models
from pycchdo.models import (
    DBSession, reset_database, reset_fs, _Attr, FSFile,
    log as model_log,
    )
from pycchdo.models.search import SearchIndex
from pycchdo.models.filestorage import copy_chunked
from pycchdo.util import guess_mime_type
from pycchdo.log import ColoredLogger, DEBUG, INFO, WARN, ERROR


__all__ = [
    'log', 'db_session', 'su', 'ssh_connect', 'ssh', 'sftp', 'sftp_dl',
    'sftp_dl_dir', 'set_stat', 'guess_mime_type', 'Downloader', '_ustr2uni',
    '_date_to_datetime', 'copy_chunked', 'Updater', 'pushd', 'lock', ]


log = ColoredLogger(__name__)


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
        log.error('Error in pushd')
        log.error(e)
    finally:
        chdir(cwd)


@contextmanager
def lock(lock=None):
    if lock:
        log.debug(u'{0} requested by {1}'.format(lock, current_thread().name))
        lock.acquire()
        log.debug(u'{0} acquired by {1}'.format(
            lock, current_thread().name))
        try:
            yield
        finally:
            log.debug(u'{0} released by {1}'.format(
                lock, current_thread().name))
            lock.release()
    else:
        yield


@contextmanager
def su(uid=0, gid=0, su_lock=None):
    """Temporarily switch effective uid and gid to provided values."""
    with lock(su_lock):
        try:
            seuid = geteuid()
            segid = getegid()
            if uid != 0 and seuid != 0:
                seteuid(0)
            setegid(gid)
            seteuid(uid)
        except OSError, e:
            log.error('You must run this program as root because file '
                         'permissions need to be set.')
            argparser.exit(1)
        try:
            yield
        except Exception, e:
            log.error(u'Error while su(%s, %s)' % (uid, gid))
            raise e
        finally:
            if uid != 0:
                seteuid(0)
            setegid(segid)
            seteuid(seuid)


def ssh_connect(ssh_host,
                known_hosts='import_assets/known_hosts',
                ssh_key_file='import_assets/root_ssh_key'):
    log.info(u"Connecting (SSH) to %s" % ssh_host)
    ssh_client = paramiko.SSHClient()
    with su():
        try:
            ssh_client.load_host_keys(known_hosts)
        except IOError, e:
            log.error(u'Need file %s with %s host key' % (known_hosts,
                                                             ssh_host))
            raise e
        try:
            ssh_client.connect(ssh_host, username='root',
                               key_filename=ssh_key_file)
        except IOError, e:
            log.error(u'Need file %s to SSH as remote root.' % ssh_key_file)
            log.info(
                "Please generate an SSH key and put the public key in the "
                "remote host's root authorized keys. Remember that this will "
                "allow anyone with the generated private key to log in as the "
                "remote root so BE CAREFUL.")
            raise e
    return ssh_client


@contextmanager
def ssh(ssh_host):
    ssh_client = None
    try:
        ssh_client = ssh_connect(ssh_host)
        yield ssh_client
    except paramiko.SSHException:
        log.error(repr(e))
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
            log.error(repr(e))
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
        log.info('downloading %s' % filepath)
        if dl_files:
            sftp.get(filepath, temp.name)
        else:
            log.info('Skipped.')
            downloaded = None
    except IOError, e:
        log.warn("Unable to locate file on remote %s: %s" % (filepath, e))
        downloaded = None

    try:
        yield downloaded
    finally:
        try:
            unlink(temp.name)
        except OSError, e:
            log.error('Unable to unlink tempfile: %s' % e)


@contextmanager
def local_dl(filepath, su_lock, dl_files=True):
    """Download a filepath from the local filesystem.

    Arguments:
    dl_files - denotes whether the file is actually downloaded
    hardlink - whether to hard link the file instead of copying

    """
    with su(su_lock=su_lock):
        try:
            log.info('downloading {0}'.format(filepath))
            downloaded = open(filepath, 'rb')
        except IOError, e:
            log.warn(u"Unable to locate file on local {0}:\n{1!r}".format(
                filepath, e))
            downloaded = None
        try:
            yield downloaded
        finally:
            if downloaded:
                downloaded.close()


def set_stat(downloader, stat, path):
    with su(su_lock=downloader.su_lock):
        try:
            chmod(path, stat.st_mode)
            chown(path, stat.st_uid, downloader.import_gid)
            utime(path, (stat.st_atime, stat.st_mtime))
        except (OSError, IOError), e:
            log.error(u'unable to chmod {0!r}:\n{1!r}'.format(path, e))


def _dl_dir(downloader, remotedir, localdir, listdir, lstat, copy):
    if not downloader.dl_files:
        log.info(u'skipping download as requested')
        return
    log.info(u'downloading dir {0} to {1}'.format(remotedir, localdir))
    try:
        with su(su_lock=downloader.su_lock):
            mkdir(localdir)
    except OSError, e:
        log.error(u'Unable to create directory {0}:\n{1!r}'.format(
            os.path.basename(remotedir), e))
        return

    remote_dir_stat = lstat(remotedir)

    try:
        with su(su_lock=downloader.su_lock):
            listing = listdir(remotedir)
    except OSError, e:
        log.error(u'Unable to list directory {0}: {1!r}'.format(remotedir, e))
        return

    for file in listing:
        remote_path = os.path.join(remotedir, file)
        local_path = os.path.join(localdir, file)

        try:
            with su(su_lock=downloader.su_lock):
                remote_stat = lstat(remote_path)
        except OSError, e:
            log.error(u'Unable to get stat for {0}'.format(remote_path))
            continue

        if stat.S_ISDIR(remote_stat.st_mode):
            _dl_dir(downloader, remote_path, local_path, listdir, lstat, copy)
        else:
            try:
                with su(su_lock=downloader.su_lock):
                    copy(remote_path, local_path)
            except IOError, e:
                log.warning('unable to copy %s (%s)' % (remote_path, e))

        set_stat(downloader, remote_stat, local_path)
    set_stat(downloader, remote_dir_stat, localdir)


def sftp_copy_dir(remote_path, local_path):
    sftp.get(remote_path, local_path)


def sftp_dl_dir(downloader, sftp, remotedir, localdir):
    log.info(u'sftp copying {0}'.format(remotedir))
    _dl_dir(downloader, remotedir, localdir, sftp.listdir, sftp.lstat,
            sftp_copy_dir)


def local_copy_dir(remote_path, local_path, hardlink=False):
    if hardlink:
        link(remote_path, local_path)
    else:
        shutil.copy2(remote_path, local_path)


def local_dl_dir(downloader, remotedir, localdir, hardlink=False):
    """Download a directory from the local filesystem

    Arguments:
    hardlink - whether to hard link the files in the directory instead of copying

    """
    log.info(u'locally copying {0}'.format(remotedir))
    _dl_dir(downloader, remotedir, localdir, listdir, lstat, local_copy_dir)


class Downloader(object):
    """Encapsulate the mechanics of downloading."""

    def __init__(self, dl_files, ssh_sftp, import_gid, local_rewriter=None,
                 su_lock=None, sesh_lock=None):
        self.dl_files = dl_files
        self.set_ssh_sftp(ssh_sftp)
        self.import_gid = import_gid
        self.local_rewriter = local_rewriter
        self.su_lock = su_lock
        self.sesh_lock = sesh_lock

    def __copy__(self):
        return Downloader(
            self.dl_files, (self.ssh, self.sftp), self.import_gid,
            self.local_rewriter, self.su_lock, self.sesh_lock)

    def set_ssh_sftp(self, ssh_sftp):
        self.ssh, self.sftp = ssh_sftp

    @contextmanager
    def dl(self, file_path):
        if self.local_rewriter:
            if not self.su_lock:
                log.error(
                    u'Unable to find su lock when copying file. Cannot '
                    'continue without risk. Skipping.')
                yield None
                return
            rewritten_path = self.local_rewriter(file_path)
            log.debug(
                u'rewrite {} to {}'.format(file_path, rewritten_path))
            with local_dl(rewritten_path, self.su_lock, self.dl_files) as x:
                log.debug('downloaded')
                yield x
        else:
            with sftp_dl(self.sftp, file_path, self.dl_files) as x:
                log.debug('downloaded')
                yield x

    def dl_dir(self, remote_dir_path, local_dir_path):
        if not self.su_lock:
            log.error(
                u'Unable to find su lock when copying directory. Cannot '
                'continue without risk. Skipping.')
            return
        if self.local_rewriter:
            local_dl_dir(self, self.local_rewriter(remote_dir_path), local_dir_path)
        else:
            sftp_dl_dir(self, self.sftp, remote_dir_path, local_dir_path)

    def lstat(self, path):
        if self.local_rewriter:
            return lstat(self.local_rewriter(path))
        else:
            return self.sftp.lstat(path)

    def mtime(self, path):
        return datetime.fromtimestamp(self.lstat(path).st_mtime)

    def listdir(self, dir_path):
        if self.local_rewriter:
            return listdir(self.local_rewriter(dir_path))
        else:
            return self.sftp.listdir(dir_path)

    def readlink(self, path):
        if self.local_rewriter:
            return readlink(self.local_rewriter(path))
        else:
            return self.sftp.readlink(path)


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
        obj = klass(self.importer)
        obj.accept(self.importer)
        DBSession.add(obj)
        DBSession.flush()
        return obj

    def note(self, obj, note, data_type=None, creation_timestamp=None):
        if not note:
            return
        matched_note = False
        for n in obj.notes:
            if n.body == note:
                matched_note = True
                break
        if not matched_note:
            note = models.Note(
                self.importer, _ustr2uni(note), data_type=data_type)
            if creation_timestamp:
                note.creation_timestamp = creation_timestamp
            obj.notes.append(note)

    def attr(self, obj, key, value, accept=True, note=None,
             note_data_type=None, creation_time=None, attr=None):
        log.debug('setting {0!r}.{1!r} to {2!r}'.format(obj, key, value))
        if attr is None:
            attr = obj.attrsq(key, accepted_only=False).\
                order_by(_Attr.creation_timestamp).\
                options(lazyload('vs')).\
                first()
            log.debug(
                u'finding {0!r}.{1!r} ({2!r}) = {3!r}'.format(
                    obj, key, attr, value))
        else:
            log.debug(
                u'using   {0!r}.{1!r} ({2!r}) = {3!r}'.format(
                    obj, key, attr, value))
        if attr:
            log.debug(u'modifying {0} {1} to match {2}'.format(
                attr, attr.value, value))
            if attr.value != value:
                attr._set(value)
                log.debug(u'done setting')
            log.debug(u'setting accept to {0}'.format(accept))
            attr.accepted = accept
            if not accept:
                attr.judgment_person = None
                attr.judgment_timestamp = None
        else:
            if accept:
                attr = obj.set_accept(key, value, self.importer)
            else:
                attr = obj.set(key, value, self.importer)
        if attr:
            if creation_time is not None:
                attr.creation_timestamp = creation_time
            if note is not None:
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
    '-u', '--username', type=str, default='_www',
    help='The webserver username for import permissions (default: _www)')
argparser.add_argument(
    '-v', '--verbose', action='count', default=0,
    help='Verbosity by logging level.')
argparser.set_defaults(
    app_entry='app:pycchdo', sqlalchemy_pool_echo=False,sqlalchemy_echo=False)


def _read_config(args):
    args.settings = get_appsettings(args.paste_config + '#pycchdo')
    args.db_search_index_path = args.settings['db_search_index_path']


def do_import():
    # Import here because this module __init__ has to do some setup first.
    from pycchdo.importer import cchdo, seahunt
    args = argparser.parse_args()

    try:
        wwwuser = getpwnam(args.username)
    except Exception:
        log.error('No such user {}'.format(username))
        argparser.exit(1)

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
            'db_search_index_path defined for {}'.format(args.app_entry))
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
        pool_logger.setLevel(logging.DEBUG)

    DBSession.configure(bind=engine)
    FSFile.fs_setup(root=args.settings['fs_root'])

    if not args.search_index_only:

        if args.tabula_rasa:
            log.info('resetting db')
            reset_database(engine)

        if args.tabula_rasa or args.clear_filesystem:
            log.info(u'resetting fs')
            with su():
                reset_fs()

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(wwwuser.pw_gid, pool_size, args)

        if not args.skip_seahunt:
            seahunt.import_(args)

    if not args.skip_search_index:
        log.info("indexing...")
        SearchIndex(args.db_search_index_path).rebuild_index(
            clear=args.tabula_rasa)

    log.info("finished import.")
    return 0
