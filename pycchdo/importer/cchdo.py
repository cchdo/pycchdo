# -*- coding: utf8 -*-
from datetime import datetime
from cgi import FieldStorage
import stat
import tempfile
import os
import re
import tarfile
import shutil
from contextlib import closing
from copy import copy
from threading import current_thread, Thread, Lock
import traceback
import time
import zipfile
from tempfile import NamedTemporaryFile, SpooledTemporaryFile
from traceback import format_exc

from sqlalchemy.sql.expression import select, alias
from sqlalchemy.exc import OperationalError

from paramiko import SSHException

import shapely.wkt
from shapely.geos import ReadingError
from shapely.geometry import LineString

from webob.request import BaseRequest

import transaction

import libcchdo
from libcchdo.fns import uniquify
import libcchdo.db.model.convert as lcconvert
std = lcconvert.std
legacy = lcconvert.legacy

from pycchdo import models
from pycchdo.util import pyStringIO, StringIO, MemFile
from pycchdo.models.serial import (
    store_context, DBSession,
    Note,
    FSFile,
    Change,
    Cruise, Person, Institution, Country, Participant, Participants, 
    ArgoFile,
    Collection,
    Submission, OldSubmission, 
    Unit, Ship, Parameter,
    ParameterGroup, 
    RequestFor,
    ParameterInformation, 
    )
from pycchdo.models.types import DateTime
from pycchdo.importer import * 
from pycchdo.views import text_to_obj


__all__ = ['import_Collection', 'import_person']


remote_host = 'ghdc.ucsd.edu'


def get_by_import_id(cls, import_id):
    return cls.query().filter(cls.import_id == import_id).first()


def _log_progress(i, total):
    if total == 0:
        log.info(u'{0!r} / {1!r} = {2!r}'.format(i, total, 1.))
        return
    log.info(u'{0!r} / {1!r} = {2:g}'.format(i, total, float(i) / total))

        
def rewrite_dl_path_to_local(path):
    """Rewrite paths to reference the correct local path."""
    leader_data = '/data/'
    leader_submissions0 = (
        '/Library/Webserver/Documents/cchdo/public/submissions/')
    leader_submissions1 = (
        '/Library/WebServer/Documents/cchdo/public/submissions/')
    leader_submissions2 = (
        '/Library/WebServer/Documents/cchdo/submissions/')
    leader_submissions3 = (
        '/mnt/www-data/cchdo/public/submissions/')
    leader_old_submissions = (
        '/incoming_data/old_sys/')
    if path.startswith(leader_data):
        # data
        return '/var/cchdo-data/data/' + \
            path[len(leader_data):]
    elif path.startswith(leader_submissions0):
        # Submissions
        return '/var/cchdo-data/submissions/' + \
            path[len(leader_submissions0):]
    elif path.startswith(leader_submissions1):
        # Submissions
        return '/var/cchdo-data/submissions/' + \
            path[len(leader_submissions1):]
    elif path.startswith(leader_submissions2):
        # Submissions
        return '/var/cchdo-data/submissions/' + \
            path[len(leader_submissions2):]
    elif path.startswith(leader_submissions3):
        # Submissions
        return '/var/cchdo-data/submissions/' + \
            path[len(leader_submissions3):]
    elif path.startswith(leader_old_submissions):
        # OldSubmissions
        return '/var/cchdo-data/submissions/old_sys/' + \
            path[len(leader_old_submissions):]
    return path


def import_Collection(updater, name, type):
    """A Collection also will include a type as part of its identifier to
    differentiate between the fields it came from in the original database.

    """
    collection = Collection.query().filter(Collection._names.any(name=name)).\
        filter(Collection.type == type).first()
    if collection:
        log.info(u'Updating Collection {!r} {!r}'.format(name, type))
    else:
        log.info(u'Creating Collection {!r} {!r}'.format(name, type))
        collection = updater.create_accept(Collection)
        updater.attr(collection, 'names', [name])
        updater.attr(collection, 'type', type)
    return collection


def _namesonly(names):
    d = {}
    for name in names:
        d[name] = (name, None, )
    return d


codes_name_to_param_info_code = {
    'OnLine': 'online',
    'Reformatted': 'reformatted',
    'Submitted': 'submitted',
    'NotMeasured': 'not_measured',
    'Proposed': 'proposed',
    'No Information': 'no_information',
}


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


def _find_person_with_qlastn_name_first(qlastn, name_first):
    people = qlastn.filter(Person.name_first == name_first).all()
    if len(people) == 1:
        return people[0]
    elif len(people) > 1:
        log.error(
            u'Multiple people for {0} {1!r}'.format(str(qlastn), name_first))
    else:
        log.error(
            u'No person for {0} {1!r}'.format(str(qlastn), name_first))
    return None


def _name_to_person(updater, cruise, name):
    qlastn = Person.query().filter(Person.name_last == name)
    people = qlastn.all()
    if len(people) == 1:
        return people[0]
    elif len(people) > 1:
        try:
            name_first = known_first_name_for_cruise[cruise.id]
            person = _find_person_with_qlastn_name_first(
                qlastn, name_first)
            if person is not None:
                return person
        except KeyError:
            try:
                name_first = known_first_name_given_last_name_for_cruise[
                    (cruise.id, name)]
                person = _find_person_with_qlastn_name_first(
                    qlastn, name_first)
                if person is not None:
                    return person
            except KeyError:
                first_names = [p.name_first for p in people]
                ids = [p.id for p in people]
                log.warn(u'>1 match for {0!r} {1!r} (cruise {2})'.format(
                    first_names, ids, cruise.id))
                if name in known_duplicates:
                    log.info(u'Known duplicate %s' % name)
                    return people[0]
                if name in known_multiple_names.keys():
                    log.info(u'Known multiple names %s' % name)
                    return people[0]
        log.error(u'Unable to pick person for last name {0!r}'.format(name))

    # No people found
    log.warn('No person matched {0!r} (cruise {1!r})'.format(name, cruise.id))
    return _import_contact(updater, name, None, name=name)


def _name_to_inst(updater, name, p):
    if name is None or name == 'None' or name == '':
        return None

    try:
        names = known_institutions[name]
    except KeyError:
        names = []

    try:
        iname = p.institution.name or ''
        for partial_name in names:
            if partial_name in iname:
                return p.institution
    except AttributeError:
        pass

    try:
        replacement = names[0]
        return _import_inst(updater, replacement)
    except IndexError:
        return None


def _person_insts_to_pi(updater, cruise, person_insts):
    p = _name_to_person(updater, cruise, person_insts[0])
    if len(person_insts) > 1:
        i = _name_to_inst(updater, person_insts[1], p)
    else:
        i = None
    return (p, i)


def _cchdo_pi_to_person_insts(pi, cruise, updater):
    """Attempt to map the CCHDO PI/Chief Scientist string melange into Person
    Institutions pairs.

    """
    log.info(
        u'Mapping {0!r} {1} to person-institution'.format(pi, cruise.id))

    # Special cases
    if pi == 'Unknown':
        return []
    if pi == 'Miller/NOAA':
        return [_import_person_inst(
                    updater, u'Miller', u'Rick', u'NOAA',
                    u'Hendrick.V.Miller@noaa.gov')]
    if pi == 'Gaillard/NWU':
        return [_import_person_inst(
                    updater, u'Gaillard', u'Jean-François',
                    u'Northwestern University',
                    u'jf-gaillard@northwestern.edu')]
    if pi == 'JOHNSON':
        return [_import_person_inst(
                    updater, u'Johnson', u'Rodney J.',
                    u'Bermuda Institute of Ocean Sciences',
                    u'rod.johnson@bios.edu')]

    names = [_ustr2uni(x.strip()) for x in pi.split(',')]
    pis = []
    for name in names:
        if ':' in name:
            name0, name1 = map(lambda x: x.strip(), name.split(':', 1))
            if '/' in name0:
                pis.extend([name0.split('/', 1), name1.split('/', 1)])
                continue
            if '/' in name1:
                name1, name2 = name1.split('/', 1)
                pis.extend([(name0, name2, ), (name1, name2, )])
                continue
            else:
                pis.extend([(name0, None), (name1, None)])
                continue
        if '/' in name:
            name0, name1 = map(lambda x: x.strip(), name.split('/', 1))
            if name1 in known_names:
                pis.extend([(name0, None), known_names[name1]])
                continue
            if not name1 in known_institutions.keys() and '/' in name1:
                name1, name2 = name1.split('/', 1)
                if name2 in known_institutions.keys():
                    pis.extend([(name0, name2, ), (name1, name2, )])
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
        pis.append((name, None, ))
    return [_person_insts_to_pi(updater, cruise, pi) \
            for pi in filter(None, pis)]


