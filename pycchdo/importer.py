#!/usr/bin/env python
# -*- coding: utf8 -*-

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
import tarfile
import shutil
from StringIO import StringIO
import pwd
import threading
import time
import zipfile

import sqlalchemy.exc

import paramiko

import shapely.wkt
import shapely.geos
from shapely.geometry import LineString

import pycchdo.models as models
from pycchdo.importers import *
from pycchdo.importers.cchdo import *
import pycchdo.importers.seahunt as seahunt
import pycchdo.models.triggers as triggers
from pycchdo.models.search import SearchIndex

import libcchdo
import libcchdo.fns
import libcchdo.db.model.convert as lcconvert
std = lcconvert.std
legacy = lcconvert.legacy


nthreads = 20


_USAGE = """\
Usage: importer.py
\t-c|--clear\tClear database before importing
\t-h|--help\tPrint this help message
"""

wwwusername = '_www'
try:
    wwwuser = pwd.getpwnam(wwwusername)
    import_uid = wwwuser.pw_uid
    import_gid = wwwuser.pw_gid
except Exception:
    implog.error('No such user %s' % wwwusername)
    sys.exit(1)


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


def sftp_dl_dir(sftp, remotedir, localdir, su_lock=None):
    try:
        os.mkdir(localdir)
    except OSError, e:
        implog.debug('Unable to create directory %s %s' %
                     (os.path.basename(remotedir), e))
        return

    for file in sftp.listdir(remotedir):
        remote_path = os.path.join(remotedir, file)
        local_path = os.path.join(localdir, file)

        remote_stat = sftp.lstat(remote_path)

        if stat.S_ISDIR(sftp.lstat(remote_path).st_mode):
            sftp_dl_dir(sftp, remote_path, local_path)
        else:
            try:
                sftp.get(remote_path, local_path)
            except IOError, e:
                implog.warning('Unable to download %s (%s)' % (remote_path, e))

        if su_lock:
            su_lock.acquire()
        with su():
            os.chmod(local_path, remote_stat.st_mode)
            os.chown(local_path, remote_stat.st_uid, import_gid)
            os.utime(local_path, (remote_stat.st_atime, remote_stat.st_mtime))
        if su_lock:
            su_lock.release()


def _namesonly(names):
    d = {}
    for name in names:
        d[name] = (name, None, )
    return d


known_names = _namesonly([
    'O. Pfannkuche',
    'Nicol',
    'D.  Capone',
    'Hellsvik',
    'Collins',
    'Smethie',
    'Olsen',
    'Talley',
    'Skjelvan',
    'M.Estrada',
    'A.Subramaniam',
    'Key',
    'Warren',
    'Murata',
    'Garzoli',
    'Hosie',
    'Rey',
])
known_names['Unknown'] = None


# Maps known acronyms to a good search phrase
known_institutions = {
    u'PMEL': [u'Pacific Marine Environmental Laboratory', u'PMEL',
        u'NOAA'],
    u'NOAA': [u'NOAA'],
    u'FIMR': [u'Finnish Institute of Marine Research'], 
    u'LODYC': [u"Laboratoire d'Océanographie Dynamique et de Climatologie",
               u'LODYC'],
    u'JAMSTEC': [u'Japan Agency for Marine-Earth Science and Technology',
        u'Japan Marine Science and Technology Center',
        u'Marine Science and Technology Center', u'JAMSTEC', ],
    u'JODC': [u'Japan Oceanographic Data Center'],
    u'BAH': [u'Biologische Anstalt Helgoland'],
    u'IfMH': [u'Institut für Meereskunde der Universität Hamburg',
              u'Institut für Meereskunde\nUniversität Hamburg',
              u'Institut fur Meereskunde\nUniversitat of Hamburg',
              u'University of Hamburg\nInstitute for Oceanography'], 
    u'IfMK': [u'Institut für Meereskunde an der Universität Kiel',
              u'Institut fur Meereskunde\nUniversitat Kiel', u'IfMK'], 
    u'IOS': [u'Institute of Ocean Sciences', # Canada
             u'Institute of Oceanographic Sciences'], # NOC SOTON
    u'IOS BC': [u'Institute of Ocean Sciences'], # Canada
    u'IMR': [u'Institute of Marine Research Bergen, Norway',
             u'Institute of Marine Research'],
    u'BIO': [u'Bedford Institute of Oceanography'],
    u'BSH': [u'Bundesamt fur Seeschiffahrt und Hydrographie'],
    u'SOI': [u'P.P. Shirshov Institute of Oceanology',
             u'P.P. Shirshov Inst. of Oceanology',
             u'Shirshov Institute of Oceanology'],
    u'GOIN': [u'State Oceanographic Institute'], # Russia
    u'IEO': [u'Instituto Español de Oceanografía (IEO)'],
    u'LPO': [u'Laboratoire de Physique des Oceans'],
    u'ORSTOM': [u'ORSTOM'],
    u'IPO': [u'WOCE International Project Office'],
    u'AWI': [u'Alfred-Wegener-Institut für Polar- und Meeresforschung',
             u'Alfred-Wegener'], 
    u'Alfred-Wegener-Institut für Polar- und Meeresforschung':
        [u'Alfred-Wegener'],
    u'LDEO': [u'Lamont-Doherty Earth Observatory'],
    u'SIO': [u'Scripps Institution of Oceanography'],
    u'WHOI': [u'Woods Hole Oceanographic Institution'],
    u'JRC': [u'James Rennell Division for Ocean Circulation and Climate',
             u'James Rennell'],
    u'UB': [u'Universitat Bremen'],
    u'PRINCETON': [u'Princeton'],
    u'AOML': [u'Atlantic Oceanographic and Meteorological Laboratory'],
    u'UBIfU': [u'Institut fur Umweltphysik', u'Institut für Umweltphysik'],
    u'IOW': [u'Institut Fur Ostseeforschung'],
    u'SHN': [u'Servicio de Hidrografia Naval'],
    u'SHOA': [u'Servicio Hidrografico y Oceanografico de la Armada', u'SHOA'],
    u'SHN': [u'Hidrografia Naval'],
    u'PML': [u'Plymouth Marine Laboratory'],
    u'WHPO': [u'WOCE Hydrographic Programme Office'],
    u'MHI': [u'Marine Hydrophysical Institute National Academy of Sciences of'
              ' Ukraine'],
    u'UL': [u'University of Liverpool'],
    u'Biologische Anstalt Helgoland': [u'Biologische Anstalt Helgoland'],
    u'IIM': [u'IIM'],
    u'NCSU': [u'North Carolina State University'],
    u'UTK': [u'University of Tennessee'],
    u'SOC': [u'Southampton Oceanography Centre'],
    u'SOES': [u'School of Ocean and Earth Sciences'],
    u'SOC-SOES': [
        u'Southampton Oceanography Centre - School of Ocean and Earth Sciences'],
    u'CSIRO': [u'Commonwealth Scientific and Industrial Research Organisation',
               u'CSIRO'],
    u'LPCM': [u'Laboratory De Physique Et Chimie Marines'],
    u'RSMAS': [u'Rosenstiel School of Marine and Atmospheric Research', 
               u'Rosenstiel School of Marine and Atmospheric Sciences'],
    u'MNHN': [u"Museum National d'Histoire Naturelle"],
    u'UCT': [u'University of Cape Town'],
    u'TU': [u'Tokai University'],
    u'NRIFS': [u'National Research Institute of Fisheries Science'],
    u'(HD) MSA': [
        u'Maritime Safety Agency',
        u'Hydrographic and Oceanographic Department\nJapan Coast Guard'],
    u'JMA': [u'Japan Meteorological Agency'],
    u'ORI': [u'Ocean Research Institute'],
    u'UW': [u'University of Washington'],
    u'UA': [u'University of Alaska'],
    u'STM': [u'Sanyo Technomarine'],
    u'NZOI': [u'New Zealand Oceanographic Institute'],
    u'HMO': [u'Hakodate Marine Observatory'],
    u'NMO': [u'Nagasaki Marine Observatory'],
    u'KMO': [u'Kobe Marine Observatory'],
    u'UH': [u'University of Hawaii'],
    u'MRI': [u'Marine Research Institute'],
    u'RSADU': [u'Remote Sensing Applications Development Unit'],
    u'NTU': [u'National Taiwan University'],
    u'FIAMS': [u'FIAMS'],
    u'CRC': [u'Antarctic CRC'],
    u'SPRS': [u'Swedish Polar Research Secretariat'],
    u'GSO': [u'Graduate School of Oceanography\nUniversity of Rhode Island'],
    u'BIOS': [u'Bermuda Institute of Ocean Sciences'],
    u'GEOMAR': [
        u'Leibniz-Institut für Meereswissenschaften an der Universität Kiel'],
    u'OSI': [u'Flinders University'],
    u'NIRE': [u'National Institute for Resources and Environment'], # Japan
    u'FA': [u'National Research Institute of Far Seas Fisheries'], # Japan
    u'GRGS': [u'Le Groupe de Recherche de Géodésie Spatiale'],
    u'PML': [u'Plymouth Marine Laboratory'], # noc.soton.ac.uk
    u'NOC': [u'National Oceanography Centre', u'NOC'], # Southampton, UK
    u'LPCM': [u'Laboratoire de Physique et Chimie Marines'],
    u'NWU': [u'Northwestern University'],
    u'UBC': [u'University of British Columbia'],
    u'IFREMER': [
        u"Institut français de recherche pour l'exploitation de la mer"],
}
known_institutions[u'NOAA/PMEL'] = known_institutions['PMEL']
known_institutions[u'NOAA-PMEL'] = known_institutions['PMEL']
known_institutions[u'IfMUH'] = known_institutions[u'IfMH']
known_institutions[u'JRD'] = known_institutions[u'JRC']
known_institutions[u'James Rennell Centre'] = known_institutions[u'JRC']
known_institutions[u'SOC-JRD'] = known_institutions[u'JRC']
known_institutions[u'IORAN'] = known_institutions[u'SOI']
known_institutions[u'IOAN'] = known_institutions[u'SOI']
known_institutions[u'Shirshov Institute of Oceanology'] = \
    known_institutions[u'SOI']


