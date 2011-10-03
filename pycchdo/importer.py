import datetime
import getopt
import sys
from cgi import FieldStorage
import stat
from contextlib import contextmanager
import logging
import urllib2
import tempfile
import os
import re
import mimetypes

import paramiko
import shapely.wkt
import shapely.geos
from shapely.geometry import LineString

import pycchdo.models as models

import libcchdo
import libcchdo.fns
import libcchdo.db.model.convert as lcconvert
std = lcconvert.std
legacy = lcconvert.legacy


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


def _ustr2uni(string):
    return unicode(string, 'unicode_escape')


def _date_to_datetime(date):
    return datetime.datetime.combine(date, datetime.time(0))


@contextmanager
def sftp_dl(sftp, filepath):
    temp = tempfile.NamedTemporaryFile(delete=False)
    try:
        logging.info('Downloading %s' % filepath)
        sftp.get(filepath, temp.name)
        yield temp
    except IOError:
        logging.error("Unable to locate file on remote %s" % filepath)
        yield None
    finally:
        os.unlink(temp.name)


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


def _import_person_inst(importer, name_first, name_last,
                        institution_name, email):
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

    person = models.Person.get_one({'name_first': name_first,
                                    'name_last': name_last})
    if not person:
        logging.info("Creating Contact %s %s" % (
            name_first, 
            name_last))

        person = models.Person(
            name_first=name_first,
            name_last=name_last,
            institution=institution.id,
            email=email,
            )
        person.save()
    else:
        logging.info("Updating Contact %s %s" % (name_first, name_last))
    return person


def _import_contacts(session, importer):
    logging.info("Importing Contacts")
    map_persons = {}

    for contact in session.query(legacy.Contact).all():
        person = _import_person_inst(importer, _ustr2uni(contact.FirstName),
                                     _ustr2uni(contact.LastName), 
                                     _ustr2uni(contact.Institute),
                                     _ustr2uni(contact.email))
        # Since CCHDO currently has no concept of an Institution separate from a contact, make them here.
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

    cruises = session.query(legacy.Cruise).all()
    len_cruises = float(len(cruises))
    for i, cruise in enumerate(cruises):
        if i % 10 == 0:
            logging.info('%d/%d = %f' % (i, len_cruises, i / len_cruises))
        cs = models.Cruise.get_by_attrs(import_id=cruise.id)
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
                attr_aliases.save()
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
            attr_collections.save()
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
            #    attr_participants.save()
            #except KeyError:
            #    c.set_accept('participants', participants, importer)
        # TODO ensure that expocode is unique. or merge cruises that seem to only just have different line numbers

    return map_cruises


def _import_track_lines(session, importer, map_cruises):
    tls = session.query(legacy.TrackLine).all()
    for tl in tls:
        wkt = session.scalar(tl.Track.wkt)
        try:
            linestring = shapely.wkt.loads(wkt)
        except shapely.geos.ReadingError:
            # There are some linestrings in the DB that are single point lines. Yes.
            point = tuple(shapely.wkt.loads(wkt.replace('LINESTRING', 'POINT')).coords)[0]
            pt_list = [point, point]
            linestring = LineString(pt_list)

        cruises = models.Cruise.get_by_attrs(expocode=tl.ExpoCode)
        if len(cruises) > 0:
            cruise = cruises[0]
        else:
            logging.warn('Unable to import track_line %s because the cruise '
                         '%s does not exist' % (tl.id, tl.ExpoCode))
            continue

        print type(linestring)
        if cruise.track:
            logging.info('Updating %s track' % tl.ExpoCode)
            if cruise.track != linestring:
                try:
                    attr = cruise.get_attr('track')
                    attr.value = list(linestring.coords)
                    attr.creation_stamp = models.Stamp(importer)
                    attr.judgment_stamp = models.Stamp(importer)
                    attr.save()
                except KeyError:
                    cruise.set_accept('track', linestring, importer)
            else:
                logging.info('Updating %s track' % tl.ExpoCode)
        else:
            logging.info('Creating %s track' % tl.ExpoCode)
            cruise.set_accept('track', linestring, importer)


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

        imported_collection = models.Collection.get_by_attrs(names=collection.Name)
        # Filter again for collection's exact name to be the importee name
        imported_collection = [c for c in imported_collection if c.name == collection.Name]
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
                logging.info(
                    "Updating participant %s %s to %s" % (person, role, cruise))
                continue
        except KeyError:
            pass
        logging.info(
            "Importing participant %s %s to %s" % (person, role, cruise))
        cruise.participants.add(person, role, importer).accept(importer)