def _import_inst(updater, name):
    if not name:
        return None
    name = _ustr2uni(name)
    inst = Institution.query().filter(Institution.name == name).first()
    if inst:
        log.info(u"Updating Institution {0!r}".format(name))
    else:
        log.info(u"Creating Institution {0!r}".format(name))
        inst = updater.create_accept(Institution)
        updater.attr(inst, 'name', name)
    # Since we matched on name, don't waste time setting it again
    return inst


def _import_contact(updater, name_last, name_first, institution=None,
                    email=None, name=None):
    return import_person(updater, name_last, name_first, None,
                         institution=institution, email=email, name=name)


def _import_person_inst(
        updater, name_last, name_first, institution_name, email):
    institution = _import_inst(updater, institution_name)
    person = _import_contact(
        updater, name_last, name_first, institution, email)
    return (person, institution)


def _import_users(session):
    log.info("Importing users")
    users = session.query(legacy.User).all()
    updater = _get_updater()
    for user in users:
        person = import_person(
            updater, None, user.username, user.username)
        updater.attr(person, 'password_hash', user.password_hash)
        updater.attr(person, 'password_salt', user.password_salt)
        person.import_id = str(user.id)


def _import_contacts(session):
    log.info("Importing Contacts")
    contacts = session.query(legacy.Contact).all()
    updater = _get_updater()
    for contact in contacts:
        person, inst = _import_person_inst(
            updater, _ustr2uni(contact.LastName), _ustr2uni(contact.FirstName),
            _ustr2uni(contact.Institute), _ustr2uni(contact.email))
        # Since CCHDO currently has no concept of an Institution separate from
        # a contact, differentiate them here.
        if contact.Address:
            updater.attr(person, 'address', _ustr2uni(contact.Address))
        if contact.telephone:
            updater.attr(person, 'phone', contact.telephone)
        if contact.fax:
            updater.attr(person, 'fax', contact.fax)
        if contact.title:
            updater.attr(person, 'title', contact.title)
        person.import_id = str(contact.id)


def _import_ship(updater, ship_name):
    ship = Ship.query().filter(Ship.name == ship_name).first()
    if ship:
        log.info('Updating Ship %s' % ship_name)
    else:
        log.info('Creating Ship %s' % ship_name)
        ship = updater.create_accept(Ship)
        updater.attr(ship, 'name', ship_name)
    return ship


known_country_names = {
    'AUS': 'Australia',
    'AUSTRALIA': 'Australia',
    'Australia': 'Australia',
    'CAN': 'Canada',
    'CHN': 'China',
    'FRA': 'France',
    'GER': 'Germany',
    'JAPAN': 'Japan',
    'JPN': 'Japan',
    'NET': 'Netherlands',
    'NTH': 'Netherlands',
    'SPN': 'Spain',
    'US': 'United States of America',
    'United States': 'United States of America',
    'indonesia': 'Indonesia',
    'ARG': 'Argentina',
    'RUS': 'Russia',
    'CHI': 'Chile',
    'BEL': 'Belgium',
    'BM': 'Bermuda',
    'FIN': 'Finland',
    'ICE': 'Iceland',
    'NEW': 'New Zealand',
    'POL': 'Poland',
    'NOR': 'Norway',
    'SWE': 'Sweden',
    'SA': 'South Africa',
    'TAI': 'Taiwan',
    'UK': 'United Kingdom',
    'UKR': 'Ukraine',
    'USA': 'United States of America',
}

known_country_2_codes = {
    'Australia': 'AU',
    'Canada': 'CA',
    'China': 'CN',
    'France': 'FR',
    'Germany': 'DE',
    'Japan': 'JP',
    'Netherlands': 'NL',
    'New Zealand': 'NZ',
    'Norway': 'NO',
    'Spain': 'ES',
    'United Kingdom': 'GB',
    'United States of America': 'US',
}


def _import_country(updater, country_name):
    if country_name in known_country_names.keys():
        country_name = known_country_names[country_name]
    country = Country.query().filter(
        Country.name == country_name).first()
    if country:
        log.info('Updating Country %s' % country_name)
    else:
        log.info('Creating Country %s' % country_name)
        country = updater.create_accept(Country)
        country.name = country_name
        try:
            country.alpha2 = known_country_2_codes[country_name]
        except KeyError:
            pass
    return country


def _import_cruise(cruise, dblock):
    import_id = str(cruise.id)
    with lock(dblock):
        updater = _get_updater()
        c = get_by_import_id(Cruise, import_id)
        if c:
            log.info('Updating Cruise %s %s' % (import_id, cruise.ExpoCode))
        else:
            log.info('Creating Cruise %s %s' % (import_id, cruise.ExpoCode))
            c = updater.create_accept(Cruise)

    c.import_id = import_id
    updater.attr(c, 'expocode', cruise.ExpoCode)

    if cruise.Begin_Date:
        updater.attr(
            c, 'date_start', _date_to_datetime(cruise.Begin_Date))
    if cruise.EndDate:
        updater.attr(c, 'date_end', _date_to_datetime(cruise.EndDate))
    if cruise.link:
        updater.attr(c, 'link', cruise.link)

    if cruise.Country:
        with lock(dblock):
            country = _import_country(updater, cruise.Country)
        updater.attr(c, 'country', country)

    if cruise.Ship_Name:
        with lock(dblock):
            ship = _import_ship(updater, cruise.Ship_Name)
        updater.attr(c, 'ship', ship)

    if cruise.Alias:
        # Hope that Alias fields are all comma separated...
        aliases = uniquify([x.strip() for x in cruise.Alias.split(',')])
        updater.attr(c, 'aliases', aliases)

    collections = []
    if cruise.Line:
        with lock(dblock):
            collections.append(import_Collection(updater, cruise.Line, 'WOCE line'))
    if cruise.Group:
        groups = [x.strip() for x in cruise.Group.split(',')]
        for group in groups:
            with lock(dblock):
                collections.append(import_Collection(updater, group, 'group'))
    if cruise.Program:
        programs = [x.strip() for x in cruise.Program.split(',')]
        for program in programs:
            with lock(dblock):
                collections.append(import_Collection(updater, program, 'program'))

    collections = uniquify(collections)
    updater.attr(c, 'collections', collections)
    
    log.debug('imported cruise %s' % cruise.id)


class CruisesImporter(Thread):
    def __init__(self, cruise, dblock):
        Thread.__init__(self)
        self.daemon = True
        self.cruise = cruise
        self.dblock = dblock

    def run(self):
        try:
            _import_cruise(self.cruise, self.dblock)
        except Exception, e:
            # Close out the transaction for this thread. This is done here in
            # case of fast return from import method.
            pass
        finally:
            transaction.commit()


def _import_cruises(session, nthreads):
    log.info("Importing Cruises")

    cruises = session.query(legacy.Cruise).all()

    dblock = Lock()

    # import_cruise cannot be multithreaded or duplicate objects will appear
    #importers = []
    #for cruise in cruises:
    #    importers.append(CruisesImporter(cruise, dblock))
    #_run_importers(importers, nthreads=1)

    plog = ProgressLog(cruises, nthreads)
    for cruise in cruises:
        _import_cruise(cruise, dblock)
        plog.log()
    

def _run_importers(importers, nthreads=6, remote_downloads=False, sleep=0.5):
    num_importers = float(len(importers))
    log.info(    
        "Running %d importers with %d threads" % (num_importers, nthreads))
    i = 0

    # setup sftp connections
    if remote_downloads:
        log.info("opening %d sftp connections" % nthreads)
        sftp_pool = []
        for i in range(nthreads):
            try:
                ssh_sftp = SFTP(remote_host)
            except SSHException, e:
                log.error(repr(e))
            sftp_pool.append(ssh_sftp)

    active_importers = []
    while importers:
        # Clean up importers that have finished
        for imp in active_importers:
            if not imp.is_alive():
                log.debug('importer finished %s' % imp.name)
                active_importers.remove(imp)
                if remote_downloads:
                    sftp_pool.append(imp.ssh_sftp)
                i += 1
                if i % nthreads == 0:
                    _log_progress(i, num_importers)
        # Start new importers when resources become available
        while ( len(active_importers) < nthreads and importers and
                (not remote_downloads or sftp_pool)):
            imp = importers.pop()
            if remote_downloads:
                imp.ssh_sftp = sftp_pool.pop()
                imp.downloader = copy(imp.downloader)
                imp.downloader.set_ssh_sftp(imp.ssh_sftp)
            active_importers.append(imp)
            imp.start()
            log.debug('importer started %s' % imp.name)
        time.sleep(sleep)

    # Wait for remaining importers to finish
    for imp in active_importers:
        if imp.is_alive():
            imp.join()
    _log_progress(i, num_importers)

    log.debug(u'closing sftp connections')
    if remote_downloads:
        for ssh_sftp in sftp_pool:
            ssh_sftp.__exit__(None, None, None)