known_first_name_for_cruise = {
    49: 'Robert R.',
    90: 'W. John',
    109: 'W. Glen',
    113: 'W. Glen',
    126: 'Arnold L.',
    149: 'W. John',
    212: 'W. John',
    213: 'Robert R.',
    214: 'Robert R.',
    277: 'Gregory C.',
    278: 'Gregory C.',
    294: 'Arnold L.',
    324: 'Robert R.',
    384: 'David',
    401: 'Nicholas J. P.',
    462: 'W. Breck',
    523: 'Ben',
    559: 'Ben',
    560: 'Ben',
    575: 'Ben',
    579: 'Ben',
    580: 'Ben',
    581: 'Ben',
    584: 'Ben',
    595: 'Ben',
    645: 'Cho-Teng',
    646: 'Cho-Teng',
    649: 'Cho-Teng',
    650: 'Cho-Teng',
    651: 'Cho-Teng',
    652: 'Cho-Teng',
    653: 'Cho-Teng',
    658: 'Cho-Teng',
    750: 'Robert R.',
    764: 'David',
    793: 'Leif',
    870: 'Leif',
    973: 'Kevin T. M.',
    1063: 'Kevin T. M.',
    1296: 'W. Glen',
    1298: 'W. Glen',
    1338: 'Rodney J.',
}


known_first_name_given_last_name_for_cruise = {
    (461, 'Owens'): 'W. Breck',
    (848, 'Johnson'): 'Gregory C.',
}


known_duplicates = [
    'Church',
]


known_multiple_names = {
    'Bindoff': [u'Nathan L.', u'Nathan'],
    'Budeus': [u'Gereon', u''],
    'Bullister': [u'Dr. John L.', u'John L.', u'John', u''],
    'Curry': [u'Ruth G.', u'Ruth'],
    'Feely': [u'Richard A.', u'Richard'],
    'Freeland': [u'Howard J.', u'Howard'],
    'Gould': [u'W. John', u'W John'],
    'Hallock': [u'Zachariah R.', u''],
    'Hendry': [u'Ross M.', u'Ross'],
    'Henin': [u'Christian M.', u'Christian'],
    'Holfort': [u'J\xc5rgen', u''],
    'Ishii': [u'Masao', u''],
    'Jenkins': [u'Prof. William J.', u'William J.', u'William ', u'Bill'],
    'Kawano': [u'Mr. Takeshi', u'Takeshi'],
    'Key': [u'Dr. Robert M.', u'Robert M.', u'Robert ', u'Bob', u'Bpb', u''],
    'King': [u'Dr. Brian A.', u'Brian A.', u'Brian', u''], 
    'Kelly Falkner': [u''],
    'Koltermann': [u'K. Peter', u'K.-Peter'],
    'Lee': [u'Hoyle', u''],
    'Mercier': [u'Herl\xe9', u'Herle'],
    'McCartney': [u'Dr. Michael S.', u'Michael', u'Michael S.', u'Mike', u'Dr. Michael'],
    'Musgrave': [u'David L.', u'David'],
    'Nakano': [u'Toshiya', u''],
    'New': [u'Adrian L.', u''],
    'Olsen': [u'A', u''],
    'Pickart': [u'Robert', u'Robert '],
    'Quadfasel': [u'Detlef R.', u'R. Detlef'],
    'Rintoul': [u'Stephen R.', u'Steve R.'],
    'Rojas': [u'Ricardo L.', u'Ricardo'],
    'Rosenberg': [u'Mark', u''],
    'Schott': [u'Friedrich A.', u'Fritz'],
    'Sabine': [u'Christopher L.', u'Chris '],
    'Sloyan': [u'Bernadette M.', u'Bernardette', u'Bernadette'],
    'Smethie': [u'William A.', u'William', u'Bill'],
    'Swift': [u'Dr. James H.', u'James', u'Jim', u'Dr. James'],
    'Talley': [u'Dr. Lynne', u'Lynne'],
    'Uchida': [u'Hiroshi', u''],
    'van Aken': [u'Dr. Hendrik M.', u'', u'Hendrik M.'],
    'Warren': [u'Bruce A.', u''],
    'Watson': [u'Andrew J.', u'Andrew'],
    'Wijffels': [u'Susan E.', u'Susan'],
    'Williams': [u'Robert', u'', u'Robert '],
    'Zhang': [u'Huai-Min', u''],
}