def _import_events(session, importer):
    logging.info("Importing Events")
    map_events = {}
    events = session.query(legacy.Event).all()
    present_note_import_ids = []
    for note in models.Note.get_all():
        try:
            present_note_import_ids.append(note.import_id)
        except AttributeError:
            pass
    len_events = len(events)
    for i, event in enumerate(events):
        if i % 100 == 0:
            logging.info('%d/%d = %f' % (i, len_events,
                                            float(i) / len_events))
        if event.ID in present_note_import_ids:
            logging.info("Updating Event %s" % event.ID)
        else:
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

            person = _import_person(
                session, importer, event.LastName, event.First_Name)
            note = models.Note(person, body, action, data_type, summary)
            note.creation_stamp.timestamp = \
                _date_to_datetime(event.Date_Entered)
            note.import_id = event.ID
            note.save()
            map_events[event.ID] = note

            cruises = models.Cruise.get_by_attrs(expocode=event.ExpoCode)
            for cruise in cruises:
                logging.info("Creating Event %s for cruise %s" % (
                    event.ID, cruise.get('import_id')))
                cruise.add_note(note)
    return map_events


def _import_old_submissions(session, importer, sftp_cchdo):
    logging.info("Importing Old Submissions")
    subs = session.query(legacy.OldSubmission).all()
    map_submissions = {}
    for sub in subs:
        try:
            submission = map_submissions[sub.Folder]
        except KeyError:
            submissions = models.OldSubmission.get_by_attrs(folder=sub.Folder)
            if len(submissions) > 0:
                logging.info('Updating OldSubmission %s' % sub.Folder)
                submission = submissions[0]
            else:
                logging.info('Creating OldSubmission %s' % sub.Folder)
                submission = models.OldSubmission(importer)
                submission.creation_stamp['timestamp'] = sub.created_at
                submission.accept(importer)
                submission.judgment_stamp['timestamp'] = sub.updated_at
                submission.save()
                submission.set_accept('folder', sub.Folder, importer)
                submission.set_accept(
                    'date', _date_to_datetime(sub.Date), importer)
                submission.set_accept('stamp', sub.Stamp, importer)
                submission.set_accept('line', sub.Line, importer)
                submission.set_accept('submitter', sub.Name, importer)
                submission.set_accept('files', [], importer)

            map_submissions[sub.Folder] = submission
        attr = submission.get_attr('files')
        if models.fs().exists({'filename': sub.Filename,
                               'old_submission': True}):
            continue
        with sftp_dl(sftp_cchdo, sub.Location) as file:
            if file is None:
                if sub.Location in (
                    # File seems to be missing
                    '/incoming_data/old_sys/20041214.085723_STEINFELDT_CARIBINFLOW/20041214.085723_STEINFELDT_CARIBINFLOW_TMP.zip',
                    # File seems to be missing
                    '/incoming_data/old_sys/20041214.084855_STEINFELDT_METEOR53_3/20041214.084855_STEINFELDT_METEOR53_3_ctd.zip',
                    # File seems to be missing; maybe can regenerate from gzipped flat files?
                    '/incoming_data/old_sys/20040224.000001_MCTAGGART_PR15/20040224.000001_MCTAGGART_PR15_Archive.zip',
                    # File seems to be missing
                    '/incoming_data/old_sys/20040224.000001_MCTAGGART_PR15/20040224.000001_MCTAGGART_PR15_00_README.gz',
                    # File seems to be missing; maybe can regenerate from gzipped flat files?
                    '/incoming_data/old_sys/20040224.000000_MCTAGGART_PR16/20040224.000000_MCTAGGART_PR16_Archive.zip',
                    # File seems to be missing
                    '/incoming_data/old_sys/20040224.000000_MCTAGGART_PR16/20040224.000000_MCTAGGART_PR16_00_README.gz',
                    # File seems to be missing; maybe can regenerate from gzipped flat files?
                    '/incoming_data/old_sys/20030304.000001_MCTAGGART_PR15/20030304.000001_MCTAGGART_PR15_Archive.zip',
                    # File seems to be missing; maybe can regenerate from gzipped flat files?
                    '/incoming_data/old_sys/20030304.000000_MCTAGGART_PR16/20030304.000000_MCTAGGART_PR16_Archive.zip',
                    ):
                    continue
                else:
                    raise ValueError('Unable to find file for old submission: '
                                     '%s' % sub.Location)
            id = models.fs().put(file, filename=sub.Filename,
                                 old_submission=True)
            attr.value = attr.value + [id]
            attr.save()


