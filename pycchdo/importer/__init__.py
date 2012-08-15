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

from pycchdo import models
from pycchdo.models import DBSession, reset_database, reset_fs, _Attr, FSFile
from pycchdo.models.models import log as model_log, DEBUG
from pycchdo.models.search import SearchIndex
from pycchdo.log import *


__all__ = [
    'implog', 'db_session', 'su', 'ssh_connect', 'ssh', 'sftp', 'sftp_dl',
    'sftp_dl_dir', 'copy_stat', 'Downloader', '_ustr2uni', '_date_to_datetime',
    'copy_chunked', 'Updater', 'pushd', 'lock', ]


implog = ColoredLogger(__name__)


def _is_root():
    return geteuid() is 0


def _drop_permissions(user):
    """Drop effective privileges.
    Need to re-escalate later when importing files.

    """
    # Group must be set first while permissions are available
    setegid(user.pw_gid)
    seteuid(user.pw_uid)
    implog.info(u'De-escalated to {0} ({1})'.format(user.pw_gid, user.pw_uid))


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
        #implog.debug(u'{0!r} acquired by {1!r}'.format(
        #    lock, current_thread().name))
        try:
            yield
        finally:
            #implog.debug(u'{0!r} released by {1!r}'.format(
            #    lock, current_thread().name))
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
            implog.error('You must run this program as root because file '
                         'permissions need to be set.')
            argparser.exit(1)
        try:
            yield
        except Exception, e:
            implog.error(u'Error while su(%s, %s)' % (uid, gid))
            raise e
        finally:
            if uid != 0:
                seteuid(0)
            setegid(segid)
            seteuid(seuid)