def _name_to_person(importer, cruise, name):
    people = models.Person.get_all({'name_last': name})
    if len(people) == 1:
        return people[0]
    elif len(people) > 1:
        try:
            name_first = known_first_name_for_cruise[cruise.id]
            people = models.Person.get_all({'name_last': name,
                                            'name_first': name_first})
            if len(people) == 1:
                return people[0]
            elif len(people) > 1:
                implog.error(
                    u'More than one person for %s' % (name, name_first))
            else:
                implog.error(u'No person found for last: %s first: %s' % (
                    name, name_first))
        except KeyError:
            try:
                name_first = known_first_name_given_last_name_for_cruise[
                    (cruise.id, name)]
                people = models.Person.get_all({'name_last': name,
                                                'name_first': name_first})
                if len(people) == 1:
                    return people[0]
                elif len(people) > 1:
                    implog.error(
                        u'More than one person for %s' % (name, name_first))
                else:
                    implog.error(u'No person found for last: %s first: %s' % (
                        name, name_first))
            except KeyError:
                first_names = [p.name_first for p in people]
                ids = [p.id for p in people]
                implog.warn(u'More than one person for %s %r %s' % (
                    cruise.id, first_names, ids))
                if name in known_duplicates:
                    implog.info(u'Known duplicate %s' % name)
                    return people[0]
                if name in known_multiple_names.keys():
                    implog.info(u'Known multiple names %s' % name)
                    return people[0]
                implog.error(u'More than one person with last name %s and '
                              'unable to pick' % name)
        #raise ValueError(u'More than one person with last name %s and unable '
        #                  'to pick' % name)

    # No people found
    implog.warn('No person found for %s' % name)
    return _import_contact(importer, name, '')


def _name_to_inst(importer, name, p):
    if name is None or name == 'None' or name == '':
        return None

    try:
        names = known_institutions[name]
    except KeyError:
        names = []

    try:
        iname = p.institution.get('name')
        for partial_name in names:
            if partial_name in iname:
                return p.institution
    except AttributeError:
        pass

    try:
        replacement = names[0]
        return _import_inst(importer, replacement)
    except IndexError:
        return None


def _person_insts_to_pi(importer, cruise, person_insts):
    p = _name_to_person(importer, cruise, person_insts[0])
    i = _name_to_inst(importer, person_insts[1], p)
    return (p, i)


def _cchdo_pi_to_person_insts(pi, cruise, importer):
    """ Attempt to map the CCHDO PI/Chief Scientist string melange into Person
    Institutions pairs.

    """
    # Special cases
    if pi == 'Unknown':
        return []
    if pi == 'Miller/NOAA':
        return [_import_person_inst(
                    importer, u'Miller', u'Rick', u'NOAA',
                    u'Hendrick.V.Miller@noaa.gov')]
    if pi == 'Gaillard/NWU':
        return [_import_person_inst(
                    importer, u'Gaillard', u'Jean-François',
                    u'Northwestern University',
                    u'jf-gaillard@northwestern.edu')]
    if pi == 'JOHNSON':
        return [_import_person_inst(
                    importer, u'Johnson', u'Rodney J.',
                    u'Bermuda Institute of Ocean Sciences',
                    u'rod.johnson@bios.edu')]

    names = [unicode(x.strip(), 'unicode_escape') for x in pi.split(',')]
    pis = []
    for name in names:
        if ':' in name:
            name0, name1 = map(lambda x: x.strip(), name.split(':', 1))
            if '/' in name0:
                pis.extend([name0.split('/', 1), name1.split('/', 1)])
                continue
            if '/' in name1:
                name1, name2 = name1.split('/', 1)
                pis.extend([(name0, name2), (name1, name2)])
                continue
            else:
                pis.extend([(name0, None), (name1, None)])
                continue
        if '/' in name:
            name0, name1 = map(lambda x: x.strip(), name.split('/', 1))
            if name1 in known_names:
                pis.extend([(name0, None), known_names[name1]])
                continue
            if not name1 in known_institutions.keys() and \
               '/' in name1:
                name1, name2 = name1.split('/', 1)
                if name2 in known_institutions.keys():
                    pis.extend([(name0, name2), (name1, name2)])
                else:
                    pis.extend([(name0, None), (name1, None), (name2, None)])
                continue
            if '_' in name0 and '_' in name1:
                pis.extend([name0.split('_', 1), name1.split('_', 1)])
                continue
            pis.extend([(name0, name1)])
            continue
        try:
            pis.extend([known_names[name]])
            continue
        except KeyError:
            pass
        pis.append((name, None))

    return [_person_insts_to_pi(importer, cruise, pi) \
            for pi in filter(None, pis)]


def _import_inst(importer, institution_name):
    institutions = models.Institution.get_by_attrs(name=institution_name)
    if len(institutions) > 0:
        implog.info("Updating Institution %s" % (institution_name))
        institution = institutions[0]
    else:
        implog.info("Creating Institution %s" % (institution_name))
        institution = models.Institution(importer)
        institution.accept(importer)
        institution.save()
        institution.set_accept('name', institution_name, importer)
    return institution


def _import_contact(importer, name_last, name_first, institution=None,
                    email=None):
    inst_id = None
    if institution is not None:
        inst_id = institution.id
    return _import_person(importer, name_last, name_first, None,
                          institution=inst_id, email=email)


def _import_person_inst(importer, name_last, name_first,
                        institution_name, email):
    institution = _import_inst(importer, institution_name)
    person = _import_contact(importer, name_last, name_first,
                             institution, email)
    return (person, institution)


def _import_users(session, importer):
    implog.info("Importing users")
    users = session.query(legacy.User).all()
    for user in users:
        person = models.Person.get_one({'identifier': user.username})
        if not person:
            implog.info('Creating User %s' % user.username)
            person = _import_person(
                importer, None, user.username, user.username)
        else:
            implog.info('Updating User %s' % user.username)
        update_attr(person, 'password_hash', user.password_hash, importer)
        update_attr(person, 'password_salt', user.password_salt, importer)
        update_attr(person, 'id', user.id, importer)
        update_attr(person, 'import_id', user.id, importer)