def _import_track_lines(session):
    log.info(u'Importing track lines')
    tls = session.query(legacy.TrackLine).all()
    updater = _get_updater()
    for tl in tls:
        try:
            wkt = session.scalar(tl.Track.wkt)
        except OperationalError:
            log.error("Unable to get track from CCHDO db for %s" % tl.id)
            continue
        try:
            linestring = shapely.wkt.loads(wkt)
        except ReadingError:
            # There are some linestrings in the DB that are single point lines. Yes.
            # Turn them into a very short lines.
            point = tuple(shapely.wkt.loads(wkt.replace('LINESTRING', 'POINT')).coords)[0]
            pt_list = [point, point]
            linestring = LineString(pt_list)

        if not linestring:
            log.warn(
                u'Unable to convert trackline {0} to linestring'.format(tl.id))
            continue

        cruise = Cruise.query().filter(Cruise.expocode == tl.ExpoCode).first()
        if not cruise:
            log.info("Creating Cruise {0} for track line {1}".format(
                tl.ExpoCode, tl.id))
            cruise = updater.create_accept(Cruise)
            updater.attr(cruise, 'expocode', tl.ExpoCode)

        log.info(u'Track for {0}'.format(tl.ExpoCode))
        log.debug(u'{0}'.format(linestring))
        updater.attr(cruise, 'track', linestring)


def import_person(updater, name_last, name_first,
                  identifier=None, institution=None, email=None, name=None):
    query = {}
    dbquery = Person.query()
    if name_last:
        query['name_last'] = _ustr2uni(name_last)
        dbquery = dbquery.filter(Person.name_last == query['name_last'])
    if name_first:
        query['name_first'] = _ustr2uni(name_first)
        dbquery = dbquery.filter(Person.name_first == query['name_first'])
    if identifier:
        query['identifier'] = identifier
        dbquery = dbquery.filter(Person.identifier == query['identifier'])
    if email:
        query['email'] = email
        dbquery = dbquery.filter(Person.email == query['email'])
    if name:
        query['name'] = name
        dbquery = dbquery.filter(Person.name == query['name'])

    people = dbquery.all()

    person = None
    if people:
        if institution:
            person = None
            for p in people:
                if p.get('institution') == institution:
                    person = p
                    break
        else:
            person = people[0]
    if person:
        log.info(u"Updating person %s" % query)
    else:
        log.info(u"Creating person %s" % query)

        if updater is None:
            person = Person.create().obj
        else:
            person = Person.create(updater.importer).obj

        # Make sure there is either an identifier or both names
        person.set_id_names(
            identifier=query.get('identifier', None),
            name=query.get('name', None),
            name_last=query.get('name_last', None),
            name_first=query.get('name_first', None))
        person.email = query.get('email', None)

        if institution:
            updater.attr(person, 'institution', institution)
    return person


def _collections_merge(signer):
    """Merge all collections that are the same together."""
    cls = Collection

    # Pass 1: same name and same type
    log.info('Collection merge pass 1: same name, same type')
    sames = {}
    colls = cls.query().all()
    for coll in colls:
        key = '|'.join([''.join(filter(None, coll.names)), coll.type or ''])
        try:
            sames[key].append(coll)
        except KeyError:
            sames[key] = [coll]
    for same in sames.values():
        if len(same) < 2:
            continue
        log.info(u'Merging {} with {}'.format(same[0], same[1:]))
        same[0].merge_(signer, *same[1:])

    # Pass 2: same name and similar types
    log.info('Collection merge pass 2: same name, similar type')
    sames = {}
    colls = cls.query().all()
    for coll in colls:
        key = ''.join(filter(None, coll.names))
        try:
            sames[key].append(coll)
        except KeyError:
            sames[key] = [coll]
    for same in sames.values():
        if len(same) < 2:
            continue

        types = {}
        for s in same:
            key = s.type or ''
            try:
                types[key].append(s)
            except KeyError:
                types[key] = [s]

        if '' in types:
            s = types['']
            if 'group' in types:
                g = types['group'][0]
                g.merge(signer, *s)
            elif 'program' in types:
                p = types['program'][0]
                p.merge(signer, *s)
            elif 'WOCE line' in types:
                w = types['WOCE line'][0]
                w.merge(signer, *s)
        if 'group' in types:
            g = types['group']
            if 'WOCE line' in types:
                w = types['WOCE line'][0]
                w.merge(signer, *g)
            elif 'program' in types:
                p = types['program'][0]
                p.merge(signer, *g)
        if 'spatial_group' in types:
            s = types['spatial_group']
            if 'WOCE line' in types:
                w = types['WOCE line'][0]
                w.merge(signer, *s)


def _import_collections(session):
    log.info("Importing Collections")
    collections = session.query(legacy.Collection).all()
    updater = _get_updater()
    new_collections = Collection.query().all()

    imported_id_colls = {}
    for coll in new_collections:
        imported_id_colls[coll.import_id] = coll

    for coll in collections:
        import_id = str(coll.id)
        if import_id in imported_id_colls:
            log.info("Updating Collection %s %s" % (
                import_id, coll.Name))
            newcoll = imported_id_colls[import_id]
        else:
            log.info("Creating Collection %s %s" % (
                import_id, coll.Name))
            newcoll = updater.create_accept(Collection)
        updater.attr(newcoll, 'names', [coll.Name])
        newcoll.import_id = import_id


def _import_collections_cruises(session):
    log.info("Importing CollectionsCruises")
    updater = _get_updater()
    collections_cruises = session.query(legacy.CollectionsCruise).all()

    cruise_colls = {}
    colls_by_ids = {}

    for cc in collections_cruises:
        log.debug(u'{0} belongs to {1}'.format(cc.cruise_id, cc.collection_id))
        if cc.collection_id is None:
            log.warn(u'bad pair {0} {1}, no collection'.format(
                cc.collection_id, cc.cruise_id))
            continue
        if cc.cruise_id is None:
            log.warn(u'bad pair {0} {1}, no cruise'.format(
                cc.collection_id, cc.cruise_id))
            continue

        collid = cc.collection_id
        try:
            colls_by_ids[collid]
        except KeyError:
            colls_by_ids[collid] = get_by_import_id(Collection, str(collid))
            if not colls_by_ids[collid]:
                log.error('Could not find imported collection {0}'.format(collid))
                continue

        try:
            cruise_colls[cc.cruise_id].append(collid)
        except KeyError:
            cruise_colls[cc.cruise_id] = [collid]

    items = cruise_colls.items()
    plog = ProgressLog(items)
    for cid, collids in items:
        plog.log()
        cruise = get_by_import_id(Cruise, str(cid))
        if not cruise:
            log.error('Could not find imported cruise {0}'.format(cid))
            continue

        cruise_colls = cruise.collections
        new_colls = [colls_by_ids[cid] for cid in sorted(collids)]
        colls_to_add = list(set(new_colls) - set(cruise_colls))

        if not colls_to_add:
            continue

        log.info('Adding Collections {0} to Cruise {1} collections'.format(
            colls_to_add, cruise))
        updater.attr(cruise, 'collections', cruise_colls + colls_to_add)

    # Do this after all collections and changes to them have been imported
    # Otherwise there will be missing collections while importing.
    log.info('Merging same collections')
    _collections_merge(updater.importer)


def _import_collection_basins(session):
    """Add basin tags to collections according to how the ByOceanController
    used to find collections. This will be used by the basin view to generate
    the corresponding basin pages more efficiently than scanning cruises.

    """
    woce_line_basins = {}

    arctic = session.query(legacy.Cruise.Line, legacy.Cruise.Group)
    asub = arctic.with_entities(legacy.Cruise.Line).\
        filter(legacy.Cruise.Group.like('%arctic%')).\
        distinct().subquery()
    arctic = arctic.join((asub, asub.c.Line == legacy.Cruise.Line)).all()

    for line, groups in arctic:
        gs = set([u'arctic'])
        if groups:
            if 'Atlantic' in groups:
                gs.add(u'atlantic')
            if 'Indian' in groups:
                gs.add(u'indian')
            if 'Pacific' in groups:
                gs.add(u'pacific')
        try:
            woce_line_basins[line] |= gs
        except KeyError:
            woce_line_basins[line] = gs

    southern = session.query(legacy.Cruise.Line, legacy.Cruise.Group)
    ssub = southern.with_entities(legacy.Cruise.Line).\
        filter(legacy.Cruise.Group.like('%southern%')).\
        distinct().subquery()
    southern = southern.join((ssub, ssub.c.Line == legacy.Cruise.Line)).all()

    for line, groups in southern:
        gs = set([u'southern'])
        if groups:
            if 'Atlantic' in groups:
                gs.add(u'atlantic')
            if 'Indian' in groups:
                gs.add(u'indian')
            if 'Pacific' in groups:
                gs.add(u'pacific')
        try:
            woce_line_basins[line] |= gs
        except KeyError:
            woce_line_basins[line] = gs

    updater = _get_updater()
    for line, basins in woce_line_basins.items():
        coll = import_Collection(updater, line, 'WOCE line')
        basins = sorted(list(basins | set(coll.basins)))
        updater.attr(coll, 'basins', basins)


