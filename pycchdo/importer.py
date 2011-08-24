import datetime
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
import libcchdo.fns
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
        person = models.Person.get_one({'identifier': user.username})
        if not person:
            logging.info('Creating User %s' % user.username)
            person = models.Person(identifier=user.username)
            person.creation_stamp['person'] = importer
            person.save()
        else:
            logging.info('Updating User %s' % user.username)
        if person.get('password_hash', None) != user.password_hash:
            person.set_accept('password_hash', user.password_hash, importer)
        if person.get('password_salt', None) != user.password_salt:
            person.set_accept('password_salt', user.password_salt, importer)
        if person.get('id', None) != user.id:
            person.set_accept('id', user.id, importer)
        map_users[user.id] = person.id

    return map_users


def _ustr2uni(string):
    return unicode(string, 'unicode_escape')


def _import_contacts(session, importer):
    logging.info("Importing Contacts")
    map_persons = {}

    for contact in session.query(legacy.Contact).all():
        # Since CCHDO currently has no concept of an Institution separate from a contact, make them here.
        institution_name = _ustr2uni(contact.Institute)
        institutions = models.Institution.get_by_attrs(name=institution_name)
        if len(institutions) > 0:
            logging.info("Updating Institution %s" % (institution_name))
            institution = institutions[0]
        else:
            logging.info("Creating Institution %s" % (institution_name))
            institution = models.Institution(importer)
            institution.accept(importer)
            institution.save()
            institution.set_accept('name', institution_name, importer)

        person = models.Person.get_one({
            'name_first': _ustr2uni(contact.FirstName),
            'name_last': _ustr2uni(contact.LastName)})
        if not person:
            logging.info("Creating Contact %s %s" % (
                _ustr2uni(contact.FirstName), 
                _ustr2uni(contact.LastName)))

            person = models.Person(
                name_first=_ustr2uni(contact.FirstName),
                name_last=_ustr2uni(contact.LastName),
                institution=institution.id,
                email=_ustr2uni(contact.email),
                )
            person.save()
        else:
            logging.info("Updating Contact %s %s" % (
                _ustr2uni(contact.FirstName), 
                _ustr2uni(contact.LastName)))
        if contact.Address and person.get('address', None) is None:
            person.set_accept('address', _ustr2uni(contact.Address), importer)
        if contact.telephone and person.get('telephone', None) is None:
            person.set_accept('telephone', contact.telephone, importer)
        if contact.fax and person.get('fax', None) is None:
            person.set_accept('fax', contact.fax, importer)
        if contact.title and person.get('title', None) is None:
            person.set_accept('title', contact.title, importer)
        map_persons[contact.id] = person.id
    return map_persons


def _date_to_datetime(date):
    return datetime.datetime.combine(date, datetime.time(0))


def _import_Collection(importer, name, type):
    """ A Collection also will include a type as part of its identifier to
    differentiate between the fields it came from in the original database.
    
    """
    collections = models.Collection.get_by_attrs(names=[name], type=type)
    if len(collections) > 0:
        logging.info('Updating Collection %s %s' % (name, type))
        collection = collections[0]
    else:
        logging.info('Creating Collection %s %s' % (name, type))
        collection = models.Collection(importer)
        collection.accept(importer)
        collection.save()
        collection.set_accept('names', [name], importer)
        collection.set_accept('type', type, importer)
    return collection


