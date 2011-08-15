import getopt
import sys
import cgi
import stat
from contextlib import contextmanager
import logging
import urllib2
import tempfile
import os

import paramiko

import pycchdo.models as models

import libcchdo
import libcchdo.db.model.legacy as legacy


logging.basicConfig(level=logging.DEBUG)


_USAGE = """\
Usage: importer.py
\t-c|--clear\tClear database before importing
\t-h|--help\tPrint this help message
"""


@contextmanager
def db_session(session):
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ssh_cchdo():
    host = 'cchdo.ucsd.edu'
    logging.info("Connecting (SSH) to %s" % host)
    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()
    ssh_client.connect(host)
    return ssh_client


def import_users(session, importer):
    map_users = {}

    logging.info("Importing users")
    users = session.query(legacy.User).all()
    for user in users:
        logging.info('Importing User %s' % user.username)
        person = models.Person.map_mongo(models.Person.find_one({'identifier': user.username}))
        if not person:
            person = models.Person(identifier=user.username)
            person.creation_stamp['person'] = importer
            person.save()
        if person.attrs.get('password_hash', None) != user.password_hash:
            person.attrs.set('password_hash', user.password_hash, importer).accept(importer)
        if person.attrs.get('password_salt', None) != user.password_salt:
            person.attrs.set('password_salt', user.password_salt, importer).accept(importer)
        if person.attrs.get('id', None) != user.id:
            person.attrs.set('id', user.id, importer).accept(importer)
        map_users[user.id] = person.id

    return map_users


def _contact_unicode_to_utf8(string):
    return unicode(string, 'unicode_escape')


def _import_contacts(session, importer):
    logging.info("Importing Contacts")
    map_persons = {}

    for contact in session.query(legacy.Contact).all():
        logging.info("Importing Contact %s %s" % (
            _contact_unicode_to_utf8(contact.FirstName), 
            _contact_unicode_to_utf8(contact.LastName)))

        # Since CCHDO currently has no concept of an Institution separate from a contact, make them here.
        institution_name = _contact_unicode_to_utf8(contact.Institute)
        institutions = models.Institution.get_by_attrs(name=institution_name)
        if len(institutions) > 0:
            institution = institutions[0]
        else:
            logging.info("Importing Institution %s" % (institution_name))
            institution = models.Institution(importer)
            institution.save()
            institution.attrs.set('name', institution_name, importer).accept(importer)

        person = models.Person.map_mongo(models.Person.find_one({
            'name_first': _contact_unicode_to_utf8(contact.FirstName),
            'name_last': _contact_unicode_to_utf8(contact.LastName)}))
        if not person:
            person = models.Person(
                name_first=_contact_unicode_to_utf8(contact.FirstName),
                name_last=_contact_unicode_to_utf8(contact.LastName),
                institution=institution.id,
                email=_contact_unicode_to_utf8(contact.email),
                )
            person.save()
        if contact.Address and not person.attrs.get('address', None):
            person.attrs.set('address', _contact_unicode_to_utf8(contact.Address), importer).accept(importer)
        if contact.telephone and not person.attrs.get('telephone', None):
            person.attrs.set('telephone', contact.telephone, importer).accept(importer)
        if contact.fax and not person.attrs.get('fax', None):
            person.attrs.set('fax', contact.fax, importer).accept(importer)
        if contact.title and not person.attrs.get('title', None):
            person.attrs.set('title', contact.title, importer).accept(importer)
        map_persons[contact.id] = person.id
    return map_persons


def _import_cruises(session, importer):
    logging.info("Importing Cruises")
    map_cruises = {}

    for cruise in session.query(legacy.Cruise).limit(10).all():
        print cruise.ExpoCode, cruise.Line, cruise.Country, cruise.Chief_Scientist, cruise.Begin_Date, cruise.EndDate, cruise.Ship_Name, cruise.Alias, cruise.Group, cruise.Program, cruise.link

    return map_cruises


def import_argo_files(session, importer, map_users, ssh_cchdo):
    logging.info("Importing Argo files")
    argo_files = session.query(legacy.ArgoFile).all()

    sftp_cchdo = ssh_cchdo.open_sftp()
    sftp_cchdo.chdir('/data/argo/files')

    for file in argo_files:
        logging.info('Importing Argo File (%s, %s)' % (file.filename, file.created_at))
        argo_file = models.ArgoFile.map_mongo(models.ArgoFile.find_one({'creation_stamp.timestamp': file.created_at}))
        if not argo_file:
            argo_file = models.ArgoFile(importer)
            argo_file.creation_stamp['person'] = map_users[file.user.id]
            argo_file.creation_stamp['timestamp'] = file.created_at
            argo_file.save()

        if argo_file.text_identifier != file.expocode:
            argo_file.attrs.set('text_identifier', file.expocode, importer).accept(importer)
        if argo_file.description != file.description:
            argo_file.attrs.set('description', file.description, importer).accept(importer)
        if argo_file.display != file.display:
            argo_file.attrs.set('display', file.display, importer).accept(importer)
        if argo_file.file is None:
            # Special case for missing.txt because there is no actual file.
            if file.filename != 'missing.txt':
                actual_file = cgi.FieldStorage()

                lstat = sftp_cchdo.lstat(file.filename)
                if stat.S_ISLNK(lstat.st_mode):
                    # TODO need to figure out whether this file is already in
                    # the file store and link to it instead of creating a new
                    # copy.
                    logging.warn('TODO Need to figure out how to link files')
                else:
                    temp = tempfile.NamedTemporaryFile(delete=False)
                    logging.info('Downloading %s' % file.filename)
                    sftp_cchdo.get(file.filename, temp.name)
                    actual_file.file = temp
                    actual_file.filename = file.filename
                    actual_file.type = file.content_type
                    logging.debug(actual_file)
                    logging.debug(repr(actual_file))
                    argo_file.attrs.set('file', actual_file, importer).accept(importer)
                    os.unlink(temp.name)

        logging.warn('downloads to import %r' % file.downloads)


def main(argv):
    options = {
        'clear_db_first': False,
        'db_uri': 'mongodb://dimes.ucsd.edu:28019',
    }

    opts, args = getopt.getopt(argv[1:], 'hc', ('help', 'clear'))
    for option, value in opts:
        if option in ('-h', '--help'):
            print _USAGE
            return 0
        if option in ('-c', '--clear'):
            options['clear_db_first'] = True

    logging.info("Connect to pycchdo (%s)" % options['db_uri'])
    models.init_conn({'db_uri': options['db_uri']})

    if options['clear_db_first']:
        logging.info('Clearing database')
        cchdo = models.cchdo()
        for coll in cchdo.collection_names():
            if not coll.startswith('system'):
                cchdo.drop_collection(coll)

    logging.info("Create Importer to take blame")
    importer = models.Person.map_mongo(models.Person.find_one({
        'name_first': 'CCHDO', 'name_last': 'importer'}))
    if not importer:
        importer = models.Person(identifier='CCHDO_importer',
                                 name_first='CCHDO',
                                 name_last='importer')
        importer.save()

    logging.info("Connecting to cchdo db")
    with db_session(legacy.session()) as session:
        map_users = import_users(session, importer)

        map_persons = _import_contacts(session, importer)

        map_cruises = _import_cruises(session, importer)

        logging.info('cruise early quit')
        return 0

        ssh_cchdo = _ssh_cchdo()

        # TODO Revisit for linked files and downloads
        import_argo_files(session, importer, map_users, ssh_cchdo)

    logging.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
