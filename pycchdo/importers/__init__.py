import datetime
import logging
from contextlib import contextmanager
import tempfile
import os

import paramiko

from pymongo import DESCENDING

from pycchdo import models


__all__ = ['implog', 'db_session', 'su', 'ssh_connect', 'ssh', 'sftp',
           'sftp_dl', '_ustr2uni', '_date_to_datetime', 'update_note',
           'update_attr', 'pushd', ]


implog = logging.getLogger('pycchdo.import')
implog.setLevel(logging.DEBUG)
logging.basicConfig(format='%(levelname)s %(asctime)-15s %(message)s')


@contextmanager
def db_session(session):
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def pushd(dir):
    cwd = os.getcwd()
    os.chdir(dir)
    try:
        yield
    except Exception, e:
        implog.error('Error in pushd')
        implog.error(e)
    finally:
        os.chdir(cwd)


@contextmanager
def su(uid=0, gid=0, su_lock=None):
    """ Temporarily switch effective uid and gid to provided values """
    if su_lock:
        su_lock.acquire()
    try:
        seuid = os.geteuid()
        segid = os.getegid()
        if uid != 0 and seuid != 0:
            os.seteuid(0)
        os.setegid(gid)
        os.seteuid(uid)
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
            os.seteuid(0)
        os.setegid(segid)
        os.seteuid(seuid)
    if su_lock:
        su_lock.release()


def ssh_connect(ssh_host,
                known_hosts='pycchdo_import/known_hosts',
                ssh_key_file='pycchdo_import/root_ssh_key'):
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
    """ Download a filepath from the remote server
        dl_files - denotes whether the file is actually downloaded
    """
    temp = tempfile.NamedTemporaryFile(delete=False)
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
            os.unlink(temp.name)
        except OSError, e:
            implog.error('Unable to unlink tempfile: %s' % e)


def _ustr2uni(s):
    if type(s) is unicode:
        return s
    return unicode(s, 'unicode_escape')


def _date_to_datetime(date):
    return datetime.datetime.combine(date, datetime.time(0))


def update_note(obj, note, person, data_type=None):
    if not note:
        return
    matched_note = False
    for n in obj.notes:
        if n.body == note:
            matched_note = True
            break
    if not matched_note:
        obj.add_note(models.Note(person, _ustr2uni(note),
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