def _import_cruises(session, importer):
    logging.info("Importing Cruises")
    map_cruises = {}

    for cruise in session.query(legacy.Cruise).all():
        cs = models.Cruise.get_by_attrs(expocode=cruise.ExpoCode, import_id=cruise.id)
        if len(cs) > 0:
            logging.info('Updating Cruise %s %s' % (cruise.id, cruise.ExpoCode))
            c = cs[0]
        else:
            logging.info('Creating Cruise %s %s' % (cruise.id, cruise.ExpoCode))
            c = models.Cruise(importer)
            c.accept(importer)
            c.save()
            c.set_accept('expocode', cruise.ExpoCode, importer)
            c.set_accept('import_id', cruise.id, importer)

        map_cruises[cruise.id] = c

        if cruise.Begin_Date and c.get('date_start', None) is None:
            c.set_accept('date_start', _date_to_datetime(cruise.Begin_Date), importer)
        if cruise.EndDate and c.get('date_end', None) is None:
            c.set_accept('date_end', _date_to_datetime(cruise.EndDate), importer)
        if cruise.link and c.get('link', None) is None:
            c.set_accept('link', cruise.link, importer)

        if cruise.Country and c.get('country', None) is None:
            countries = models.Country.get_by_attrs(**{'iso_3166-1': cruise.Country})
            if len(countries) > 0:
                logging.info('Updating Country %s' % cruise.Country)
                country = countries[0]
            else:
                logging.info('Creating Country %s' % cruise.Country)
                country = models.Country(importer)
                country.accept(importer)
                country.save()
                country.set_accept('iso-3166-1', cruise.Country, importer)
            c.set_accept('country', country.id, importer)

        if cruise.Ship_Name and c.get('ship', None) is None:
            ships = models.Ship.get_by_attrs(name=cruise.Ship_Name)
            if len(ships) > 0:
                logging.info('Updating Ship %s' % cruise.Ship_Name)
                ship = ships[0]
            else:
                logging.info('Creating Ship %s' % cruise.Ship_Name)
                ship = models.Ship(importer)
                ship.accept(importer)
                ship.save()
                ship.set_accept('name', cruise.Ship_Name, importer)
            c.set_accept('ship', ship.id, importer)

        if cruise.Alias:
            # TODO hope that Alias fields are all comma separated...
            aliases = libcchdo.fns.uniquify([x.strip() for x in cruise.Alias.split(',')])
            try:
                attr_aliases = c.get_attr('aliases')
                attr_aliases.value = aliases
                attr_aliases.creation_stamp = models.Stamp(importer)
                attr_aliases.judgment_stamp = models.Stamp(importer)
            except KeyError:
                c.set_accept('aliases', aliases, importer)

        collections = []

        if cruise.Line:
            collections.append(_import_Collection(importer, cruise.Line, 'WOCE line').id)
        if cruise.Group:
            groups = [x.strip() for x in cruise.Group.split(',')]
            for group in groups:
               collections.append(_import_Collection(importer, group, 'group').id)
        if cruise.Program:
            collections.append(_import_Collection(importer, cruise.Program, 'program').id)

        collections = libcchdo.fns.uniquify(collections)
        try:
            attr_collections = c.get_attr('collections')
            attr_collections.value = collections
            attr_collections.creation_stamp = models.Stamp(importer)
            attr_collections.judgment_stamp = models.Stamp(importer)
        except KeyError:
            c.set_accept('collections', collections, importer)
        
        if cruise.Chief_Scientist:
            #TODO this will be a bit difficult because institution information is
            # also included. sometimes.
            persons = [cruise.Chief_Scientist]

            logging.error('TODO: import persons: %r' % persons)

            #participants = []
            #for person in persons:
            #    participants.append({'role': 'chief_scientist', 'person': person.id})

            #try:
            #    attr_participants = c.get_attr('participants')
            #    attr_participants.value = participants
            #    attr_participants.creation_stamp = models.Stamp(importer)
            #    attr_participants.judgment_stamp = models.Stamp(importer)
            #except KeyError:
            #    c.set_accept('participants', participants, importer)
        # TODO ensure that expocode is unique. or merge cruises that seem to only just have different line numbers

    return map_cruises


def _import_person(session, importer, name_last, name_first):
    namel = _ustr2uni(name_last)
    namef = _ustr2uni(name_first)
    persons = models.Person.get_by_attrs(name_last=namel,
                                         name_first=namef)
    if persons:
        return persons[0]
    person = models.Person(None, namel, namef)
    person.save()
    person.accept(importer)
    return person


def _import_collections(session, importer):
    logging.info("Importing Collections")
    map_collections = {}
    collections = session.query(legacy.Collection).all()
    for collection in collections:
        imported_collection = models.Collection.get_by_attrs(
            import_id=collection.id)
        if imported_collection:
            logging.info("Updating Collection %s" % collection.id)
            continue

        imported_collection = models.Collection.get_by_attrs(
            **{'names.0': collection.Name})
        if imported_collection:
            logging.info("Updating Collection %s" % collection.id)
            map_collections[collection.id] = imported_collection[0]
            continue

        logging.info("Creating Collection %s" % collection.id)
        import_collection = models.Collection(importer)
        import_collection.save()
        import_collection.accept(importer)
        import_collection.set_accept('names', [collection.Name], importer)
        map_collections[collection.id] = import_collection
    return map_collections


def _import_collections_cruises(session, importer, map_cruise,
                                map_collections):
    logging.info("Importing CollectionsCruises")
    collections_cruises = session.query(legacy.CollectionsCruise).all()
    for cc in collections_cruises:
        if cc.collection is None or cc.cruise is None :
            logging.warn(
                'CollectionCruises pair (cruise %d, collection %d) is bad' % (
                    cc.cruise_id, cc.collection_id))
            continue
        try:
            cruise = map_cruise[cc.cruise.id]
        except KeyError:
            logging.warn('Bad cruise %d' % cc.cruise.id)
            continue
        try:
            collection = map_collections[cc.collection.id]
        except KeyError:
            logging.warn('Bad collections %d' % cc.collection.id)
            continue
        present = True
        cruise_collections = cruise.get('collections')
        if collection.id in cruise_collections:
            logging.info('Collection already present in Cruise collections')
        else:
            logging.info('Addding Collection %s to Cruise collections' % \
                         collection.id)
            cruise.set_accept('collections',
                              cruise_collections + [collection.id], importer)
# TODO make sure everything corroborates