def _import_spatial_groups(session, importer):
    logging.info("Importing Spatial groups")
    sgs = session.query(legacy.SpatialGroup).all()
    for sg in sgs:
        collection = _import_Collection(importer, sg.area, 'spatial_group')
        basins = []
        if sg.atlantic:
            basins.append('atlantic')
        if sg.arctic:
            basins.append('arctic')
        if sg.pacific:
            basins.append('pacific')
        if sg.indian:
            basins.append('indian')
        if sg.southern:
            basins.append('southern')
        collection.set_accept('basins', basins, importer)


def _import_internal(session, importer):
    """ Internal maps a cruise to a basin """
    logging.info("Importing Internal")
    internals = session.query(legacy.Internal).all()
    for i in internals:
        cruises = models.Cruise.get_by_attrs(expocode=i.ExpoCode)
        if len(cruises) > 0:
            logging.info("Updating Cruise %s for internal" % i.ExpoCode)
            cruise = cruises[0]
        else:
            logging.info("Creating Cruise %s for internal" % i.ExpoCode)
            cruise = models.Cruise(importer)
            cruise.accept(importer)
            cruise.save()
            cruise.set_accept('expocode', i.ExpoCode, importer)
        collection = _import_Collection(importer, i.Basin, 'basin')
        a = cruise.get_attr('basin')
        a.value = libcchdo.fns.uniquify(a.value + [collection.id])
        a.save()


def _import_unused_tracks(session, importer):
    logging.info("Importing unused tracks")
    ts = session.query(legacy.UnusedTrack).all()
    for t in ts:
        cruises = models.Cruise.get_by_attrs(expocode=t.ExpoCode)
        if len(cruises) > 0:
            logging.info("Updating Cruise %s for unused track" % t.ExpoCode)
            cruise = cruises[0]
        else:
            logging.info("Creating Cruise %s for unused track" % t.ExpoCode)
            cruise = models.Cruise(importer)
            cruise.accept(importer)
            cruise.save()
            cruise.set_accept('expocode', t.ExpoCode, importer)
        collection = _import_Collection(importer, t.Basin, 'basin')
        a = cruise.get_attr('basin')
        a.value = libcchdo.fns.uniquify(a.value + [collection.id])
        a.save()


def _import_unit(importer, unit):
    us = models.Unit.get_by_attrs(import_id=unit.id)
    if len(us) > 0:
        return us[0]
    else:
        u = models.Unit(importer)
        u.accept(importer)
        u.save()
        u.set_accept('name', unit.name, importer)
        u.set_accept('mnemonic', unit.mnemonic, importer)
        return u


def _import_parameter_descriptions(session, importer):
    logging.info("Importing parameter descriptions")
    std_session = std.session()
    parameters = lcconvert.all_parameters(std_session)
    std_session.close()
    for parameter in parameters:
        parameters = models.Parameter.get_by_attrs(name=parameter.name)
        if len(parameters) > 0:
            logging.info("Updating Parameter %s" % parameter.name)
            p = parameters[0]
        else:
            logging.info("Creating Parameter %s" % parameter.name)
            p = models.Parameter(importer)
            p.accept(importer)
            p.save()
            p.set_accept('name', parameter.name, importer)
            p.set_accept('full_name', parameter.full_name, importer)
            p.set_accept('name_netcdf', parameter.name_netcdf, importer)
            p.set_accept('format', parameter.format, importer)
            if parameter.units:
                p.set_accept(
                    'unit',
                    _import_unit(importer, parameter.units).id, importer)
            p.set_accept('bounds', (parameter.bound_lower,
                                    parameter.bound_upper), importer)
            aliases = [a.name for a in parameter.aliases]
            p.set_accept('aliases', aliases, importer)


