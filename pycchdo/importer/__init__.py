import argparse
from datetime import datetime, time
import logging
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from os import getcwd, chdir, unlink, geteuid, getegid, seteuid, setegid
from pwd import getpwnam
from ConfigParser import (
    SafeConfigParser, NoSectionError, NoOptionError, Error as ConfigError)

import paramiko

from pymongo import DESCENDING

from pycchdo import models
from pycchdo.importer import cchdo, seahunt
from pycchdo.models.search import SearchIndex
from pycchdo.log import ColoredLogger


__all__ = ['implog', 'db_session', 'su', 'ssh_connect', 'ssh', 'sftp',
           'sftp_dl', '_ustr2uni', '_date_to_datetime', 'update_note',
           'update_attr', 'pushd', ]


implog = ColoredLogger(__name__)


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
        raise e
    try:
        yield
    except Exception, e:
        implog.error('Error in su(%s, %s): %s' % (uid, gid, e))
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
    implog.info("Connecting (SSH) to %s" % ssh_host)
    ssh_client = paramiko.SSHClient()
    with su():
        try:
            ssh_client.load_host_keys(known_hosts)
        except IOError:
            implog.error('Need file %s with %s host key' % (known_hosts,
                                                            ssh_host))
            raise
        try:
            ssh_client.connect(ssh_host, username='root',
                               key_filename=ssh_key_file)
        except IOError:
            implog.error('Need file %s to SSH as remote root.' % ssh_key_file)
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
    try:
        implog.info('Downloading %s' % filepath)
        if dl_files:
            sftp.get(filepath, temp.name)
            yield temp
        else:
            implog.info('Skipping download of %s' % filepath)
            yield None
    except IOError, e:
        implog.warn("Unable to locate file on remote %s: %s" % (filepath, e))
        yield None
    finally:
        try:
            unlink(temp.name)
        except OSError, e:
            implog.error('Unable to unlink tempfile: %s' % e)


def _ustr2uni(s):
    if type(s) is unicode:
        return s
    return unicode(s, 'unicode_escape')


def _date_to_datetime(date):
    return datetime.combine(date, time(0))


def update_note(obj, note, person, data_type=None):
    if not note:
        return
    matched_note = False
    for n in obj.notes:
        if n.body == note:
            matched_note = True
            break
    if not matched_note:
        obj.add_note(models.Note(person.id, _ustr2uni(note),
                                 data_type=data_type).save())


def update_attr(o, key, value, signer, accept=True, note=None,
                note_data_type=None, creation_time=None):
    attr = None
    try:
        if accept:
            a = o.get_attr(key)
        else:
            a = o.find_attr({'key': key, 'accepted': False},
                            sort=[('creation_stamp.timestamp', DESCENDING)])
            if a:
                a = models._Attr.map_mongo(a)
            else:
                a = None
        if a:
            a.set(key, value)
            a.accepted = accept
            a.save()
            attr = a
        else:
            if accept:
                attr = o.set_accept(key, value, signer)
            else:
                attr = o.set(key, value, signer)
    except KeyError:
        if accept:
            attr = o.set_accept(key, value, signer)
        else:
            attr = o.set(key, value, signer)
    if creation_time is not None:
        attr.creation_stamp.timestamp = creation_time
        attr.save()
    if attr and note is not None:
        update_note(attr, note, signer, note_data_type)
    return attr


argparser = argparse.ArgumentParser(description='Import CCHDO/Seahunt data')
argparser.add_argument(
    'paste_config',
    help='A Paste config .ini file that contains application, database, and '
         'search index settings')
argparser.add_argument(
    '-T', '--tabula-rasa', type=bool, default=False,
    help='Whether to reset the pycchdo database before rebuilding. Useful for '
         'full rebuilds.')
argparser.add_argument(
    '-C', '--skip_cchdo', type=bool, default=False,
    help='Skip importing CCHDO data')
argparser.add_argument(
    '-S', '--skip_seahunt', type=bool, default=False,
    help='Skip importing Seahunt data')
argparser.add_argument(
    '-I', '--skip_search_index', type=bool, default=False,
    help='Skip building the search index')
argparser.add_argument(
    '-i', '--search_index_only', type=bool, default=False,
    help='Only build the serach index')
argparser.add_argument(
    '-D', '--skip_downloads', type=bool, default=False,
    help='Skip downloading files')
argparser.add_argument(
    '-X', '--clear_seahunt', type=bool, default=False,
    help='Clear seahunt imports and exit.')
argparser.add_argument(
    '-F', '--files_only', type=bool, default=False,
    help='Only import items that have files')
argparser.add_argument(
    '-u', '--username', type=str, default='_www',
    help='The webserver username for import permissions')


def _is_root():
    return geteuid() is 0


def _drop_permissions(user):
    """Drop effective privileges.
    Need to re-escalate later when importing files.

    """
    seteuid(user.pw_uid)
    setegid(user.pw_gid)


def _read_config(args):
    config = SafeConfigParser()
    config.read(args.paste_config)
    app_entry = 'app:pycchdo'
    args.db_uri = config.get(app_entry, 'db_uri')
    args.db_search_index_path = config.get(
        app_entry, 'db_search_index_path')


def do_import():
    args = argparser.parse_args()

    username = '_www'
    try:
        wwwuser = getpwnam(username)
    except Exception:
        implog.error('No such user {}'.format(username))
        argparser.exit(1)

    if not args.skip_downloads:
        if not _is_root():
            _drop_permissions(wwwuser)
        else:
            implog.error('pycchdo importer must be run as root in order to '
                         'import correct file ownerships')
            argparser.exit(1)
    elif _is_root():
        _drop_permissions(wwwuser)

    try:
        _read_config(args)
    except ConfigError:
        implog.error('importer requires an .ini file with db_uri and '
                     'db_search_index_path defined for %s' % app_entry)
        argparser.exit(1)

    implog.info('importing with options %s' % args)

    implog.info("connect to pycchdo (%s)" % args.db_uri)
    engine = None
    DBSession.configure(bind=engine)

    if not args.search_index_only:
        if args.tabula_rasa:
            models._reset_database(engine)

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(import_gid, dl_files=not args.skip_downloads,
                          files_only=args.files_only)

        if not args.skip_seahunt:
            seahunt.import_(dl_files=not args.skip_downloads,
                            files_only=args.files_only)

    if not args.skip_search_index:
        SearchIndex(args.db_search_index_path).rebuild_index(
            clear=args.tabula_rasa)

    implog.info("finished import.")
    return 0