def _import_contacts(session, importer):
    implog.info("Importing Contacts")
    for contact in session.query(legacy.Contact).all():
        person, inst = _import_person_inst(
            importer, _ustr2uni(contact.LastName),
            _ustr2uni(contact.FirstName), _ustr2uni(contact.Institute),
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
        person.set_accept('import_id', contact.id, importer)


def _import_cruise(importer, cruise):
    cs = models.Cruise.get_by_attrs(import_id=cruise.id)
    if len(cs) > 0:
        implog.info('Updating Cruise %s %s' % (cruise.id, cruise.ExpoCode))
        c = cs[0]
    else:
        implog.info('Creating Cruise %s %s' % (cruise.id, cruise.ExpoCode))
        c = models.Cruise(importer)
        c.accept(importer)
        c.save()
        c.set_accept('expocode', cruise.ExpoCode, importer)
        c.set_accept('import_id', cruise.id, importer)

    if cruise.Begin_Date and c.get('date_start', None) is None:
        c.set_accept('date_start', _date_to_datetime(cruise.Begin_Date), importer)
    if cruise.EndDate and c.get('date_end', None) is None:
        c.set_accept('date_end', _date_to_datetime(cruise.EndDate), importer)
    if cruise.link and c.get('link', None) is None:
        c.set_accept('link', cruise.link, importer)

    if cruise.Country and c.get('country', None) is None:
        countries = models.Country.get_by_attrs({'iso_3166-1': cruise.Country})
        if len(countries) > 0:
            implog.info('Updating Country %s' % cruise.Country)
            country = countries[0]
        else:
            implog.info('Creating Country %s' % cruise.Country)
            country = models.Country(importer)
            country.accept(importer)
            country.save()
            country.set_accept('iso_3166-1', cruise.Country, importer)
        c.set_accept('country', country.id, importer)

    if cruise.Ship_Name and c.get('ship', None) is None:
        ships = models.Ship.get_by_attrs(name=cruise.Ship_Name)
        if len(ships) > 0:
            implog.info('Updating Ship %s' % cruise.Ship_Name)
            ship = ships[0]
        else:
            implog.info('Creating Ship %s' % cruise.Ship_Name)
            ship = models.Ship(importer)
            ship.accept(importer)
            ship.save()
            ship.set_accept('name', cruise.Ship_Name, importer)
        c.set_accept('ship', ship.id, importer)

    if cruise.Alias:
        # Hope that Alias fields are all comma separated...
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
        programs = [x.strip() for x in cruise.Program.split(',')]
        for program in programs:
            collections.append(_import_Collection(importer, program, 'program').id)

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
        person_insts = _cchdo_pi_to_person_insts(cruise.Chief_Scientist,
                                                 cruise, importer)
        c.participants._clear()
        for pi in person_insts:
            c.participants._add(pi[0], 'Chief Scientist', pi[1])
        if c.participants:
            implog.debug('Participants for cruise %s: %s' % (cruise.id, c.participants))
        c.participants.save(importer)


def _import_cruises(session, importer):
    implog.info("Importing Cruises")

    cruises = session.query(legacy.Cruise).all()
    len_cruises = float(len(cruises))

    for i, c in enumerate(cruises):
        if i % 10 == 0:
            implog.info('%d / %d = %f' % (i, len_cruises, i / len_cruises))
        _import_cruise(importer, c)


def _import_track_lines(session, importer):
    tls = session.query(legacy.TrackLine).all()
    for tl in tls:
        try:
            wkt = session.scalar(tl.Track.wkt)
        except sqlalchemy.exc.OperationalError:
            implog.error("Unable to get track from CCHDO db for %s" % tl.id)
            continue
        try:
            linestring = shapely.wkt.loads(wkt)
        except shapely.geos.ReadingError:
            # There are some linestrings in the DB that are single point lines. Yes.
            # Turn them into a very short lines.
            point = tuple(shapely.wkt.loads(wkt.replace('LINESTRING', 'POINT')).coords)[0]
            pt_list = [point, point]
            linestring = LineString(pt_list)

        cruises = models.Cruise.get_by_attrs(expocode=tl.ExpoCode)
        if len(cruises) > 0:
            cruise = cruises[0]
        else:
            implog.warn('Unable to import track_line %s because the cruise '
                         '%s does not exist' % (tl.id, tl.ExpoCode))
            continue

        if cruise.track:
            implog.info('Updating %s track' % tl.ExpoCode)
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
                implog.info('Updating %s track' % tl.ExpoCode)
        else:
            implog.info('Creating %s track' % tl.ExpoCode)
            cruise.set_accept('track', linestring, importer)


def _import_person(signer, name_last, name_first,
                   identifier=None, institution=None, email=None):
    query = {}
    if name_last:
        query['name_last'] = _ustr2uni(name_last)
    if name_first:
        query['name_first'] = _ustr2uni(name_first)
    if identifier:
        query['identifier'] = identifier
    if institution:
        query['institution'] = institution
    if email:
        query['email'] = email

    persons = models.Person.get_all(query)
    if len(persons) > 0:
        implog.debug(u"Updating person %s" % query)
        return persons[0]

    implog.debug(u"Creating person %s" % query)

    # Make sure there is either an identifier or both names
    try:
        query['identifier']
    except KeyError:
        try:
            query['name_last']
        except KeyError:
            query['name_last'] = ''
        try:
            query['name_first']
        except KeyError:
            query['name_first'] = ''

    person = models.Person(**query)
    person.save()
    if signer is None:
        person.accept(person)
    else:
        person.accept(signer)
    return person


def _import_collections(session, importer):
    implog.info("Importing Collections")
    collections = session.query(legacy.Collection).all()
    for collection in collections:
        imported_collection = models.Collection.get_by_attrs(
            import_id=collection.id)
        if imported_collection:
            implog.info("Updating Collection %s" % collection.id)
            continue

        imported_collection = models.Collection.get_by_name(collection.Name)
        if imported_collection:
            implog.info("Updating Collection %s" % collection.id)
            continue

        implog.info("Creating Collection %s" % collection.id)
        import_collection = models.Collection(importer)
        import_collection.save()
        import_collection.accept(importer)
        import_collection.set_accept('names', [collection.Name], importer)
        import_collection.set_accept('import_id', collection.id, importer)


def _import_collections_cruises(session, importer):
    implog.info("Importing CollectionsCruises")
    collections_cruises = session.query(legacy.CollectionsCruise).all()
    for cc in collections_cruises:
        if cc.collection is None or cc.cruise is None :
            implog.warn(
                'CollectionCruises pair (cruise %d, collection %d) is bad' % (
                    cc.cruise_id, cc.collection_id))
            continue

        cruises = models.Cruise.get_by_attrs(import_id=cc.cruise.id)
        if len(cruises) > 0:
            cruise = cruises[0]
        else:
            implog.warn('Bad cruise %d' % cc.cruise.id)
            continue

        collections = models.Collection.get_by_attrs(import_id=cc.collection.id)
        if len(collections) > 0:
            collection = collections[0]
        else:
            implog.warn('Bad collections %d' % cc.collection.id)
            continue

        present = True
        cruise_collections = cruise.get('collections')
        if collection.id in cruise_collections:
            implog.info('Collection already present in Cruise collections')
        else:
            implog.info('Adding Collection %s to Cruise collections' % \
                         collection.id)
            cruise.set_accept('collections',
                              cruise_collections + [collection.id], importer)


def _import_contacts_cruises(session, importer):
    implog.info("Importing ContactsCruises")
    contacts_cruises = session.query(legacy.ContactsCruise).all()
    for cc in contacts_cruises:
        if not cc.cruise:
            implog.info("Bad Cruise ID %s" % (cc.cruise_id))
            continue
        if not cc.contact:
            implog.info("Bad Contact ID %s" % (cc.contact_id))
            continue

        cruises = models.Cruise.get_by_attrs(import_id=cc.cruise_id)
        if len(cruises) > 0:
            cruise = cruises[0]
        else:
            implog.warn("Could not import ContactsCruise pair because cruise "
                         '%s does not exist.' % cruise)
            continue

        persons = models.Person.get_by_attrs(import_id=cc.contact.id)
        if len(persons) > 0:
            person = persons[0]
        else:
            implog.warn("Could not import ContactsCruise pair because person "
                         '%s does not exist.' % cc.contact.id)
            continue

        role = cc.function
        if not role:
            role = 'Chief Scientist'
        try:
            if person in [pi['person'] for pi in cruise.participants[role]]:
                implog.info(
                    "Updating participant %s %s to %s" % (person, role, cruise))
                continue
        except KeyError:
            pass
        implog.info(
            "Importing participant %s %s to cruise %s" % (person, role,
                                                          cruise.id))
        implog.debug(cruise.participants)
        implog.debug(person)
        cruise.participants.add(person, role, importer)
        implog.debug(cruise.participants)


def _import_events(session, importer):
    implog.info("Importing Events")

    events = session.query(legacy.Event).all()
    len_events = len(events)
    for i, event in enumerate(events):
        if i % 100 == 0:
            implog.info('%d/%d = %f' % (i, len_events,
                                        float(i) / len_events))
        note = models.Note.get_one({'import_id': event.ID})
        if note:
            implog.info("Updating Event %s" % event.ID)
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

            person = _import_person(importer, event.LastName, event.First_Name)
            note = models.Note(person, body, action, data_type, summary)
            note.creation_stamp.timestamp = \
                _date_to_datetime(event.Date_Entered)
            note.import_id = event.ID
            note.save()

            cruises = models.Cruise.get_by_attrs(expocode=event.ExpoCode)
            for cruise in cruises:
                implog.info("Creating Event %s for cruise %s" % (
                    event.ID, cruise.get('import_id')))
                cruise.add_note(note)


def _import_old_submissions(session, importer, sftp_cchdo):
    implog.info("Importing Old Submissions")
    subs = session.query(legacy.OldSubmission).all()

    # Group submissions by folder
    map_submissions = {}
    for sub in subs:
        try:
            submission = map_submissions[sub.Folder]
        except KeyError:
            submissions = models.OldSubmission.get_by_attrs(folder=sub.Folder)
            if len(submissions) > 0:
                implog.info('Updating OldSubmission %s' % sub.Folder)
                submission = submissions[0]
            else:
                implog.info('Creating OldSubmission %s' % sub.Folder)
                submission = models.OldSubmission(importer)
                submission.creation_stamp['timestamp'] = sub.created_at
                submission.accept(importer)
                submission.judgment_stamp['timestamp'] = sub.updated_at
                submission.folderfolder = sub.Folder
                submission.date = _date_to_datetime(sub.Date)
                submission.stamp = sub.Stamp
                submission.line = sub.Line
                submission.submitter = sub.Name
                submission.files = []
                submission.save()
            map_submissions[sub.Folder] = submission

        files = submission.files_
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
            id = models.fs().put(
                file, filename=sub.Filename, old_submission=True)
            files += [id]
            submission.files_ = files
            submission.save()


def _import_spatial_groups(session, importer):
    implog.info("Importing Spatial groups")
    sgs = session.query(legacy.SpatialGroup).all()
    for sg in sgs:
        collection = _import_Collection(importer, sg.area, 'spatial_group')
        basins = []
        if sg.atlantic == '1':
            basins.append('atlantic')
        if sg.arctic == '1':
            basins.append('arctic')
        if sg.pacific == '1':
            basins.append('pacific')
        if sg.indian == '1':
            basins.append('indian')
        if sg.southern == '1':
            basins.append('southern')
        collection.set_accept('basins', basins, importer)

        cruises = models.Cruise.get_by_attrs(expocode=sg.expocode)
        if len(cruises) > 0:
            implog.info("Updating Cruise %s for spatial_groups" % sg.expocode)
            cruise = cruises[0]
            collections = libcchdo.fns.uniquify(cruise.collections + [collection])
            if cruise.collections != collections:
                a = cruise.get_attr('collections')
                ids = [c.id for c in collections]
                if a:
                    a.value = ids
                    a.save()
                else:
                    cruise.set_accept('collections', ids, request.user)


def _import_internal(session, importer):
    """ Internal maps a cruise to a basin """
    implog.info("Importing Internal")
    internals = session.query(legacy.Internal).all()
    for i in internals:
        cruises = models.Cruise.get_by_attrs(expocode=i.expocode)
        if len(cruises) > 0:
            implog.info("Updating Cruise %s for internal" % i.expocode)
            cruise = cruises[0]
        else:
            implog.info("Creating Cruise %s for internal" % i.expocode)
            cruise = models.Cruise(importer)
            cruise.accept(importer)
            cruise.save()
            cruise.set_accept('expocode', i.expocode, importer)
            cruise.set_accept('import_id', 'internal', importer)
        collection = _import_Collection(importer, i.Basin, 'basin')
        try:
            a = cruise.get_attr('basin')
            a.value = libcchdo.fns.uniquify(a.value + [collection.id])
            a.save()
        except KeyError:
            cruise.set_accept('basin', [collection.id], importer)


def _import_unused_tracks(session, importer):
    implog.info("Importing unused tracks")
    ts = session.query(legacy.UnusedTrack).all()
    for t in ts:
        cruises = models.Cruise.get_by_attrs(expocode=t.expocode)
        if len(cruises) > 0:
            implog.info("Updating Cruise %s for unused track" % t.expocode)
            cruise = cruises[0]
        else:
            implog.info("Creating Cruise %s for unused track" % t.expocode)
            cruise = models.Cruise(importer)
            cruise.accept(importer)
            cruise.save()
            cruise.set_accept('expocode', t.expocode, importer)
            cruise.set_accept('import_id', 'unused_track', importer)
        collection = _import_Collection(importer, t.Basin, 'basin')
        try:
            a = cruise.get_attr('basin')
            a.value = libcchdo.fns.uniquify(a.value + [collection.id])
            a.save()
        except KeyError:
            cruise.set_accept('basin', [collection.id], importer)


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


def _import_parameter_descriptions(importer):
    implog.info("Importing parameter descriptions")
    std_session = std.session()
    std_session.autoflush = False
    try:
        parameters = lcconvert.all_parameters(std_session)
    except sqlalchemy.exc.OperationalError, e:
        implog.error("unable to convert parameters: %s" % e)
        parameters = []
    finally:
        std_session.close()
    for parameter in parameters:
        parameters = models.Parameter.get_by_attrs(name=parameter.name)
        if len(parameters) > 0:
            implog.info("Updating Parameter %s" % parameter.name)
            p = parameters[0]
        else:
            implog.info("Creating Parameter %s" % parameter.name)
            p = models.Parameter(importer)
            p.accept(importer)
            p.save()
            p.set_accept('name', parameter.name, importer)
            p.set_accept('full_name', parameter.full_name, importer)
            p.set_accept('name_netcdf', parameter.name_netcdf, importer)
            p.set_accept('description', parameter.description, importer)
            p.set_accept('format', parameter.format, importer)
            if parameter.units:
                p.set_accept('unit',
                    _import_unit(importer, parameter.units).id, importer)
            p.set_accept('bounds', (parameter.bound_lower,
                                    parameter.bound_upper), importer)
            aliases = [a.name for a in parameter.aliases]
            p.set_accept('aliases', aliases, importer)


def _import_parameter_groups(session, importer):
    std_session = std.session()
    groups = session.query(legacy.ParameterGroup).all()
    std_session.close()
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
            porder = []
            for p in order:
                parameters = models.Parameter.get_by_attrs(name=p)
                if len(parameters) < 1:
                    implog.warn("Could not find parameter %s for order" % p)
                    parameter = models.Parameter(importer)
                    parameter.accept(importer)
                    parameter.save()
                    parameter.set_accept('name', p, importer)
                    parameter.set_accept('in_groups_but_did_not_exist', True, importer)
                else:
                    parameter = parameters[0]
                porder.append(parameter.id)
            g.set_accept('order', porder, importer)


def _import_bottle_dbs(session, importer):
    implog.info("Importing Bottle DBs")
    # TODO regenerate bottle parameter information cache
    implog.info("Omitting import in favor of regenerating this information")


def _import_parameter_status(session, importer):
    implog.info("Importing parameter statuses")
    implog.info("Omitting import because information is never used in site "
                 "and probably is replaced by documents.preliminary")


def _import_parameters(session, importer):
    implog.info("Importing parameters (chiscis responsible)")

    codes = {}
    for code in session.query(legacy.Codes).all():
        codes[int(code.Code)] = code.Status

    parameters = {}
    for param in legacy.CruiseParameterInfo._PARAMETERS:
        ps = models.Parameter.get_by_attrs(name=param)

        if len(ps) > 0:
            implog.info("Found Parameter %s for CPI" % param)
            parameter = ps[0]
        else:
            implog.warn("Created Parameter %s for CPI" % param)
            parameter = models.Parameter(importer)
            parameter.accept(importer)
            parameter.save()
            parameter.set_accept('name', param, importer)
            parameter.set_accept('import_id', 'cruise_param_info', importer)
        parameters[param] = parameter

    for p in session.query(legacy.CruiseParameterInfo).all():
        cruise = models.Cruise.get_by_attrs(expocode=p.ExpoCode)
        if len(cruise) > 0:
            implog.info("Found Cruise %s for CPI" % p.ExpoCode)
            cruise = cruise[0]
        else:
            implog.info("Creating Cruise %s for CPI" % p.ExpoCode)
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
                    implog.warn("Bad Status while importing 'parameters' row "
                                 "%d parameter %s" % (p.id, param))
                status = None
            except KeyError:
                implog.warn("Unrecognized status while importing 'parameters' "
                             "row %d parameter %s" % (p.id, param))
                status = None

            try:
                pi = _ustr2uni(getattr(p, param + '_PI'))
                pi, inst = _cchdo_pi_to_person_insts(pi)
            except TypeError:
                pi = None
                inst = None
            
            try:
                d = _date_to_datetime(getattr(p, param + '_Date'))
            except TypeError:
                d = None

            param_infos.append({'parameter': parameter.id, 'status': status,
                                'pi': pi, 'inst': inst, 'ts': d})

        try:
            attr = cruise.get_attr('parameter_informations')
            attr.value = param_infos
            attr.creation_stamp = models.Stamp(importer)
            attr.judgment_stamp = models.Stamp(importer)
            attr.save()
        except KeyError:
            cruise.set_accept('parameter_informations', param_infos, importer)


def _import_submissions(session, importer, sftp_cchdo):
    implog.info("Importing Submissions")

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
            implog.info("Updating Submission %d" % sub.id)
            continue
        else:
            implog.info("Creating Submission %d" % sub.id)
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

            submitter, inst = _import_person_inst(importer, name, '', inst, email)
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
            file_path = sub.file

            if expocode:
                submission.expocode_ = _ustr2uni(expocode)
            if ship_name:
                submission.ship_name_ = _ustr2uni(ship_name)
            if line:
                submission.line_ = _ustr2uni(line)
            if action:
                submission.action_ = _ustr2uni(action)
            if notes:
                submission.add_note(
                    models.Note(submitter, _ustr2uni(notes)).save())

            file = None
            with sftp_dl(sftp_cchdo, file_path) as file:
                if not file:
                    submission.remove()
                    implog.warn('unable to get file for Submission %s', sub.id)
                    continue

                file_name = os.path.basename(file_path)
                actual_file = FieldStorage()
                actual_file.filename = file_name

                # ZipFile.open will clobber a file object so make a copy.
                temp = StringIO()
                temp.write(file.read())
                file.seek(0)

                if file_name.startswith('multiple_files') and file_name.endswith('.zip'):
                    # unzip multiple_files zips that are actually just one file
                    with zipfile.ZipFile(temp) as zf:
                        infos = zf.infolist()
                        if len(infos) == 1:
                            file = zf.open(infos[0])
                            actual_file.filename = infos[0].filename
                        actual_file.file = file
                        submission.store_file(actual_file)
                else:   
                    actual_file.file = file
                    submission.store_file(actual_file)
                submission.save()

            public = public_to_bool(sub.public, action)
            # 2011-09-16 myshen
            # cberys has determined "assigned" corroborates
            # non-public status and is generally redundant. More importantly it
            # is not used.
            # "assimilated" is used to color code the submission table according
            # to whether submission has been put in the queue.
            assimilated = bool(sub.assimilated)
            submission.public_ = public
            submission.attached_ = assimilated
            submission.save()
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
    implog.info("Importing queue files")

    re_docs = re.compile('Cruise (report|information)', re.IGNORECASE)

    queue_files = session.query(legacy.QueueFile).all()
    for qfile in queue_files:
        cruises = models.Cruise.get_by_attrs(expocode=qfile.expocode)
        if not cruises:
            implog.warn("Missing cruise for queue file %s" % qfile.expocode)
            continue
        else:
            cruise = cruises[0]

        queue_file = models._Attr.get_one({'import_id': qfile.id,
                                           'key': 'data_suggestion'})
        unprocessed_input = qfile.unprocessed_input.strip()
        if not queue_file:
            implog.info('Creating Queue File %s' % qfile.id)

            with sftp_dl(sftp_cchdo, unprocessed_input) as file:
                if file is None:
                    implog.warn(
                        "Missing queue file %s" % unprocessed_input)
                    implog.info("Skipping queue record import")
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
            if not name:
                submitter = importer
            else:
                submitter, inst = _import_person_inst(
                    importer, name, '', '', '')

            queue_file.creation_stamp['person'] = submitter.id
            date_received = None
            if qfile.date_received:
                date_received = _date_to_datetime(qfile.date_received)
            else:
                date_received = _get_mtime(sftp_cchdo, unprocessed_input)
            queue_file.creation_stamp['timestamp'] = date_received
            queue_file.save()
        else:
            implog.info('Updating Queue File %s' % qfile.id)

        if qfile.cchdo_contact:
            contact = models.Person.get_one({'identifier': qfile.cchdo_contact})
            if contact:
                queue_file.acknowledge(contact)
            else:
                implog.warn(
                    "CCHDO contact %s is not recognized" % qfile.cchdo_contact)

        if qfile.merged == 1:
            date_merged = qfile.date_merged
            queue_file.accept(importer)
            if not date_merged:
                implog.warn('No date merged for merged file. Obtaining from '
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


_DOCS_TYPE_IGNORE = [
    'Coord info', 'Coordinates?', 'Data History HTML', 'Directory Description',
    'GMT info File', 'Index HTML File', 'Old Index HTML File', 'Person HTML',
    'Type HTML',
]


_DOCS_FILES_IGNORE = [
    'ExpoCode', 'work', '.passwd', 'test', 'TMP', '.DS_Store', 'CTD', 
    '.directory', 'chg_cst_bot.pl', 'fort.7', 'KARLA_DEMO',
    'gmt_statrack_sumfile.csh', 'shell.gmt_statrack',
    'shell.gmt_statrack_polar', 'TEMP', 'KML', 
]


_DOCS_RE_IGNORE = map(re.compile, [
    '.*~', '.*\.xml', '.gmt.*', 'index\.htm.*', '\.\d+', '.*na\.txt',
    '.*inv_(hyd|ctd)\.txt', '.*trk\.(pdf|ps)', '.*(oxy|sal)\.ps.*',
    '.*_check\.txt', 
])


_DOCS_TYPE_TO_PYCCHDO_TYPE = {
    'Directory': 'directory',
    'CTD File': 'woce_ctd',
    'Documentation': 'doc_txt',
    'PDF Documentation': 'doc_pdf',
    'Encrypted file': 'encrypted',
    'Exchange Bottle': 'bottle_exchange',
    # All bottle exchange zips are actually bottle exchange that are zipped for
    # HOT OR missing & mislabeled files for SAVE.
    'Exchange Bottle (Zipped)': 'ignore',
    'Exchange CTD': 'ctd_exchange',
    'Exchange CTD (Zipped)': 'ctdzip_exchange',
    'JGOFS File': 'jgofs',
    'Small Plot': 'map_thumb',
    'Large Plot': 'map_full',
    'Large Volume file': 'large_volume_samples_woce',
    'Matlab file': 'matlab',
    'NetCDF Bottle': 'bottlezip_netcdf',
    'NetCDF CTD': 'ctdzip_netcdf',
    'SEA file': 'sea',
    'Sum File': 'sum',
    'WCT CTD File': 'ctd_wct',
    'Woce Bottle': 'bottle_woce',
    'Woce CTD (Zipped)': 'ctdzip_woce',
    'Woce Sum': 'sum_woce',
}


def _import_documents_for_cruise(importer, sftp_cchdo, docs, cruise, su_lock):
    expocode = cruise.get('expocode')
    if docs:
        implog.info("Importing documents for %s" % expocode)
    else:
        return

    implog.setLevel(logging.INFO)
    mapped_docs = {}
    for doc in docs:
        if doc.FileType in _DOCS_TYPE_IGNORE:
            implog.debug('Ignoring doc of type %s: %s' % (doc.FileType,
                                                          doc.FileName))
            continue

        try:
            pycchdo_type = _DOCS_TYPE_TO_PYCCHDO_TYPE[doc.FileType]
        except KeyError:
            basename = os.path.basename(doc.FileName)
            if doc.FileType == 'Unrecognized' and \
                (basename == 'ExpoCode' or 
                 basename == '.passwd' or
                 basename == '.password' or
                 basename == 'error_File'):
                pycchdo_type = 'ignore'
            else:
                implog.warn('Unmapped doc type %s: %s' % (doc.FileType,
                                                          doc.FileName))
                continue
        if pycchdo_type == 'bottle_exchange':
            if doc.FileName.endswith('lv_hy1.csv'):
                pycchdo_type = 'large_volume_samples_exchange'

        try:
            if doc.LastModified > mapped_docs[pycchdo_type].LastModified:
                implog.warning('%s already exists: old %s new %s' % (
                    pycchdo_type, mapped_docs[pycchdo_type].FileName,
                    doc.FileName))
                mapped_docs[pycchdo_type] = doc
        except KeyError:
            mapped_docs[pycchdo_type] = doc
            implog.debug('Mapped %s %s' % (pycchdo_type, doc.FileName))
    implog.setLevel(logging.DEBUG)

    try:
        dir = mapped_docs['directory'].FileName
        del mapped_docs['directory']
    except KeyError:
        implog.error('%s has no directory registered' % expocode)
        return

    if not cruise.get('data_dir', None):
        cruise.set_accept('data_dir', dir, importer)

    accounted_files = []
    for type, doc in mapped_docs.items():
        if type == 'ignore':
            continue

        id = doc.id
        if cruise.find_attrs({'key': type, 'import_id': id}).count() > 0:
            implog.info('%s already imported' % id)
            continue

        preliminary = bool(doc.Preliminary)
        if preliminary:
            implog.info('Marking file %s for %s preliminary' % (type, expocode))
            status_key = '%s_status' % type
            if cruise.find_attrs({'key': status_key,
                                  'import_id': id}).count() < 1:
                statuses = cruise.get(status_key, [])
                if 'preliminary' not in statuses:
                    statuses.extend(['preliminary'])
                    attr = cruise.set_accept(status_key, statuses, importer)
                    attr.import_id = id
                    attr.save()

        size = int(doc.Size)
        try:
            lstat = sftp_cchdo.lstat(doc.FileName)
            if lstat.st_size != size:
                implog.warn(
                    'File %s has mismatched size. Expected %s got %s' % (
                        doc.FileName, size, lstat.st_size))
        except IOError:
            implog.error('Missing file %s' % doc.FileName)
            continue

        stamps = doc.Stamp

        field = FieldStorage()
        field.filename = os.path.basename(doc.FileName)
        field.type = mimetypes.guess_type(doc.FileName)[0]

        with sftp_dl(sftp_cchdo, doc.FileName) as file:
            field.file = file
        if not field.file:
            implog.error('Unable to download %s. Skipping' % doc.FileName)
            continue

        attr = cruise.set_accept(type, field, importer)

        date_creation = doc.Modified
        date_accepted = doc.LastModified
        attr.creation_stamp.timestamp = date_creation
        attr.judgment_stamp.timestamp = date_accepted

        attr.import_filepath = doc.FileName
        attr.import_id = id
        attr.save()

        accounted_files.append(field.filename)
    accounted_files.extend(_DOCS_FILES_IGNORE)

    if cruise.find_attrs({'key': 'unaccounted',
                          'import_id': cruise.id}).count() > 0:
        implog.info('%s unaccounted already imported' % cruise.id)
        return

    any_unaccounted = False
    remote_dir = os.path.dirname(doc.FileName)
    # Use a shorter temp root so long path names don't get too long. Mac OS
    # X limits to 1024 bits.
    su_lock.acquire()
    local_dir = tempfile.mkdtemp(dir='/tmp')
    su_lock.release()
    implog.debug('allocated local tempdir %s' % local_dir)
    try:
        dirlist = sftp_cchdo.listdir(remote_dir)
    except IOError:
        implog.error(
            'Could not list remote dir %s to find unaccounted files' % 
            remote_dir)
        return
    for entry in dirlist:
        if entry in _DOCS_FILES_IGNORE:
            continue
        if entry in accounted_files:
            continue
        accounted = False
        for regexp in _DOCS_RE_IGNORE:
            if regexp.match(entry):
                accounted = True
                continue
        if accounted:
            continue

        any_unaccounted = True
        implog.info('Not accounted: %s' % entry)

        remote_path = os.path.join(remote_dir, entry)
        local_path = os.path.join(local_dir, entry)

        remote_stat = sftp_cchdo.lstat(remote_path)

        if stat.S_ISDIR(remote_stat.st_mode):
            try:
                sftp_dl_dir(sftp_cchdo, remote_path, local_path, su_lock)
            except IOError, e:
                implog.error('Unable to download unaccounted dir %s' %
                               remote_path)
                implog.error(repr(e))
        else:
            try:
                sftp_cchdo.get(remote_path, local_path)
            except IOError, e:
                implog.error('Unable to download unaccounted file %s' %
                               remote_path)
                implog.error(repr(e))

        su_lock.acquire()
        with su():
            try:
                os.chmod(local_path, remote_stat.st_mode)
                os.chown(local_path, remote_stat.st_uid, import_gid)
                os.utime(local_path, (remote_stat.st_atime,
                                      remote_stat.st_mtime))
            except Exception, e:
                implog.error("Unable to chmod downloaded file: %s %s" %
                             (local_path, e))
        su_lock.release()

    unaccounted_archive = StringIO()
    ua_tar = tarfile.open(mode='w:bz2', fileobj=unaccounted_archive)
    su_lock.acquire()
    with su():
        with pushd(local_dir):
            ua_tar.add('.')
        ua_tar.close()
        shutil.rmtree(local_dir)
    su_lock.release()
    unaccounted_archive.seek(0)

    if any_unaccounted:
        field = FieldStorage()
        field.filename = 'unaccounted.tar.bz2'
        field.type = mimetypes.guess_type(field.filename)
        field.file = unaccounted_archive
        attr = cruise.set_accept('unaccounted', field, importer)
        attr.import_id = cruise.id
        attr.save()

    unaccounted_archive.close()


class DocumentsImporter(threading.Thread):
    def __init__(self, docs, importer, cruise, su_lock):
        threading.Thread.__init__(self)
        self.importer = importer
        self.cruise = cruise
        self.docs = docs
        self.ssh_sftp = (None, None)
        self.su_lock = su_lock

    def run(self):
        _import_documents_for_cruise(
            self.importer, self.ssh_sftp[1], self.docs, self.cruise,
            self.su_lock)
        implog.debug('imported docs for %s' % self.cruise.get('expocode', ''))


def _import_documents(session, importer):
    implog.info("Importing documents")

    # Instead of importing the documents table, go the other way around and
    # import documents for each cruise
    cruises = models.Cruise.get_all()
    len_cruises = float(len(cruises))

    su_lock = threading.Lock()

    importers = []
    for cruise in cruises:
        docs = session.query(legacy.Document).filter(
            legacy.Document.ExpoCode==cruise.get('expocode')).order_by(
            legacy.Document.LastModified.desc()).all()
        importers.append(DocumentsImporter(docs, importer, cruise, su_lock))

    sftp_pool = []
    implog.info("Opening %d SSH connections" % nthreads)
    for i in range(nthreads):
        try:
            ssh_cchdo = ssh_connect('cchdo.ucsd.edu')
            sftp_cchdo = ssh_cchdo.open_sftp()
        except paramiko.SSHException, e:
            implog.error(repr(e))
        sftp_pool.append((ssh_cchdo, sftp_cchdo))

    implog.info("Starting doc import with %d threads" % nthreads)
    active_importers = []
    while importers:
        for imp in active_importers:
            if not imp.is_alive():
                active_importers.remove(imp)
                sftp_pool.append(imp.ssh_sftp)
        while len(active_importers) < nthreads and importers:
            t = importers.pop()
            t.ssh_sftp = sftp_pool.pop()
            active_importers.append(t)
            t.start()
        time.sleep(0.5)
    for imp in active_importers:
        if imp.is_alive():
            imp.join()
    for ssh, sftp in sftp_pool:
        sftp.close()
        ssh.close()


class FakeWebObRequest(object):
    def __init__(self, date=None, remote_addr=None):
        self.date = date
        self.remote_addr = remote_addr


def _import_argo_files(session, importer, sftp_cchdo):
    implog.info("Importing Argo files")
    argo_files = session.query(legacy.ArgoFile).all()

    sftp_cchdo.chdir('/data/argo/files')

    for file in argo_files:
        argo_file = models.ArgoFile.get_one({
            'creation_stamp.timestamp': file.created_at})
        if not argo_file:
            implog.info('Creating Argo File (%s, %s)' % (file.filename,
                                                         file.created_at))
            argo_file = models.ArgoFile(importer)
            users = models.Person.get_by_attrs(import_id=file.user.id)
            if len(users) > 0:
                user = users[0]
            else:
                user = importer
            argo_file.creation_stamp.person = user.id
            argo_file.creation_stamp.timestamp = file.created_at
            argo_file.save()
        else:
            implog.info('Updating Argo File (%s, %s)' % (file.filename,
                                                         file.created_at))

        argo_file.text_identifier = file.expocode
        argo_file.description = file.description
        argo_file.display = file.display
        # Special case for missing.txt because there is no actual file.
        if file.filename != 'missing.txt':
            lstat = sftp_cchdo.lstat(file.filename)
            if stat.S_ISLNK(lstat.st_mode):
                # Attempt to find the cruise and corresponding file type to link
                symlink_target = sftp_cchdo.readlink(file.filename)
                file_type = libcchdo.fns.guess_file_type(symlink_target)
                expopath = os.path.join(os.path.dirname(symlink_target),
                                        'ExpoCode')
                expocode = None
                with sftp_dl(sftp_cchdo, expopath) as expo:
                    if expo:
                        expocode = expo.read().strip()
                cruises = models.Cruise.get_by_attrs(expocode=expocode)
                if expocode and len(cruises) > 0:
                    cruise = cruises[0]
                    if file_type:
                        # This method is more simple
                        argo_file.link(cruise, file_type)
                        continue
                    else:
                        a = models._Attr.get_one({
                            'import_filepath': symlink_target})
                        if a:
                            argo_file.link(cruise, a.key)
                            continue
                implog.warn('Unable to find cruise %s to link ArgoFile %s to. '
                            'Attempting download of file.' % (expocode,
                                                              file.created_at))
                with sftp_dl(sftp_cchdo, symlink_target) as f:
                    if f:
                        downloaded = FieldStorage()
                        downloaded.filename = os.path.basename(
                            file.filename)
                        downloaded.type = mimetypes.guess_type(
                            downloaded.filename)[0]
                        downloaded.file = f
                        argo_file.store_file(downloaded)
                    else:
                        implog.error(
                            'Unable to attach argo file by download')
            else:
                # File is not a link so just download and attach
                with sftp_dl(sftp_cchdo, file.filename) as f:
                    actual_file = FieldStorage()
                    actual_file.filename = file.filename
                    actual_file.type = mimetypes.guess_type(
                        file.filename)[0]
                    actual_file.file = f
                    argo_file.store_file(actual_file)

        if file.downloads:
            argo_file.clear_requests()
            for dl in file.downloads:
                argo_file.add_request(FakeWebObRequest(date=dl.created_at,
                                                       remote_addr=dl.ip))

        argo_file.save()


def _import_cchdo_uname_uids(ssh_cchdo, importer):
    """ Uname/ids preserves the username/id mapping from the imported host

    This is necessary because of the stored tarballs of unaccounted files that
    need to be crossreferenced for permissions.

    """
    if not importer.get('cchdo_uname_uids'):
        implog.info('Import CCHDO username/ids')
        username_uid_map = {}
        (sshin, sshout, ssherr) = ssh_cchdo.exec_command(
            'dscl . list /Users UniqueID')
        for line in sshout:
            uname, uid = line.split()
            username_uid_map[uname] = int(uid)
        importer.set_accept('cchdo_uname_uids', username_uid_map, importer)


def main(argv):
    if os.geteuid() != 0:
        implog.error('pycchdo importer must be run as root in order to '
                     'import correct file ownerships')
        return 1
    # Drop effective privileges to _www, need to re-escalate later when
    # importing files
    os.setegid(import_gid)
    os.seteuid(import_uid)

    options = {
        'clear_db_first': False,
        'db_uri': 'mongodb://dimes.ucsd.edu:28017',
        #'db_uri': 'mongodb://dimes.ucsd.edu:28019',
        'db_search_index_path': '/var/cache/pycchdo_search_index',
    }

    opts, args = getopt.getopt(argv[1:], 'hc', ('help', 'clear'))
    for option, value in opts:
        if option in ('-h', '--help'):
            print _USAGE
            return 0
        if option in ('-c', '--clear'):
            options['clear_db_first'] = True

    implog.info("Connect to pycchdo (%s)" % options['db_uri'])
    models.init_conn(options['db_uri'])

    if options['clear_db_first']:
        implog.info('Clearing database')
        cchdo = models.cchdo()
        for coll in cchdo.collection_names():
            if not coll.startswith('system'):
                cchdo.drop_collection(coll)

    implog.info("Get/Create Importer to take blame")
    importer = _import_person(None, 'importer', 'CCHDO', 'CCHDO_importer')

    models.ensure_indices()

    # libcchdo does not need a local cache of parameter information. That will
    # be done during the import
    libcchdo.check_cache = False

    cchdo_import = True
    seahunt_import = True
    cchdo_import = False
    seahunt_import = False

    if cchdo_import:
        implog.info("Connecting to cchdo db")
        with db_session(legacy.session()) as session:
            session.autoflush = False

            _import_users(session, importer)
            _import_contacts(session, importer)
            _import_collections(session, importer)
            _import_cruises(session, importer)

            # TODO ensure that expocode is unique. or merge cruises that seem to
            # only just have different line numbers. Watch out for no_expocode

            _import_track_lines(session, importer)
            _import_collections_cruises(session, importer)
            _import_contacts_cruises(session, importer)

            _import_events(session, importer)

            _import_spatial_groups(session, importer)
            _import_internal(session, importer)
            _import_unused_tracks(session, importer)

            _import_parameter_descriptions(importer)
            _import_parameter_groups(session, importer)
            _import_bottle_dbs(session, importer)
            _import_parameter_status(session, importer)
            _import_parameters(session, importer)

            with sftp('cchdo.ucsd.edu') as (ssh_cchdo, sftp_cchdo):
                _import_submissions(session, importer, sftp_cchdo)
                _import_old_submissions(session, importer, sftp_cchdo)
                _import_queue_files(session, importer, sftp_cchdo)
                _import_documents(session, importer)
                _import_cchdo_uname_uids(ssh_cchdo, importer)
                _import_argo_files(session, importer, sftp_cchdo)

    if seahunt_import:
        implog.info('Connecting to seahunt db')
        with db_session(seahunt.session()) as session:
            seahunt.import_(session, importer)

    SearchIndex(options['db_search_index_path']).rebuild_index(clear=True)

    implog.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