def ssh_connect(ssh_host,
                known_hosts='import_assets/known_hosts',
                ssh_key_file='import_assets/root_ssh_key'):
    implog.info(u"Connecting (SSH) to %s" % ssh_host)
    ssh_client = paramiko.SSHClient()
    with su():
        try:
            ssh_client.load_host_keys(known_hosts)
        except IOError, e:
            implog.error(u'Need file %s with %s host key' % (known_hosts,
                                                             ssh_host))
            raise e
        try:
            ssh_client.connect(ssh_host, username='root',
                               key_filename=ssh_key_file)
        except IOError, e:
            implog.error(u'Need file %s to SSH as remote root.' % ssh_key_file)
            implog.info(
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
            implog.info('Skipped.')
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


@contextmanager
def local_dl(filepath, su_lock, dl_files=True):
    """Download a filepath from the local filesystem.

    Arguments:
    dl_files - denotes whether the file is actually downloaded
    hardlink - whether to hard link the file instead of copying

    """
    with su(su_lock=su_lock):
        try:
            implog.info('Downloading %s' % filepath)
            downloaded = open(filepath, 'rb')
        except IOError, e:
            implog.warn(
                u"Unable to locate file on local %s: %s" % (filepath, e))
            downloaded = None
        try:
            yield downloaded
        finally:
            if downloaded:
                downloaded.close()


def copy_stat(downloader, stat, path):
    with su(su_lock=downloader.su_lock):
        try:
            chmod(path, stat.st_mode)
            chown(path, stat.st_uid, downloader.import_gid)
            utime(path, (stat.st_atime, stat.st_mtime))
        except IOError, e:
            implog.error(
                u'Unable to chmod downloaded path {0!r}:\n{1!r}'.format(
                    path, e))


def sftp_dl_dir(downloader, sftp, remotedir, localdir):
    try:
        with su(su_lock=downloader.su_lock):
            mkdir(localdir)
    except OSError, e:
        implog.debug('Unable to create directory %s %s' %
                     (os.path.basename(remotedir), e))
        return

    for file in sftp.listdir(remotedir):
        remote_path = os.path.join(remotedir, file)
        local_path = os.path.join(localdir, file)

        remote_stat = sftp.lstat(remote_path)

        if stat.S_ISDIR(sftp.lstat(remote_path).st_mode):
            sftp_dl_dir(downloader, sftp, remote_path, local_path)
        else:
            try:
                if downloader.dl_files:
                    with su(su_lock=downloader.su_lock):
                        sftp.get(remote_path, local_path)
            except IOError, e:
                implog.warning('Unable to download %s (%s)' % (remote_path, e))

        copy_stat(downloader, remote_stat, local_path)


def local_dl_dir(downloader, remotedir, localdir, hardlink=False):
    """Download a directory from the local filesystem

    Arguments:
    hardlink - whether to hard link the files in the directory instead of copying

    """
    try:
        with su(su_lock=downloader.su_lock):
            mkdir(localdir)
    except OSError, e:
        implog.error('Unable to create directory %s %s' %
                     (os.path.basename(remotedir), e))
        return

    for file in listdir(remotedir):
        remote_path = os.path.join(remotedir, file)
        local_path = os.path.join(localdir, file)

        remote_stat = lstat(remote_path)

        if stat.S_ISDIR(lstat(remote_path).st_mode):
            local_dl_dir(downloader, remote_path, local_path, hardlink)
        else:
            try:
                if downloader.dl_files:
                    with su(su_lock=downloader.su_lock):
                        if hardlink:
                            link(remote_path, local_path)
                        else:
                            shutil.copy2(remote_path, local_path)
            except IOError, e:
                implog.warning('Unable to copy %s (%s)' % (remote_path, e))

        copy_stat(downloader, remote_stat, local_path)


class Downloader(object):
    """Encapsulate the mechanics of downloading."""

    def __init__(self, dl_files, ssh_sftp, import_gid, local_rewriter=None,
                 su_lock=None, flush_lock=None):
        self.dl_files = dl_files
        self.set_ssh_sftp(ssh_sftp)
        self.import_gid = import_gid
        self.local_rewriter = local_rewriter
        self.su_lock = su_lock
        self.flush_lock = flush_lock

    def __copy__(self):
        return Downloader(
            self.dl_files, (self.ssh, self.sftp), self.import_gid,
            self.local_rewriter, self.su_lock, self.flush_lock)

    def set_ssh_sftp(self, ssh_sftp):
        self.ssh, self.sftp = ssh_sftp

    @contextmanager
    def dl(self, file_path):
        if self.local_rewriter:
            if not self.su_lock:
                implog.error(
                    u'Unable to find su lock when copying file. Cannot '
                    'continue without risk. Skipping.')
                yield None
                return
            rewritten_path = self.local_rewriter(file_path)
            implog.debug(
                u'rewrite {} to {}'.format(file_path, rewritten_path))
            with local_dl(rewritten_path, self.su_lock, self.dl_files) as x:
                implog.debug('downloaded')
                yield x
        else:
            with sftp_dl(self.sftp, file_path, self.dl_files) as x:
                implog.debug('downloaded')
                yield x

    def dl_dir(self, remote_dir_path, local_dir_path):
        if not self.su_lock:
            implog.error(
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
        attr = obj.attrsq(key, accepted_only=False).\
            order_by(_Attr.creation_timestamp).first()
        implog.debug(
            u'{0!r}.{1!r} ({2!r}) = {3!r}'.format(obj, key, attr, value))
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
argparser.set_defaults(
    app_entry='app:pycchdo', sqlalchemy_pool_echo=False,sqlalchemy_echo=False)


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

    implog.setLevel(ERROR)
    if args.verbose >= 0:
        implog.setLevel(WARN)
    if args.verbose >= 1:
        implog.setLevel(INFO)
    if args.verbose >= 2:
        implog.setLevel(DEBUG)
        model_log.setLevel(DEBUG)
    if args.verbose >= 3:
        args.sqlalchemy_pool_echo=True
    if args.verbose >= 4:
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

    implog.info(u'importing with options\n{0}'.format(pformat(vars(args))))

    implog.info(u"connecting (%s)" % args.settings['sqlalchemy.url'])
    engine = engine_from_config(args.settings, echo=args.sqlalchemy_echo,
        pool_size=6, max_overflow=0, pool_timeout=4, strategy='threadlocal')

    if args.sqlalchemy_pool_echo:
        pool_logger = logging.getLogger('sqlalchemy.pool')
        pool_logger.addHandler(implog.handlers[0])
        pool_logger.setLevel(logging.DEBUG)

    DBSession.configure(bind=engine)
    FSFile.reconfig_fs_storage(args.settings['fs_root'])

    if not args.search_index_only:

        if args.tabula_rasa:
            implog.info('resetting database and fs')
            reset_database(engine)
            with su():
                reset_fs()

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(wwwuser.pw_gid, args)

        if not args.skip_seahunt:
            seahunt.import_(args)

    if not args.skip_search_index:
        SearchIndex(args.db_search_index_path).rebuild_index(
            clear=args.tabula_rasa)

    implog.info("finished import.")
    return 0