def _import_contacts_cruises(session):
    log.info("Importing ContactsCruises")
    updater = _get_updater()
    contacts_cruises = session.query(legacy.ContactsCruise).all()
    cruise_contacts = {}
    for cc in contacts_cruises:
        if not cc.cruise:
            log.info("Bad Cruise ID %s" % (cc.cruise_id))
            continue
        if not cc.contact:
            log.info("Bad Contact ID %s" % (cc.contact_id))
            continue

        role = cc.function
        if not role:
            role = 'Chief Scientist'

        cruiseid = str(cc.cruise_id)
        contactid = str(cc.contact_id)
        inst = cc.institution

        try:
            cruise_contacts[cruiseid].append((role, contactid, inst))
        except KeyError:
            cruise_contacts[cruiseid] = [(role, contactid, inst)]

        # TODO institution

    for cruiseid, contacts in cruise_contacts.items():
        cruise = get_by_import_id(Cruise, cruiseid)
        if not cruise:
            log.error("Could not import ContactsCruise pair because cruise "
                        '%s was not imported.' % cruise_id)
            continue

        participants = cruise.participants
        new_participants = []

        for role, contactid, inst in contacts:
            person = get_by_import_id(Person, contactid)
            if not person:
                log.error("Could not import ContactsCruise pair because person "
                         '{0} does not exist.'.format(contactid))
                continue
            inst = _import_inst(updater, inst)

            matching_participants = filter(
                lambda ppp: ppp.role == role and ppp.person == person,
                participants)

            if not matching_participants:
                new_participants.append(
                    Participant.create(role, person, inst))
                continue

            missing_inst = None
            present = False
            for ppp in matching_participants:
                if ppp.institution == inst:
                    # The participant is already present, we're done.
                    present = True
                    break
                if missing_inst is None and ppp.institution is None:
                    missing_inst = ppp
            if present:
                continue

            # The role-person matches don't have this institution
            if missing_inst:
                missing_inst.institution = inst
            else:
                log.info(u'All participants for {0} and {1} already have '
                         'institution. Adding new Participant.'.format(
                    role, person))
                new_participants.append(
                    Participant.create(role, person, inst))

        cruise.set(updater.importer,
            'participants', participants + new_participants)


def _import_events(session):
    log.info("Importing Events")

    updater = _get_updater()
    cache_person = {}

    events = session.query(legacy.Event).all()
    plog = ProgressLog(events)
    for event in events:
        plog.log()
        event_id = str(event.ID)
        note = get_by_import_id(Note, event_id)
        if note:
            log.info("Updating Event {0}".format(event_id))
            continue

        cruises = Cruise.query().filter(Cruise.expocode == event.ExpoCode).all()
        # No cruises to add the events to? Don't do the work.
        if not cruises:
            log.error(u"Event {0}'s cruise {1!r} does not exist".format(
                event_id, event.ExpoCode))
            continue

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
        lname = event.LastName.strip()
        fname = event.First_Name.strip()
        try:
            person = cache_person[(lname, fname)]
        except KeyError:
            person = import_person(updater, lname, fname)
            cache_person[(lname, fname)] = person

        note = Note(person, body, action, data_type, summary)
        note.ts_c = _date_to_datetime(event.Date_Entered)
        note.import_id = event_id

        for cruise in cruises:
            log.info("Creating Event {0} for cruise {1} {2}".format(
                event_id, event.ExpoCode, cruise.id))
            cruise.change._notes.append(note)


_known_bad_old_submissions = [
]


def _import_old_submissions(session, downloader):
    log.info("Importing Old Submissions")
    updater = _get_updater()
    subs = session.query(legacy.OldSubmission).all()

    # Group OldSubmissions by folder into one submission per folder
    map_submissions = {}
    for sub in subs:
        try:
            map_submissions[sub.Folder].append(sub)
        except KeyError:
            map_submissions[sub.Folder] = [sub]

    for folder, subs in map_submissions.items():
        submission = OldSubmission.query().filter(
            OldSubmission.folder == folder).first()
        if submission:
            log.info('Updating OldSubmission {0}'.format(folder))
        else:
            log.info('Creating OldSubmission {0}'.format(folder))
            submission = updater.create_accept(OldSubmission)
            submission.folder = folder
            DBSession.add(submission)

            with closing(StringIO()) as temp:
                with zipfile.ZipFile(temp, 'w') as zipf:
                    for sub in subs:
                        path = sub.Location
                        with downloader.dl(path) as dfile:
                            if file is None and not downloader.dryrun:
                                if sub.Location in _known_bad_old_submissions:
                                    log.info(
                                        u'Skipping known bad Old Submission: '
                                        '{0}'.format(path))
                                    continue
                                else:
                                    raise ValueError(
                                        u'Unable to find file for old '
                                        'submission: {0}'.format(path))
                            lstat = downloader.lstat(path)
                            zipi = zipfile.ZipInfo(dfile.name)
                            dtime = datetime.fromtimestamp(lstat.st_mtime)
                            zipi.date_time = (
                                dtime.year, dtime.month, dtime.day, dtime.hour,
                                dtime.minute, dtime.second)
                            zipi.compress_type = zipfile.ZIP_DEFLATED
                            zipf.writestr(zipi, dfile.read())
                with su(su_lock=downloader.su_lock):
                    submission.file = FSFile(temp, '{0}.zip'.format(folder))
                    DBSession.flush()
        sub = subs[0]
        submission.ts_c = _date_to_datetime(sub.Date)
        submission.ts_j = sub.updated_at
        submission.line = sub.Line
        submission.submitter = sub.Name


def _import_spatial_groups(session):
    log.info("Importing Spatial groups")
    updater = _get_updater()
    sgs = session.query(legacy.SpatialGroup).all()
    for sg in sgs:
        collection = import_Collection(updater, sg.area, 'group')
        basins = collection.basins
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
        basins = uniquify(basins)
        updater.attr(collection, 'basins', basins)

        if not sg.expocode:
            log.info("Skipping non Cruise for spatial_groups")
            continue

        cruise = Cruise.query().filter(Cruise.expocode == sg.expocode).first()
        if not cruise:
            cruise = updater.create_accept(Cruise)
            updater.attr(cruise, 'expocode', sg.expocode)

        log.info("Updating Cruise %s for spatial_groups" % sg.expocode)
        collections = uniquify(cruise.collections + [collection])
        if cruise.collections != collections:
            updater.attr(cruise, 'collections', collections)


def _import_internal(session):
    """The internal table maps a cruise to a basin."""
    log.info("Importing Internal")
    updater = _get_updater()
    internals = session.query(legacy.Internal).all()
    for i in internals:
        if not i.expocode:
            log.warn("Skipping internal {0}, no expocode".format(i.id))
            continue

        cruises = Cruise.query().filter(Cruise.expocode == i.expocode).all()
        if cruises:
            log.info("Updating Cruise %s for internal" % i.expocode)
            cruise = cruises[0]
        else:
            log.info("Creating Cruise %s for internal" % i.expocode)
            cruise = updater.create_accept(Cruise)
            updater.attr(cruise, 'expocode', i.expocode)

        # TODO it may be better to map the cruise to the collection and let
        # basin attribute on collection figure out the rest.
        collection = import_Collection(updater, i.Basin, 'basin')
        collections = cruise.get('collections', []) + [collection]
        collections = uniquify(collections)
        log.info(u'add collection {0} to cruise {1}'.format(
            collection.id, i.expocode))
        updater.attr(cruise, 'collections', collections)


def _import_unused_tracks(session):
    log.info("Importing unused tracks")
    updater = _get_updater()
    ts = session.query(legacy.UnusedTrack).all()
    for t in ts:
        if not t.expocode:
            log.info(
                u"Skipping unused track {0!r}, no expocode.".format(t.id))
            continue
        cruise = Cruise.query().filter(Cruise.expocode == t.expocode).first()
        if cruise:
            log.info("Updating Cruise %s for unused track" % t.expocode)
        else:
            log.info("Creating Cruise %s for unused track" % t.expocode)
            cruise = updater.create_accept(Cruise)
            updater.attr(cruise, 'expocode', t.expocode)

        collection = import_Collection(updater, t.Basin, 'basin')
        collections = cruise.get('collections', []) + [collection]
        collections = uniquify(collections)
        updater.attr(cruise, 'collections', collections)


def _import_unit(updater, unit):
    import_id = str(unit.id)
    u = Unit.query().filter(Unit.import_id == import_id).first()
    if not u:
        u = updater.create_accept(Unit)
    u.import_id = import_id
    updater.attr(u, 'name', unit.name)
    updater.attr(u, 'mnemonic', unit.mnemonic)
    return u