def _import_parameter_groups(session, importer):
    groups = session.query(legacy.ParameterGroup).all()
    for group in groups:
        gs = models.ParameterOrder.get_by_attrs(name=group.group)
        if len(gs) > 0:
            g = gs[0]
        else:
            g = models.ParameterOrder(importer)
            g.accept(importer)
            g.save()
            g.set_accept('name', group.group, importer)
            order = group.ordered_parameters
            parameters = []
            for p in order:
                parameter = models.Parameter.get_by_attrs(name=p)
                if not parameter:
                    logging.warn("Could not find parameter %s for order" % p)
                    parameter = models.Parameter(importer)
                    parameter.accept(importer)
                    parameter.save()
                    parameter.set_accept('name', p, importer)
                    parameter.set_accept('in_groups_but_did_not_exist', True, importer)
                parameters.append(parameter)
            g.set_accept('order', parameters, importer)


def _import_bottle_dbs(session, importer):
    logging.info("Importing Bottle DBs")
    # TODO regenerate bottle parameter information cache
    logging.info("Omitting import in favor of regenerating this information")


def _import_parameter_status(session, importer):
    logging.info("Importing parameter statuses")
    logging.info("Omitting import because information is never used in site "
                 "and probably is replaced by documents.preliminary")


def _import_parameters(session, importer):
    logging.info("Importing parameters (chiscis responsible)")

    codes = {}
    for code in session.query(legacy.Codes).all():
        codes[int(code.Code)] = code.Status

    parameters = {}
    for param in legacy.CruiseParameterInfo._PARAMETERS:
        ps = models.Parameter.get_by_attrs(name=param)

        if len(ps) > 0:
            logging.info("Found Parameter %s for CPI" % param)
            parameter = ps[0]
        else:
            logging.warn("Created Parameter %s for CPI" % param)
            parameter = models.Parameter(importer)
            parameter.accept(importer)
            parameter.save()
            parameter.set_accept('name', param, importer)
            parameter.set_accept('import_id', 'cruise_param_info')
        parameters[param] = parameter

    for p in session.query(legacy.CruiseParameterInfo).all():
        cruise = models.Cruise.get_by_attrs(expocode=p.ExpoCode)
        if len(cruise) > 0:
            logging.info("Found Cruise %s for CPI" % p.ExpoCode)
            cruise = cruise[0]
        else:
            logging.info("Creating Cruise %s for CPI" % p.ExpoCode)
            cruise = models.Cruise(importer)
            cruise.accept(importer)
            cruise.save()
            cruise.set_accept('expocode', p.ExpoCode, importer)
            cruise.set_accept('import_id', 'cruise_param_info', importer)

        param_infos = []

        for param in legacy.CruiseParameterInfo._PARAMETERS:
            parameter = parameters[param]

            status = getattr(p, param)
            try:
                status = codes[int(status)]
            except (TypeError, ValueError):
                if status != None:
                    logging.warn("Bad Status while importing 'parameters' row "
                                 "%d parameter %s" % (p.id, param))
                status = None
            except KeyError:
                logging.warn("Unrecognized status while importing 'parameters' "
                             "row %d parameter %s" % (p.id, param))
                status = None

            try:
                pi = _ustr2uni(getattr(p, param + '_PI'))
            except TypeError:
                pi = None
            # TODO figure out how to import PI name/institution fun
            
            try:
                d = _date_to_datetime(getattr(p, param + '_Date'))
            except TypeError:
                d = None

            param_infos.append({'parameter': parameter.id, 'status': status,
                                'pi': pi, 'ts': d})

        cruise.set_accept('parameter_informations', param_infos, importer)


