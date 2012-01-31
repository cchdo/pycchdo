import datetime
import logging
from contextlib import contextmanager
import tempfile
import os

import paramiko

from pymongo import DESCENDING

from pycchdo import models


__all__ = ['implog', 'su', 'ssh_connect', 'ssh', 'sftp', 'sftp_dl', '_ustr2uni',
           '_date_to_datetime', 'update_attr', ]


implog = logging.getLogger('pycchdo.import')
implog.setLevel(logging.DEBUG)
imploghandler = logging.StreamHandler()
imploghandler.setFormatter(logging.Formatter(
    '%(levelname)s %(asctime)-15s %(message)s'))
implog.addHandler(imploghandler)


@contextmanager
def su(uid=0, gid=0):
    """ Temporarily switch effective uid and gid to provided values """
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


def ssh_connect(ssh_host):
    implog.info("Connecting (SSH) to %s" % ssh_host)
    ssh_client = paramiko.SSHClient()
    with su():
        try:
            ssh_client.load_host_keys('pycchdo_import_known_hosts')
        except IOError:
            implog.error('Need file pycchdo_import_known_hosts with %s '
                          'host key' % ssh_host)
            raise
        try:
            ssh_client.connect(ssh_host, username='root',
                               key_filename='pycchdo_import_root_ssh_key')
        except IOError:
            implog.error('Need file pycchdo_import_root_ssh_key to SSH '
                          'as remote root.')
            implog.info("Please generate an SSH key and put the public "
                         "key in the remote host's root authorized keys. "
                         "Remember that this will allow anyone with the "
                         "generated private key to log in as the remote "
                         "root so BE CAREFUL.")
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
def sftp_dl(sftp, filepath):
    temp = tempfile.NamedTemporaryFile(delete=False)
    try:
        implog.info('Downloading %s' % filepath)
        sftp.get(filepath, temp.name)
        yield temp
    except IOError, e:
        implog.warn("Unable to locate file on remote %s: %s" % (filepath, e))
        yield None
    finally:
        os.unlink(temp.name)


def _ustr2uni(s):
    if type(s) is unicode:
        return s
    return unicode(s, 'unicode_escape')


def _date_to_datetime(date):
    return datetime.datetime.combine(date, datetime.time(0))


def update_attr(o, key, value, signer, accept=True):
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
            a.save()
            return a
        else:
            if accept:
                return o.set_accept(key, value, signer)
            else:
                return o.set(key, value, signer)
    except KeyError:
        if accept:
            return o.set_accept(key, value, signer)
        else:
            return o.set(key, value, signer)