def _import_contacts_cruises(session, importer, map_cruises, map_persons):
    logging.info("Importing ContactsCruises")
    contacts_cruises = session.query(legacy.ContactsCruise).all()
    for cc in contacts_cruises:
        if not cc.cruise:
            logging.info("Bad Cruise ID %s" % (cc.cruise_id))
            continue
        if not cc.contact:
            logging.info("Bad Contact ID %s" % (cc.contact_id))
            continue

        cruise = map_cruises.get(cc.cruise_id, None)
        if not cruise:
            logging.warn("Could not import ContactsCruise pair because cruise "
                         '%s does not exist.' % cruise)
            continue

        person_id = map_persons.get(cc.contact.id, None)
        if person_id is not None:
            person = models.Person.get_id(person_id)
        else:
            logging.warn("Could not import ContactsCruise pair because person "
                         '%s does not exist.' % cc.contact.id)
            continue

        role = cc.function
        if not role:
            role = 'Chief Scientist'
        try:
            if person in cruise.participants[role]:
                logging.info("Updating participant %s %s to %s" % (person, role, cruise))
                continue
        except KeyError:
            pass
        logging.info("Importing participant %s %s to %s" % (person, role, cruise))
        cruise.participants.add(person, role, importer).accept(importer)


def _import_events(session, importer, map_cruises):
    logging.info("Importing Events")
    map_events = {}
    events = session.query(legacy.Event).all()
    present_notes = models.Attr.find({
        'import_id': {'$exists': True}, 'key': None,
        'value': None, 'note': {'$exists': True}})
    present_note_import_ids = set([x['import_id'] for x in present_notes])
    len_events = len(events)
    for i, event in enumerate(events):
        if i % 100 == 0:
            logging.info('%d/%d = %f' % (i, len_events,
                                            float(i) / len_events))
        if event.ID in present_note_import_ids:
            logging.info("Updating Event %s" % event.ID)
        else:
            person = _import_person(
                session, importer, event.LastName, event.First_Name)
            cruises = models.Cruise.get_by_attrs(expocode=event.ExpoCode)
            body = ''
            if event.Note:
                body = _ustr2uni(event.Note)
            action = ''
            if event.Action:
                action = _ustr2uni(event.Action)
            data_type = ''
            if event.Data_Type:
                data_type = _ustr2uni(event.Data_Type)
            summary = ''
            if event.Summary:
                summary = _ustr2uni(event.Summary)
            note = models.Note(body, action, data_type, summary)
            notes = []
            for cruise in cruises:
                logging.info("Creating Event %s for cruise %s" % (
                    event.ID, cruise.get('import_id')))
                note_attr = cruise.add_note(note, person)
                note_attr.accept(importer)
                note_attr.import_id = event.ID
                note_attr.save()
                note_attr.accept(importer)
                notes.append(note_attr)
            map_events[event.ID] = notes
    return map_events


def import_argo_files(session, importer, map_users, ssh_cchdo):
    logging.info("Importing Argo files")
    argo_files = session.query(legacy.ArgoFile).all()

    sftp_cchdo = ssh_cchdo.open_sftp()
    sftp_cchdo.chdir('/data/argo/files')

    for file in argo_files:
        argo_file = models.ArgoFile.get_one({'creation_stamp.timestamp': file.created_at})
        if not argo_file:
            logging.info('Creating Argo File (%s, %s)' % (file.filename, file.created_at))
            argo_file = models.ArgoFile(importer)
            argo_file.creation_stamp['person'] = map_users[file.user.id]
            argo_file.creation_stamp['timestamp'] = file.created_at
            argo_file.save()
        else:
            logging.info('Updating Argo File (%s, %s)' % (file.filename, file.created_at))

        if argo_file.text_identifier != file.expocode:
            argo_file.set_accept('text_identifier', file.expocode, importer)
        if argo_file.description != file.description:
            argo_file.set_accept('description', file.description, importer)
        if argo_file.display != file.display:
            argo_file.set_accept('display', file.display, importer)
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
                    creenrgo_file.set_accept('file', actual_file, importer)
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

    importer = models.Person.get_one({
        'name_first': 'CCHDO', 'name_last': 'importer'})
    if not importer:
        logging.info("Create Importer to take blame")
        importer = models.Person(identifier='CCHDO_importer',
                                 name_first='CCHDO',
                                 name_last='importer')
        importer.save()

    logging.info("Connecting to cchdo db")
    with db_session(legacy.session()) as session:
        map_users = import_users(session, importer)
        map_persons = _import_contacts(session, importer)
        map_collections = _import_collections(session, importer)
        map_cruises = _import_cruises(session, importer)

        _import_collections_cruises(session, importer,
                                    map_cruises, map_collections)
        _import_contacts_cruises(session, importer, map_cruises, map_persons)

        #map_events = _import_events(session, importer, map_cruises)
        #map_documents = _import_documents(session, importer)

        logging.info('cruise early quit')
        return 0

        ssh_cchdo = _ssh_cchdo()

        # TODO Revisit for linked files and downloads
        import_argo_files(session, importer, map_users, ssh_cchdo)

    logging.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