def _import_submissions(session, importer, sftp_cchdo):
    logging.info("Importing Submissions")

    imported_submissions = set([
        s.get('import_id') for s in models.Submission.get_all(fields=['creation_stamp'])])

    def public_to_bool(p, action):
        if p is None:
            # Assume that no response means public data as long as action does
            # not contain Argo.
            if not action or 'Argo' in action:
                return False
            return True
        elif p == 'Public':
            return True
        else:
            return False

    for sub in session.query(legacy.Submission).all():
        if sub.id in imported_submissions:
            logging.info("Updating Submission %d" % sub.id)
            continue
        else:
            logging.info("Creating Submission %d" % sub.id)
            submission = models.Submission(importer)

            submission_date = _date_to_datetime(sub.submission_date)
            submission.creation_stamp.timestamp = submission_date

            # Information about submitter
            name = sub.name
            inst = sub.institute
            email = sub.email
            country = sub.country
            ip = sub.ip
            ua = sub.user_agent

            submitter = _import_person_inst(importer, name, '', inst, email)
            submitter.set_accept('country', country, importer)
            submitter.set_accept('ip', ip, importer)
            submitter.set_accept('ua', ua, importer)

            submission.creation_stamp.person = submitter.id

            submission.save()

            expocode = sub.expocode
            ship_name = sub.ship_name
            line = sub.line
            action = sub.action
            notes = sub.notes
            file_name = sub.file

            if expocode:
                submission.set_accept('expocode', _ustr2uni(expocode), importer)
            if ship_name:
                submission.set_accept('ship_name', _ustr2uni(ship_name), importer)
            if line:
                submission.set_accept('line', _ustr2uni(line), importer)
            if action:
                submission.set_accept('action', _ustr2uni(action), importer)
            if notes:
                submission.add_note(models.Note(importer,
                                                _ustr2uni(notes)).save())

            file = None
            with sftp_dl(sftp_cchdo, file_name) as file:
                if not file:
                    submission.remove()
                    logging.warn('unable to get file for Submission %s', sub.id)
                    continue
                actual_file = FieldStorage()
                actual_file.filename = file_name
                actual_file.file = file
                submission.set_accept('file', actual_file, importer)

            public = public_to_bool(sub.public, action)
            # 2011-09-16 myshen
            # Carolina has determined "assigned" corroborates
            # non-public status and is generally redundant. More importantly it
            # is not used.
            # "assimilated" is used to color code the submission table according
            # to whether submission has been put in the queue.
            assimilated = bool(sub.assimilated)
            submission.set_accept('public', public, importer)
            submission.set_accept('assimilated', assimilated, importer)
            try:
                cruise_date = _date_to_datetime(sub.cruise_date)
                submission.set_accept('cruise_date', cruise_date, importer)
            except TypeError:
                pass

            submission.set_accept('import_id', sub.id, importer)


def _get_mtime(sftp_cchdo, filepath):
    lstat = sftp_cchdo.lstat(filepath)
    return datetime.datetime.fromtimestamp(lstat.st_mtime)


def _import_queue_files(session, importer, sftp_cchdo):
    logging.info("Importing queue files")

    re_docs = re.compile('Cruise (report|information)', re.IGNORECASE)

    queue_files = session.query(legacy.QueueFile).all()
    for qfile in queue_files:
        cruises = models.Cruise.get_by_attrs(expocode=qfile.expocode)
        if not cruises:
            logging.warn("Missing cruise for queue file %s" % qfile.expocode)
            continue
        else:
            cruise = cruises[0]

        queue_file = models.Attr.get_one({'import_id': qfile.id,
                                          'key': 'data_suggestion'})
        unprocessed_input = qfile.unprocessed_input.strip()
        if not queue_file:
            logging.info('Creating Queue File %s' % qfile.id)

            with sftp_dl(sftp_cchdo, unprocessed_input) as file:
                if file is None:
                    logging.warn(
                        "Missing queue file %s" % unprocessed_input)
                    logging.info("Skipping queue record import")
                    continue
                else:
                    actual_file = FieldStorage()
                    actual_file.filename = qfile.Name
                    actual_file.type = mimetypes.guess_type(qfile.Name)[0]
                    if not actual_file.type:
                        actual_file.type = 'application/octet-stream'
                    actual_file.file = file

            queue_file = cruise.set('data_suggestion', actual_file, importer)
            queue_file.import_id = qfile.id

            name = qfile.contact
            submitter = _import_person_inst(importer, name, '', '', '')

            queue_file.creation_stamp['person'] = submitter.id
            date_received = None
            if qfile.date_received:
                date_received = _date_to_datetime(qfile.date_received)
            else:
                date_received = _get_mtime(sftp_cchdo, unprocessed_input)
            queue_file.creation_stamp['timestamp'] = date_received
            queue_file.save()
        else:
            logging.info('Updating Queue File %s' % qfile.id)

        if qfile.cchdo_contact:
            contact = models.Person.get_one({'identifier': qfile.cchdo_contact})
            if contact:
                queue_file.acknowledge(contact)
            else:
                logging.warn(
                    "CCHDO contact %s is not recognized" % qfile.cchdo_contact)

        if qfile.merged == 1:
            date_merged = qfile.date_merged
            queue_file.accept(importer)
            if not date_merged:
                logging.warn('No date merged for merged file. Obtaining from '
                             'file timestamp')
                date_merged = _get_mtime(sftp_cchdo, unprocessed_input)
            else:
                date_merged = _date_to_datetime(date_merged)
            queue_file.judgment_stamp.timestamp = date_merged
            queue_file.save()

        if qfile.merged == 2 or qfile.hidden:
            # file is hidden
            queue_file.reject(importer)

        # processed_input is obsolete according to cberys
        # hidden flag is obsolete according to cberys

        if qfile.notes:
            queue_file.add_note(models.Note(importer,
                                            _ustr2uni(qfile.notes)).save())

        if qfile.action:
            queue_file.add_note(models.Note(importer, _ustr2uni(qfile.action),
                                            data_type='Action',
                                            discussion=True).save())

        if qfile.parameters or qfile.documentation:
            parameters = qfile.parameters
            if not parameters:
                parameters = ''
            if qfile.documentation:
                if not re_docs.match(parameters):
                    parameters = u','.join([parameters, 'Documentation'])
            queue_file.add_note(models.Note(importer, parameters,
                                            data_type='Parameters',
                                            discussion=True).save())

        if qfile.merge_notes:
            queue_file.add_note(models.Note(importer,
                                            _ustr2uni(qfile.merge_notes),
                                            discussion=True).save())