def _import_parameter_descriptions(session):
    log.info("Importing parameter descriptions")
    updater = _get_updater()
    std_session = std.session()
    try:
        parameters = std_session.query(std.Parameter).all()
        for parameter in parameters:
            p = Parameter.query().filter(Parameter.name == parameter.name).first()
            if p:
                log.info("Updating Parameter %s" % parameter.name)
            else:
                log.info("Creating Parameter %s" % parameter.name)
                p = updater.create_accept(Parameter)
            updater.attr(p, 'name', parameter.name)
            updater.attr(p, 'full_name', parameter.full_name)
            updater.attr(p, 'name_netcdf', parameter.name_netcdf)
            updater.attr(p, 'description', parameter.description or '')
            updater.attr(p, 'format', parameter.format)
            if parameter.units:
                updater.attr(
                    p, 'units', _import_unit(updater, parameter.units))
            updater.attr(
                p, 'bounds', (parameter.bound_lower, parameter.bound_upper))
            aliases = [a.name for a in parameter.aliases]
            updater.attr(p, 'aliases', aliases)
    except OperationalError, e:
        log.error("unable to convert parameters: %s" % traceback.print_exc(e))
    finally:
        std_session.rollback()
        std_session.close()


def _import_parameter_groups(session):
    log.info("Importing Parameter Groups")
    std_session = std.session()
    updater = _get_updater()
    groups = session.query(legacy.ParameterGroup).all()
    std_session.close()
    for group in groups:
        g = ParameterGroup.query().filter(ParameterGroup.name == group.group).first()
        if not g:
            g = updater.create_accept(ParameterGroup)
            updater.attr(g, 'name', group.group)
            order = group.ordered_parameters
            porder = []
            for p in order:
                parameter = Parameter.query().filter(Parameter.name == p).first()
                if not parameter:
                    log.warn('Could not find parameter {0} for order {1}. '
                        'Created parameter.'.format(p, group.id))
                    parameter = updater.create_accept(Parameter)
                    updater.attr(parameter, 'name', p)
                    updater.attr(
                        parameter, 'in_groups_but_did_not_exist', True)
                porder.append(parameter)
            updater.attr(g, 'order', porder)


def _import_bottle_dbs(session):
    log.info("Importing Bottle DBs")
    # TODO regenerate bottle parameter information cache
    log.info("Omitting import in favor of regenerating this information")


def _import_parameter_status(session):
    log.info("Importing parameter statuses")
    log.info("Omitting import because information is never used in site "
                 "and probably is replaced by documents.preliminary")


def _import_parameters(session):
    log.info("Importing parameters (chiscis responsible)")
    updater = _get_updater()

    codes = {}
    for code in session.query(legacy.Codes).all():
        codes[int(code.Code)] = codes_name_to_param_info_code[code.Status]
    codes[0] = None

    parameters = {}
    for param in legacy.CruiseParameterInfo._PARAMETERS:
        parameter = Parameter.query().filter(Parameter.name == param).first()
        if parameter:
            log.info("Found Parameter %s for CPI" % param)
        else:
            log.info("Created Parameter %s for CPI" % param)
            parameter = Parameter.create(updater.importer).obj
        updater.attr(parameter, 'name', param)
        parameter.import_id = 'cruise_param_info'
        parameters[param] = parameter

    for p in session.query(legacy.CruiseParameterInfo).all():
        cruise = Cruise.query().filter(Cruise.expocode == p.ExpoCode).first()
        if cruise:
            log.info("Found Cruise %s for CPI" % p.ExpoCode)
        else:
            log.info("Creating Cruise %s for CPI" % p.ExpoCode)
            cruise = Cruise.create(updater.importer).obj
        updater.attr(cruise, 'expocode', p.ExpoCode)
        cruise.import_id = 'cruise_param_info'

        param_infos = []
        for param in legacy.CruiseParameterInfo._PARAMETERS:
            parameter = parameters[param]

            status = getattr(p, param)
            try:
                status = codes[int(status)]
            except (TypeError, ValueError):
                if status != None:
                    log.warn(
                        u"Bad Status %r while importing 'parameters' row "
                        "%d parameter %s" % (status, p.id, param))
                status = None
            except KeyError:
                log.warn(
                    u"Unrecognized status %r while importing 'parameters' "
                    "row %d parameter %s" % (status, p.id, param))
                status = None

            try:
                pi = getattr(p, param + '_PI')
                if pi and pi != 'None':
                    pis = _cchdo_pi_to_person_insts(
                        _ustr2uni(pi), cruise, updater)
                else:
                    pis = []
            except TypeError, e:
                log.warn(e)
                pis = []
            
            try:
                ts = _date_to_datetime(getattr(p, param + '_Date'))
            except TypeError:
                ts = None

            for pi in pis:
                param_infos.append(
                    ParameterInformation(parameter, status, pi[0], pi[1], ts))
            if not pis:
                param_infos.append(
                    ParameterInformation(parameter, status, None, None, ts))

        param_infos = filter(lambda x: not x.is_empty(), param_infos)
        updater.attr(cruise, 'parameter_informations', param_infos)


argo_action_str = \
    'Non-public data for Argo calibration (proprietary, rapid-delivery)'


def submission_public_to_type(p, argo_action):
    """Convert CCHDO submission public and action to submission type."""
    # 2011-09-16 myshen
    # cberys has determined "assigned" corroborates
    # non-public status and is generally redundant. More importantly it
    # is not used anywhere in the application.
    if p is None:
        # Assume that no response means public data as long the submission
        # is not for Argo
        if argo_action:
            return 'argo'
        return 'public'

    p = p.lower()
    if p == 'public':
        return 'public'
    elif p == 'argo':
        return 'argo'
    else:
        return 'non-public'


_KNOWN_MISSING_SUBMISSIONS = [
    '/Library/WebServer/Documents/cchdo/public/submissions/20071026_12_17_Huang__Pien/1 - I8S Argo Video (Quicktime)',
    '/Library/WebServer/Documents/cchdo/public/submissions/20071129_04_25_Shibata_Fuyuki/',
    '/Library/Webserver/Documents/cchdo/public/submissions/20080222_09_21_oz/',

    '/Library/Webserver/Documents/cchdo/public/submissions/20080417_01_07_j_kappa/',
    '/Library/Webserver/Documents/cchdo/public/submissions/20090119_05_22_widodo/',
    ]


def _import_submission(session, downloader, updater, imported_submissions, dsug,
                       sub):
    import_id = str(sub.id)
    if import_id in imported_submissions:
        log.info("Updating Submission %s" % import_id)
        return
    else:
        log.info("Creating Submission %s" % import_id)
        submission = Submission.create(updater.importer).obj
        submission.import_id = import_id

        submission.ts_c = _date_to_datetime(sub.submission_date)

        # Information about submitter
        name = sub.name
        inst = sub.institute
        email = sub.email
        country = sub.country

        submitter, inst = _import_person_inst(updater, name, '', inst, email)
        submission.p_c = submitter

        if country:
            country = _import_country(updater, country)
            updater.attr(submitter, 'country', country)

        request = BaseRequest.blank('')
        request.date = submission.ts_c
        request.remote_addr = sub.ip
        request.user_agent = sub.user_agent

        submission.request_for = RequestFor(request)

        expocode = sub.expocode
        ship_name = sub.ship_name
        line = sub.line
        action = sub.action
        argo_action = False
        notes = sub.notes
        file_path = sub.file

        if expocode:
            submission.expocode = _ustr2uni(expocode)
        if ship_name:
            submission.ship_name = _ustr2uni(ship_name)
        if line:
            submission.line = _ustr2uni(line)
        if action:
            # Remove Argo import string from list of actions and set the
            # argo bit
            if 'Argo' in action:
                argo_action = True
                if argo_action_str in action:
                    removed = action.replace(argo_action_str, '')
                    action = ','.join(filter(None, removed.split(',')))
            submission.action = _ustr2uni(action)
        if notes:
            submission.notes.append(
                Note(submitter, _ustr2uni(notes)))

        if file_path in _KNOWN_MISSING_SUBMISSIONS:
            log.info(u'Skipped known missing submission: %s', file_path)
            return

        with downloader.dl(file_path) as file:
            if not file:
                submission.delete()
                log.warn(
                    u'unable to get file for Submission %s', import_id)
                return

            file_name = os.path.basename(file_path)
            fs = FieldStorage()
            fs.filename = file_name
            fs.file = file

            # unzip multiple_files*.zips that are actually just one file
            if (    file_name.startswith('multiple_files') and
                    file_name.endswith('.zip')):
                # ZipFile.open will clobber the file object so make a copy
                with closing(StringIO()) as temp:
                    copy_chunked(file, temp)
                    with zipfile.ZipFile(temp) as zf:
                        infos = zf.infolist()
                        if len(infos) == 1:
                            tempzipf = NamedTemporaryFile()
                            zippedf = zf.open(infos[0])
                            copy_chunked(zippedf, tempzipf)
                            fs.filename = infos[0].filename
                            fs.file = tempzipf
                            fs.type = guess_mime_type(fs.filename)
                            with su(su_lock=downloader.su_lock):
                                submission.file = FSFile.from_fieldstorage(fs)
                            tempzipf.close()
                        elif len(infos) == 0:
                            log.error(u'Empty submission.')
                        else:
                            # multiple file submission. just leave it as is
                            # for now...
                            # TODO split it out into multiple submissions?
                            fs.type = guess_mime_type(fs.filename)
                            with su(su_lock=downloader.su_lock):
                                submission.file = FSFile.from_fieldstorage(fs)
                            
            else:
                fs.type = guess_mime_type(fs.filename)
                with su(su_lock=downloader.su_lock):
                    submission.file = FSFile.from_fieldstorage(fs)

        submission.type = submission_public_to_type(
            sub.public, argo_action)

        # "assimilated" is used to color code the submission table according
        # to whether submission has been put in the queue.
        # This means, ideally, every assimilated submission has a queue file
        # entry. Find the imported queue file and attach that one.
        assimilated = bool(sub.assimilated)
        if assimilated:
            if sub.queue_file:
                import_id = str(sub.queue_file.id)
                queue_file = FSFile.attr_by_import_id(import_id)
            else:
                queue_file = None
            if not queue_file:
                log.warn(u'Unable to find queue file {0} for assimilated '
                    'suggestion {1}'.format(import_id, sub.id))
                queue_file = dsug
            log.debug(repr(queue_file))
            submission.attached = queue_file

        try:
            submission.cruise_date = _date_to_datetime(sub.cruise_date)
        except TypeError:
            log.warn(u'Unable to convert submission {0} date {1!r}'.format(
                sub.id, sub.cruise_date))


def _import_submissions(session, downloader):
    log.info("Importing Submissions")

    updater = _get_updater()

    submissions = Submission.query().all()
    imported_submissions = set([s.import_id for s in submissions])

    # Assimilated cruise
    # For assimilated submissions that are assimilated and have a queue file,
    # the original submission is kind of irrelevant.
    # There are no assimilated files without a queue file, so that case does not
    # need to be handled. If it were though, assigning it to the cruise as a
    # pending data_suggestion should be fine.

    # We need to create a cruise that does not appear for "assimilated"
    # submissions to be attached to it. This allows them to be marked
    # assimilated.
    cruise = get_by_import_id(Cruise, 'submissions_assimilated')
    if not cruise:
        cruise = Cruise.create(updater.importer).obj
        cruise.import_id = 'submissions_assimilated'
        fs_assimilated = FieldStorage()
        fs_assimilated.filename = 'assimilated'
        fs_assimilated.file = SpooledTemporaryFile(max_size=1)
        with su(su_lock=downloader.su_lock):
            dsug = cruise.set(updater.importer, 'data_suggestion',
                FSFile.from_fieldstorage(fs_assimilated))
        del fs_assimilated.file
    else:
        dsug = cruise.get_attr_change('data_suggestion')

    for sub in session.query(legacy.Submission).all():
        _import_submission(
            session, downloader, updater, imported_submissions, dsug, sub)


def _import_queue_files(session, downloader):
    log.info("Importing queue files")
    updater = _get_updater()

    re_docs = re.compile('Cruise (report|information)', re.IGNORECASE)

    queue_files = session.query(legacy.QueueFile).all()
    for qfile in queue_files:
        cruises = Cruise.query().filter(Cruise.expocode == qfile.expocode).all()
        if cruises:
            cruise = cruises[0]
        else:
            log.warn(
                u"Missing cruise for queue file %s. Skip" % qfile.expocode)
            continue

        contact_name = qfile.contact
        if not contact_name:
            submitter = updater.importer
        else:
            submitter, inst = _import_person_inst(
                updater, contact_name, '', '', '')

        import_id = str(qfile.id)
        unprocessed_input = qfile.unprocessed_input.strip()
        queue_file = FSFile.attr_by_import_id(import_id)

        if qfile.date_received:
            date_received = _date_to_datetime(qfile.date_received)
        else:
            date_received = None

        if not queue_file or not queue_file.attr_value.value:
            log.info('Creating Queue File %s' % import_id)

            with downloader.dl(unprocessed_input) as file:
                if file is None:
                    log.warn(
                        "Missing queue file %s" % unprocessed_input)
                    log.info("Skipping queue record import")
                    continue
                else:
                    actual_file = FieldStorage()
                    actual_file.filename = qfile.Name
                    actual_file.type = guess_mime_type(qfile.Name)
                    actual_file.file = file

                # A file in the "queue" is a file that has been attached to a
                # cruise and no more. We can't really guess the data type
                # correctly 100% with the given information so attach it as a
                # data_suggestion.
                with su(su_lock=downloader.su_lock):
                    actual_file = FSFile.from_fieldstorage(actual_file)
                    queue_file = cruise.set(updater.importer,
                        'data_suggestion', actual_file)
                # Set the import id on the FSFile
                queue_file.value.import_id = import_id

            queue_file.p_c = submitter
            if not date_received:
                date_received = downloader.mtime(unprocessed_input)
            queue_file.ts_c = date_received
        else:
            log.info('Updating Queue File %s' % import_id)

        if qfile.cchdo_contact:
            contact = import_person(updater, None, qfile.cchdo_contact)
        else:
            contact = updater.importer

        log.info(u'acknowledged by CCHDO contact {0}'.format(contact))
        queue_file.acknowledge(contact)
        queue_file.ts_ack = date_received

        # merged status codes
        # 0 - unmerged, shown online
        # 1 - merged, shown online
        # 2 - unmerged, hidden from public
        if qfile.merged == 1:
            date_merged = qfile.date_merged
            log.info(u'accepted by CCHDO contact {0}'.format(contact))
            queue_file.accept(contact)
            if not date_merged:
                log.warn(
                    'No date merged for merged file. Obtaining from file '
                    'timestamp')
                date_merged = downloader.mtime(unprocessed_input)
            else:
                date_merged = _date_to_datetime(date_merged)
            queue_file.ts_j = date_merged
        if qfile.merged == 2 or qfile.hidden:
            # file is hidden
            log.info(u'rejected by CCHDO contact {0}'.format(contact))
            queue_file.reject(contact)

        # processed_input is obsolete according to cberys
        # hidden flag is obsolete according to cberys

        if qfile.notes:
            queue_file.notes.append(
                Note(submitter, _ustr2uni(qfile.notes)))

        if qfile.action:
            queue_file.notes.append(
                Note(submitter, _ustr2uni(qfile.action),
                     data_type='action', discussion=True))

        if qfile.parameters or qfile.documentation:
            parameters = qfile.parameters
            if not parameters:
                parameters = ''
            if qfile.documentation:
                if not re_docs.match(parameters):
                    parameters = u','.join([parameters, 'Documentation'])
            queue_file.notes.append(
                Note(updater.importer, parameters, data_type='Parameters',
                     discussion=True))

        if qfile.merge_notes:
            queue_file.notes.append(
                Note(updater.importer, _ustr2uni(qfile.merge_notes),
                     discussion=True))


_DOCS_TYPE_IGNORE = [
    'Coord info', 'Coordinates?', 'Data History HTML', 'Directory Description',
    'GMT info File', 'Index HTML File', 'Old Index HTML File', 'Person HTML',
    'Type HTML', 'Unrecognized', 
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
    'CTD File': 'ctd_woce',
    'Documentation': 'doc_txt',
    'PDF Documentation': 'doc_pdf',
    'Encrypted file': 'encrypted',
    'Exchange Bottle': 'bottle_exchange',
    # All bottle exchange zips are actually bottle exchange that are zipped for
    # HOT OR missing & mislabeled files for SAVE.
    'Exchange Bottle (Zipped)': 'ignore',
    'Exchange CTD': 'ctd_exchange',
    'Exchange CTD (Zipped)': 'ctd_zip_exchange',
    'JGOFS File': 'jgofs',
    'Small Plot': 'map_thumb',
    'Large Plot': 'map_full',
    'Large Volume file': 'large_volume_samples_exchange',
    'Trace Metals file': 'trace_metals_exchange',
    'Matlab file': 'matlab',
    'NetCDF Bottle': 'bottle_zip_netcdf',
    'NetCDF CTD': 'ctd_zip_netcdf',
    'SEA file': 'sea',
    'Sum File': 'sum_woce',
    'WCT CTD File': 'ctd_wct',
    'Woce Bottle': 'bottle_woce',
    'Woce CTD (Zipped)': 'ctd_zip_woce',
    'Woce Sum': 'sum_woce',
}


def parse_dt(s):
    try:
        return text_to_obj(s, DateTime)
    except TypeError:
        # Probably got fed a datetime
        return s
    except ValueError:
        return s


_ignorable_document_types = ['ExpoCode', '.passwd', '.password', 'error_File', ]