def _import_documents(session, importer, sftp_cchdo):
    # TODO
    return {}


def import_argo_files(session, importer, map_users, sftp_cchdo):
    logging.info("Importing Argo files")
    argo_files = session.query(legacy.ArgoFile).all()

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
                lstat = sftp_cchdo.lstat(file.filename)
                if stat.S_ISLNK(lstat.st_mode):
                    # TODO need to figure out whether this file is already in
                    # the file store and link to it instead of creating a new
                    # copy.
                    logging.warn('TODO Need to figure out how to link files')
                else:
                    with sftp_dl(sftp_cchdo, file.filename) as file:
                        actual_file = FieldStorage()
                        actual_file.filename = file.filename
                        actual_file.type = file.content_type
                        actual_file.file = file
                        logging.debug(repr(actual_file))
                        argo_file.set_accept('file', actual_file, importer)

        # TODO
        logging.warn('There is download information to import %r' % file.downloads)


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

    models.Attr._mongo_collection().ensure_index([('obj', 1), ('value', 1)])

    # libcchdo does not need a local cache of parameter information. That will
    # be done during the import
    libcchdo.check_cache = False

    logging.info("Connecting to cchdo db")
    with db_session(legacy.session()) as session:
        #map_users = import_users(session, importer)
        #map_persons = _import_contacts(session, importer)
        #map_collections = _import_collections(session, importer)
        #map_cruises = _import_cruises(session, importer)
        #_import_track_lines(session, importer, map_cruises)
        #_import_collections_cruises(session, importer,
        #                            map_cruises, map_collections)
        #_import_contacts_cruises(session, importer, map_cruises, map_persons)

        #map_events = _import_events(session, importer)

        #_import_spatial_groups(session, importer)
        #_import_internal(session, importer)
        #_import_unused_tracks(session, importer)

        #_import_parameter_descriptions(session, importer)
        #_import_parameter_groups(session, importer)
        #_import_bottle_dbs(session, importer)
        #_import_parameter_status(session, importer)
        #_import_parameters(session, importer)

        # Now follows imports that need ssh access
        try:
            ssh_cchdo = _ssh_cchdo()
            sftp_cchdo = ssh_cchdo.open_sftp()
        #    _import_submissions(session, importer, sftp_cchdo)
        #    _import_old_submissions(session, importer, sftp_cchdo)
        #    import_argo_files(session, importer, map_users, sftp_cchdo)
            _import_queue_files(session, importer, sftp_cchdo)
        #    map_documents = _import_documents(session, importer, sftp_cchdo)
        finally:
            sftp_cchdo.close()
            ssh_cchdo.close()

    logging.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