def _import_documents_unaccounted(
        downloader, updater, cruise, remote_dir, accounted_files,
        tempdir='/tmp/pycchdoimp'):
    # Import unaccounted files as an archive
    archive_import_id = cruise.import_id
    log.info(u'Packaging unaccounted files for cruise {0}'.format(archive_import_id))
    archive_attr = cruise.get_attr_change('archive')
    if archive_attr:
        log.info('%s archive already imported' % archive_import_id)
        return

    # Use a shorter temp root so long path names don't get too long. Mac OS X
    # limits to 1024 bytes.
    log.debug(u'generating tempdir')
    with su(su_lock=downloader.su_lock):
        try:
            os.makedirs(tempdir)
        except OSError:
            pass
        local_dir = tempfile.mkdtemp(dir=tempdir)
    log.info(u'collecting unaccounted files from {0} to tempdir {1}'.format(
        remote_dir, local_dir))

    try:
        try:
            dirlist = downloader.listdir(remote_dir)
        except (OSError, IOError), e:
            log.error(
                u'Could not list remote dir {0} to find unaccounted files:\n'
                '{1!r}'.format(remote_dir, e))
            return
        any_unaccounted = False
        for entry in dirlist:
            if entry in _DOCS_FILES_IGNORE:
                continue
            if entry in accounted_files:
                continue
            if any(regexp.match(entry) for regexp in _DOCS_RE_IGNORE):
                continue

            any_unaccounted = True

            log.info('not accounted: %s' % entry)

            remote_path = os.path.join(remote_dir, entry)
            local_path = os.path.join(local_dir, entry)

            r_lstat = downloader.lstat(remote_path)
            try:
                if stat.S_ISDIR(r_lstat.st_mode):
                    downloader.dl_dir(remote_path, local_path)
                else:
                    with downloader.dl(remote_path) as file:
                        with open(local_path, 'wb') as ostream:
                            copy_chunked(file, ostream) 
            except (OSError, IOError), e:
                log.error(
                    u'Unable to download unaccounted file/dir {0}\n{1!r}'.format(
                    remote_path, e))

        if any_unaccounted:
            archive_name = 'archive_{0}.tar'.format(cruise.id)
            log.info(u'packaging {0} to {1}...'.format(local_dir, archive_name))
            unaccounted_archive = SpooledTemporaryFile(max_size=2**20)
            ua_tar = tarfile.open(mode='w', fileobj=unaccounted_archive)
            try:
                with su(su_lock=downloader.su_lock), pushd(local_dir):
                    ua_tar.add('.')
            finally:
                ua_tar.close()
            unaccounted_archive.seek(0)

            fs_archive = FieldStorage()
            fs_archive.filename = archive_name
            fs_archive.file = unaccounted_archive
            fs_archive.type = 'application/x-tar'

            with su(su_lock=downloader.su_lock):
                fsf = FSFile.from_fieldstorage(fs_archive)
                archive_attr = updater.attr(cruise, 'archive', fsf)
                fsf.import_id = archive_import_id
                archive_attr.permissions_read = ['staff', ]
            unaccounted_archive.close()
    finally:
        log.debug(u'removing tempdir {0}'.format(local_dir))
        with su(su_lock=downloader.su_lock):
            shutil.rmtree(local_dir)


def _import_documents_for_cruise(downloader, docs, expocode):
    cruises = Cruise.query().filter(Cruise.expocode == expocode).all()
    updater = _get_updater()
    if docs:
        log.info("Importing documents for %s" % expocode)
    else:
        log.info("No docs to import for %s" % expocode)
        return
    if cruises:
        cruise = cruises[0]
        log.info('associating documents to {0}'.format(cruise))
    else:
        log.error('no cruise {0} to associate documents'.format(expocode))
        return

    # Map the list of legacy Documents to keys that pycchdo recognizes
    mapped_docs = {}
    for doc in docs:
        if doc.FileType in _DOCS_TYPE_IGNORE:
            log.debug(
                u'Ignoring doc of type %s: %s' % (doc.FileType, doc.FileName))
            continue

        try:
            pycchdo_type = _DOCS_TYPE_TO_PYCCHDO_TYPE[doc.FileType]
        except KeyError:
            basename = os.path.basename(doc.FileName)
            if (    doc.FileType == 'Unrecognized' and 
                    basename in _ignorable_document_types):
                pycchdo_type = 'ignore'
            else:
                log.warn(
                    u'Unmapped doc type %s: %s' % (doc.FileType, doc.FileName))
                continue
        if pycchdo_type == 'bottle_exchange':
            if doc.FileName.endswith('lv_hy1.csv'):
                pycchdo_type = 'large_volume_samples_exchange'
            if doc.FileName.endswith('tm_hy1.csv'):
                pycchdo_type = 'trace_metals_exchange'

        try:
            mapped_doc = mapped_docs[pycchdo_type]
            if doc.LastModified > mapped_doc.LastModified:
                log.warning('%s already exists: old %s new %s' % (
                    pycchdo_type, mapped_doc.FileName, doc.FileName))
                mapped_docs[pycchdo_type] = doc
        except (KeyError, TypeError):
            mapped_docs[pycchdo_type] = doc
            log.debug('Mapped %s %s' % (pycchdo_type, doc.FileName))

    # Add the cruise's directory entry as import record
    try:
        remote_dir = mapped_docs['directory'].FileName
        del mapped_docs['directory']
        updater.attr(cruise, 'data_dir', remote_dir)
    except KeyError:
        log.error(
            '%s has no directory registered. Cannot import.' % expocode)
        return

    # Import all files that have been mapped to the cruise
    accounted_files = copy(_DOCS_FILES_IGNORE)
    log.debug(mapped_docs)
    log.debug(mapped_docs.items())
    for data_type, doc in mapped_docs.items():
        log.debug('handling mapped doc {0} {1}'.format(data_type, doc))
        if data_type == 'ignore':
            continue

        doc_import_id = str(doc.id)
        log.debug(u'checking import status of {0}'.format(doc_import_id))
        attr = FSFile.attr_by_import_id(doc_import_id)
        if attr:
            log.info('%s already imported' % doc_import_id)
            continue
        else:
            log.info('%s already imported' % doc_import_id)

        preliminary = bool(doc.Preliminary)
        if preliminary:
            log.info(
                'Marking file %s for %s preliminary' % (data_type, expocode))
            # Nothing else makes changes to <key>_status es so it is safe to
            # assume the only <key>_status is the one we want to change.
            status_key = '%s_status' % data_type
            statuses = uniquify(cruise.get(status_key, []) + ['preliminary'])
            updater.attr(cruise, status_key, statuses)

        # Check that the file to download is the same size as recorded in db.
        size = int(doc.Size)
        try:
            lstat = downloader.lstat(doc.FileName)
            if lstat.st_size != size:
                log.warn(
                    'File %s has mismatched size. Expected %s got %s' % (
                        doc.FileName, size, lstat.st_size))
        except (OSError, IOError), e:
            log.error((
                'Unable to check file size {0}. Skip file download.:\n'
                '{1!r}').format(doc.FileName, e))
            continue

        # We don't care about these stamps. Regenerate later.
        stamps = doc.Stamp

        field = FieldStorage()
        field.filename = os.path.basename(doc.FileName)
        field.type = guess_mime_type(doc.FileName)

        with downloader.dl(doc.FileName) as file:
            if not file:
                log.error('Unable to download %s. Skipping' % doc.FileName)
                continue

            field.file = file
            with su(su_lock=downloader.su_lock):
                fsf = FSFile.from_fieldstorage(field)
                fsf.import_path = doc.FileName
                fsf.import_id = doc_import_id
                attr = updater.attr(cruise, data_type, fsf)

        date_creation = doc.Modified
        date_accepted = doc.LastModified

        # It's possible for date_creation to be a comma separated list.
        # I'm assuming it's lists of modification times - myshen
        if date_creation:
            log.debug('setting creation date')
            creations = date_creation.split(',')
            if len(creations) > 1:
                date_creations = map(str, sorted(map(parse_dt, creations)))
                date_creation = date_creations[0]
                updater.note(
                    attr, ','.join(date_creations), 'dates_updated',
                    creation_timestamp=date_creations[-1])
            else:
                attr.ts_c = date_creation
        if date_accepted:
            log.debug('setting accept date')
            attr.ts_c = parse_dt(date_accepted)
            attr.ts_j = parse_dt(date_accepted)

        accounted_files.append(field.filename)
        log.debug('accounted')

    log.debug('accounted files: {0}'.format(accounted_files))

    _import_documents_unaccounted(
        downloader, updater, cruise, remote_dir, accounted_files)

    log.debug('imported docs for %s' % cruise.get('expocode', ''))


class DocumentsImporter(Thread):
    def __init__(self, *args):
        Thread.__init__(self)
        self.daemon = True
        self.args = args
        self.downloader = args[0]

    def run(self):
        try:
            _import_documents_for_cruise(*self.args)
        except Exception, e:
            # Close out the transaction for this thread. This is done here in
            # case of fast return from import method.
            log.error(
                u'Unable to import documents\n{0!r}\n{1}'.format(
                    e, format_exc()))
            DBSession.rollback()
        finally:
            log.debug('committing')
            transaction.commit()
            log.debug('committed')


def _import_documents(session, downloader, nthreads):
    log.info("Importing documents")

    # Instead of importing the documents table, go the other way around and
    # import documents for each cruise
    # TODO FIXME what about the files with no ExpoCode? or ExpoCode == 'NULL'?
    # package those up?
    expocodes = [ccc.expocode for ccc in DBSession.query(Cruise.expocode).all()]

    log.info(u'Found {0} expocodes. initializing threads...'.format(
        len(expocodes)))

    docs_by_expocode = {}
    docs = session.query(legacy.Document).\
        order_by(legacy.Document.LastModified.desc()).all()
    for doc in docs:
        if doc.ExpoCode:
            try:
                docs_by_expocode[doc.ExpoCode].append(doc)
            except KeyError:
                docs_by_expocode[doc.ExpoCode] = [doc]

    if nthreads > 1:
        log.info('running with threads')
        previous_su_lock = downloader.su_lock
        try:
            downloader.su_lock = Lock()
            importers = []
            for expocode in expocodes:
                try:
                    docs = docs_by_expocode[expocode]
                except KeyError:
                    continue
                importers.append(
                    DocumentsImporter(downloader, docs, expocode))
            _run_importers(importers, nthreads=nthreads, remote_downloads=False)
        finally:
            downloader.su_lock = previous_su_lock
    else:
        log.info('running without threads')
        batchsize = 4
        plog = ProgressLog(expocodes, 4)
        for i, expocode in enumerate(expocodes):
            log.info(expocode)
            try:
                docs = docs_by_expocode[expocode]
            except KeyError:
                continue
            log.info(repr(docs))
            _import_documents_for_cruise(downloader, docs, expocode)
            if i % batchsize == 0:
                transaction.commit()
                transaction.begin()
            plog.log()


class FakeWebObRequest(object):
    def __init__(self, date=None, remote_addr=None):
        self.date = date
        self.remote_addr = remote_addr


libcchdo_to_pycchdo_file_type = {
    'sumhot': 'summary_hot',
    'sumwoce': 'summary_woce',
    'botwoce': 'bottle_woce',
    'lvbotex': 'large_volume_samples_exchange',
    'tmbotex': 'trace_metals_exchange',
    'botex': 'bottle_exchange',
    'botnc': 'bottle_netcdf',
    'botzipnc': 'bottle_zip_netcdf',
    'ctdex': 'ctd_exchange',
    'ctdwoce': 'ctd_woce',
    'ctdzipex': 'ctd_zip_exchange',
    'ctdzipwoce': 'ctd_zip_woce',
    'ctdnc': 'ctd_netcdf',
    'ctdzipnc': 'ctd_zip_netcdf',
    'coriolis': 'coriolis',
    'polarstern': 'ctd_polarstern',
    'nodc_sd2': 'nodc_sd2',
    'geosecs': 'geosecs',
    'sbe9': 'ctd_sbe9',
    'tracks': 'tracks',
}


def _import_argo_missingtxt(session, downloader, argo_file, file, filename, remote_path):
    try:
        lstat = downloader.lstat(remote_path)
    except (OSError, IOError), e:
        log.error('unable to get argo file stat {0} {1!r}'.format(
            remote_path, e))
        return
    fs_argo = FieldStorage()
    fs_argo.filename = filename
    fs_argo.type = guess_mime_type(filename)
    if stat.S_ISLNK(lstat.st_mode):
        # Attempt to find the cruise and corresponding file type to link
        symlink_target = downloader.readlink(remote_path)
        log.debug(u'ArgoFile {0} is link to {1}'.format(
            file.id, symlink_target))

        # Get the ExpoCode from the symlink target's directory
        expopath = os.path.join(
            os.path.dirname(symlink_target), 'ExpoCode')
        expocode = None
        with downloader.dl(expopath) as expo:
            if expo:
                expocode = expo.read().strip()
            else:
                log.warn(
                    u'Unable to get ExpoCode for linked ArgoFile {0}.'.format(file.id))

        if expocode:
            cruise = Cruise.query().filter(Cruise.expocode == expocode).first()
            if cruise:
                file_type = libcchdo.fns.guess_file_type(symlink_target)
                if file_type:
                    log.debug(
                        u'Guessed file type to be {}'.format(file_type))
                    try:
                        file_type = libcchdo_to_pycchdo_file_type[file_type]
                    except KeyError:
                        pass
                    log.info(
                        u'linking to {0} {1}'.format(cruise, file_type))
                    argo_file.link(cruise, file_type)
                    return
                else:
                    log.debug(
                        u'Finding file in imported documents to link')
                    fsfile = FSFile.query().filter(
                        FSFile.import_path == symlink_target).first()
                    if fsfile:
                        attr = fsfile.attr_value.attr
                        if attr:
                            argo_file.link(cruise, attr.key)
                            return
        log.warn(
            u'Unable to find cruise {0} to link ArgoFile {1} to. '
            'Attaching actual file instead.'.format(expocode, file.id))

    # File is not a link or was unable to find cruise so just download
    # and attach the file
    with downloader.dl(remote_path) as f:
        if f:
            fs_argo.file = f
            with su(su_lock=downloader.su_lock):
                argo_file.file = FSFile.from_fieldstorage(fs_argo)
        else:
            log.error(
                u'Unable to attach argo file by download: could not '
                'download {0}'.format(remote_path))


def _import_argo_files(session, downloader):
    log.info("Importing Argo files")
    updater = _get_updater()
    argo_files = session.query(legacy.ArgoFile).all()

    for file in argo_files:
        filename = file.filename

        argo_file = ArgoFile.query().\
            filter(ArgoFile.text_identifier == file.expocode).\
            filter(Change.ts_c == file.created_at).first()
        if not argo_file:
            log.info(
                u'Creating Argo File ({0}, {1}, {2})'.format(
                    file.id, filename, file.created_at))
            user = get_by_import_id(Person, str(file.user.id))
            if not user:
                user = updater.importer
            argo_file = ArgoFile.create(user).obj
            argo_file.change.ts_c = file.created_at
        else:
            log.info(u'Updating Argo File ({0}, {1}, {2}) = {3}'.format(
                file.id, filename, file.created_at, argo_file.id))
        argo_file.text_identifier = file.expocode
        argo_file.description = file.description
        argo_file.display = file.display

        remote_path = os.path.join('/data/argo/files', filename)
        log.debug(remote_path)

        # Special case for missing.txt because there is no actual file. Just
        # ignore it and add the description but no file.
        if filename != 'missing.txt':
            _import_argo_missingtxt(
                session, downloader, argo_file, file, filename, remote_path)

        if file.downloads:
            requests = []
            for dl in file.downloads:
                req = FakeWebObRequest(date=dl.created_at, remote_addr=dl.ip)
                reqfor = RequestFor(req)
                requests.append(reqfor)
            argo_file.requests_for = requests


def _get_updater():
    log.info("Get/Create CCHDO Importer to take blame")
    return Updater(import_person(None, 'importer', 'CCHDO', 'CCHDO_importer'))


def import_(import_gid, nthreads, fsstore, args):
    log.info("Connecting to cchdo db")
    nthreads = 2
    try:
        with db_session(legacy.session()) as session:
            if not args.files_only:
                _import_users(session)
                _import_contacts(session)
                _import_collections(session)

                transaction.commit()
                transaction.begin()

                _import_cruises(session, nthreads - 1)

                transaction.commit()
                transaction.begin()

                _import_track_lines(session)
                _import_collections_cruises(session)
                _import_collection_basins(session)

                transaction.commit()
                transaction.begin()

                _import_contacts_cruises(session)

                transaction.commit()
                transaction.begin()

                _import_events(session)

                transaction.commit()
                transaction.begin()

                _import_spatial_groups(session)
                _import_internal(session)
                _import_unused_tracks(session)

                _import_parameter_descriptions(session)

                transaction.commit()
                transaction.begin()

                _import_parameter_groups(session)
                _import_bottle_dbs(session)
                _import_parameter_status(session)
                _import_parameters(session)

                transaction.commit()
                transaction.begin()
            with conn_dl(remote_host, args.skip_downloads, import_gid,
                         local_rewriter=rewrite_dl_path_to_local, su_lock=Lock()
                        ) as downloader, store_context(fsstore):
                _import_queue_files(session, downloader)
                _import_submissions(session, downloader)
                _import_old_submissions(session, downloader)
                _import_documents(session, downloader, nthreads - 1)
                _import_argo_files(session, downloader)
            transaction.commit()
    except (KeyboardInterrupt, Exception):
        log.info('aborted transaction')
        transaction.abort()
        raise
