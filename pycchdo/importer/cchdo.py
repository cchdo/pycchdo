# -*- coding: utf8 -*-
import datetime
from cgi import FieldStorage
import stat
import tempfile
import os
import re
import mimetypes
import tarfile
import shutil
from copy import copy
from threading import current_thread
from StringIO import StringIO as pyStringIO
try:
    from cStringIO import StringIO
except ImportError:
    StringIO = pyStringIO
from threading import Thread, Lock
import time
import zipfile
from tempfile import NamedTemporaryFile

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
from pycchdo.models import (
    DBSession,
    Note,
    FSFile,
    Cruise, Person, Institution, Country, Participant, ArgoFile, Collection,
    Submission, OldSubmission, Unit, Ship, Parameter, ParameterOrder, 
    RequestFor,
    ParameterInformation, 
    _Attr,
    )
from pycchdo.importer import * 
from pycchdo.views import text_to_obj


__all__ = ['import_Collection', 'import_person']


remote_host = 'ghdc.ucsd.edu'

        
def rewrite_dl_path_to_local(path):
    """Rewrite paths to reference the correct local path."""
    leader_data = '/data/'
    leader_submissions0 = (
        '/Library/Webserver/Documents/cchdo/public/submissions/')
    leader_submissions1 = (
        '/Library/WebServer/Documents/cchdo/public/submissions/')
    leader_submissions2 = (
        '/Library/WebServer/Documents/cchdo/submissions/')
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
    elif path.startswith(leader_old_submissions):
        # OldSubmissions
        return '/var/cchdo-data/submissions/old_sys/' + \
            path[len(leader_old_submissions):]
    return path


def import_Collection(updater, name, type):
    """A Collection also will include a type as part of its identifier to
    differentiate between the fields it came from in the original database.

    """
    collection = Collection.get_one_by_attrs({'names': name, 'type': type})
    if collection:
        implog.info(u'Updating Collection {!r} {!r}'.format(name, type))
    else:
        implog.info(u'Creating Collection {!r} {!r}'.format(name, type))
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


known_aliases = {
    'sdiggs,,': '',
}


def _find_person_with_qlastn_name_first(qlastn, name_first):
    people = qlastn.filter(Person.name_first == name_first).all()
    if len(people) == 1:
        return people[0]
    elif len(people) > 1:
        implog.error(
            u'Multiple people for {0!r} {1!r}'.format(qlastn, name_first))
    else:
        implog.error(
            u'No person for {0!r} {1!r}'.format(
                qlastn, name_first))
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
    return _import_contact(updater, name, '')


def _name_to_inst(updater, name, p):
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
    implog.info(u'Mapping {} {} to person-institution'.format(pi, cruise))

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
    inst = Institution.get_one_by_attrs({'name': name})
    if inst:
        implog.info(u"Updating Institution {}".format(name))
    else:
        implog.info(u"Creating Institution {}".format(name))
        inst = updater.create_accept(Institution)
    updater.attr(inst, 'name', _ustr2uni(name))
    return inst


def _import_contact(updater, name_last, name_first, institution=None,
                    email=None):
    inst_id = None
    if institution is not None:
        inst_id = institution.id
    return import_person(updater, name_last, name_first, None,
                         institution=inst_id, email=email)


def _import_person_inst(updater,
                        name_last, name_first, institution_name, email):
    institution = _import_inst(updater, institution_name)
    person = _import_contact(
        updater, name_last, name_first, institution, email)
    return (person, institution)


def _import_users(session):
    implog.info("Importing users")
    users = session.query(legacy.User).all()
    updater = _get_updater()
    for user in users:
        person = Person.query().filter(
            Person.identifier == user.username).first()
        if not person:
            implog.info('Creating User %s' % user.username)
            person = import_person(
                updater, None, user.username, user.username)
        else:
            implog.info('Updating User %s' % user.username)
        updater.attr(person, 'password_hash', user.password_hash)
        updater.attr(person, 'password_salt', user.password_salt)
        updater.attr(person, 'import_id', str(user.id))


def _import_contacts(session):
    implog.info("Importing Contacts")
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
        updater.attr(person, 'import_id', str(contact.id))
    DBSession.flush()


def _import_ship(updater, ship_name):
    ship = Ship.get_one_by_attrs({'name': ship_name})
    if ship:
        implog.info('Updating Ship %s' % ship_name)
    else:
        implog.info('Creating Ship %s' % ship_name)
        ship = updater.create_accept(Ship)
        updater.attr(ship, 'name', ship_name)
    return ship


def _import_country(updater, country_name):
    country = Country.query().filter(
        Country.iso_3166_1 == country_name).first()
    if country:
        implog.info('Updating Country %s' % country_name)
    else:
        implog.info('Creating Country %s' % country_name)
        country = updater.create_accept(Country)
        country.iso_3166_1 = country_name
    return country


def _import_cruise(cruise):
    updater = _get_updater()
    import_id = str(cruise.id)
    c = Cruise.get_one_by_attrs({'import_id': import_id})
    if c:
        implog.info('Updating Cruise %s %s' % (import_id, cruise.ExpoCode))
    else:
        implog.info('Creating Cruise %s %s' % (import_id, cruise.ExpoCode))
        c = updater.create_accept(Cruise)

    updater.attr(c, 'import_id', import_id)
    updater.attr(c, 'expocode', cruise.ExpoCode)

    if cruise.Begin_Date:
        updater.attr(
            c, 'date_start', _date_to_datetime(cruise.Begin_Date))
    if cruise.EndDate:
        updater.attr(c, 'date_end', _date_to_datetime(cruise.EndDate))
    if cruise.link:
        updater.attr(c, 'link', cruise.link)

    if cruise.Country:
        country = _import_country(updater, cruise.Country)
        updater.attr(c, 'country', country.id)

    if cruise.Ship_Name:
        ship = _import_ship(updater, cruise.Ship_Name)
        updater.attr(c, 'ship', ship.id)

    if cruise.Alias:
        # Hope that Alias fields are all comma separated...
        aliases = uniquify([x.strip() for x in cruise.Alias.split(',')])
        updater.attr(c, 'aliases', aliases)

    collections = []
    if cruise.Line:
        collections.append(import_Collection(updater, cruise.Line, 'WOCE line').id)
    if cruise.Group:
        groups = [x.strip() for x in cruise.Group.split(',')]
        for group in groups:
           collections.append(import_Collection(updater, group, 'group').id)
    if cruise.Program:
        programs = [x.strip() for x in cruise.Program.split(',')]
        for program in programs:
            collections.append(import_Collection(updater, program, 'program').id)

    collections = uniquify(collections)
    updater.attr(c, 'collections', collections)
    
    if cruise.Chief_Scientist:
        person_insts = _cchdo_pi_to_person_insts(
            _ustr2uni(cruise.Chief_Scientist), cruise, updater)

        participants = []
        for pi in person_insts:
            participants.append(Participant('Chief Scientist', *pi))
        participants = uniquify(participants)
        c.participants.replace(
            c, updater.importer, *participants).accept(updater.importer)
        if c.participants:
            implog.debug(
                'Participants for cruise %s: %s' % (cruise.id, c.participants))

    implog.debug('imported cruise %s' % cruise.id)


class CruisesImporter(Thread):
    def __init__(self, cruise):
        Thread.__init__(self)
        self.daemon = True
        self.cruise = cruise

    def run(self):
        _import_cruise(self.cruise)

        # Close out the transaction for this thread. This is done here in case
        # of fast return from import method.
        transaction.commit()
        DBSession.remove()


def _import_cruises(session):
    implog.info("Importing Cruises")

    cruises = session.query(legacy.Cruise).all()
    len_cruises = float(len(cruises))

    importers = []
    for cruise in cruises:
        importers.append(CruisesImporter(cruise))

    _run_importers(importers)


def _log_progress(i, total):
    implog.info(u'{0!r} / {1!r} = {2!r}'.format(i, total, i / total))
    

def _run_importers(importers, nthreads=6, remote_downloads=False, sleep=0.5):
    num_importers = float(len(importers))
    implog.info(    
        "Running %d importers with %d threads" % (num_importers, nthreads))
    i = 0

    if nthreads > 1:
        if remote_downloads:
            implog.info("opening %d sftp connections" % nthreads)
            sftp_pool = []
            for i in range(nthreads):
                try:
                    ssh = ssh_connect(remote_host)
                    sftp = ssh.open_sftp()
                except SSHException, e:
                    implog.error(repr(e))
                sftp_pool.append((ssh, sftp))

        active_importers = []
        while importers:
            # Clean up importers that have finished
            for imp in active_importers:
                if not imp.is_alive():
                    implog.info('importer finished %s' % imp.name)
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
                implog.info('importer started %s' % imp.name)
            time.sleep(sleep)

        # Wait for remaining importers to finish
        for imp in active_importers:
            if imp.is_alive():
                imp.join()
        _log_progress(i, num_importers)

        implog.debug(u'closing sftp connections')
        if remote_downloads:
            for ssh, sftp in sftp_pool:
                sftp.close()
                ssh.close()
    else:
        # Run them one by one
        for imp in importers:
            imp.run()
            i += 1
            _log_progress(i, num_importers)


def _import_track_lines(session):
    implog.info(u'Importing track lines')
    tls = session.query(legacy.TrackLine).all()
    updater = _get_updater()
    for tl in tls:
        try:
            wkt = session.scalar(tl.Track.wkt)
        except OperationalError:
            implog.error("Unable to get track from CCHDO db for %s" % tl.id)
            continue
        try:
            linestring = shapely.wkt.loads(wkt)
        except ReadingError:
            # There are some linestrings in the DB that are single point lines. Yes.
            # Turn them into a very short lines.
            point = tuple(shapely.wkt.loads(wkt.replace('LINESTRING', 'POINT')).coords)[0]
            pt_list = [point, point]
            linestring = LineString(pt_list)

        cruise = Cruise.get_one_by_attrs({'expocode': tl.ExpoCode})
        if not cruise:
            implog.warn('Unable to import track_line %s because the cruise '
                        '%s does not exist' % (tl.id, tl.ExpoCode))
            continue

        if linestring:
            updater.attr(cruise, 'track', linestring)


def import_person(updater, name_last, name_first,
                  identifier=None, institution=None, email=None):
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
        dbquery = dbquery.filter(
            Person.email == query['email'])

    people = dbquery.all()

    person = None
    if people:
        person = people[0]
        if institution:
            for p in people:
                if p.get('institution') == institution:
                    person = p
                    break
    if person:
        implog.debug(u"Updating person %s" % query)
    else:
        implog.info(u"Creating person %s" % query)

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

        person = Person(**query)
        DBSession.add(person)
        DBSession.flush()
        if updater is None:
            person.accept(person)
        else:
            person.accept(updater.importer)

        if institution:
            updater.attr(person, 'institution', institution)
        DBSession.flush()
    return person


def _collections_merge(signer):
    """Merge all collections that are the same together."""
    cls = Collection

    # Pass 1: same name and same type
    implog.info('Collection merge pass 1: same name, same type')
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
        implog.debug(u'Merging {} with {}'.format(same[0], same[1:]))
        same[0].merge(signer, *same[1:])

    # Pass 2: same name and similar types
    implog.info('Collection merge pass 2: same name, similar type')
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
    implog.info("Importing Collections")
    collections = session.query(legacy.Collection).all()
    updater = _get_updater()
    for collection in collections:
        import_id = str(collection.id)
        coll = Collection.get_one_by_attrs({'import_id': import_id})
        if coll:
            implog.info("Updating Collection %s %s" % (
                import_id, collection.Name))
        else:
            implog.info("Creating Collection %s %s" % (
                import_id, collection.Name))
            coll = updater.create_accept(Collection)
        updater.attr(coll, 'names', [collection.Name])
        updater.attr(coll, 'import_id', import_id)

    implog.info('Merging same collections')
    _collections_merge(updater.importer)


def _import_collections_cruises(session):
    implog.info("Importing CollectionsCruises")
    updater = _get_updater()
    collections_cruises = session.query(legacy.CollectionsCruise).all()
    for cc in collections_cruises:
        if cc.collection is None or cc.cruise is None:
            implog.warn(
                'CollectionCruises pair (cruise %d, collection %d) is bad' % (
                    cc.cruise_id, cc.collection_id))
            continue

        cruise = Cruise.get_one_by_attrs({'import_id': str(cc.cruise.id)})
        if not cruise:
            implog.warn('Bad cruise %d' % cc.cruise.id)
            continue

        collection = Collection.get_one_by_attrs(
            {'import_id': str(cc.collection.id)})
        if not collection:
            implog.warn('Bad collections %d' % cc.collection.id)
            continue

        present = True
        cruise_collections = cruise.get('collections')
        if collection.id in cruise_collections:
            implog.info('Collection already present in Cruise collections')
        else:
            implog.info('Adding Collection %s to Cruise %s collections' % \
                        (collection.id, cruise.id))
            updater.attr(
                cruise, 'collections', cruise_collections + [collection.id])


def _import_contacts_cruises(session):
    implog.info("Importing ContactsCruises")
    updater = _get_updater()
    contacts_cruises = session.query(legacy.ContactsCruise).all()
    for cc in contacts_cruises:
        if not cc.cruise:
            implog.info("Bad Cruise ID %s" % (cc.cruise_id))
            continue
        if not cc.contact:
            implog.info("Bad Contact ID %s" % (cc.contact_id))
            continue

        import_id = str(cc.cruise_id)
        cruise = Cruise.get_one_by_attrs({'import_id': import_id})
        if not cruise:
            implog.warn("Could not import ContactsCruise pair because cruise "
                        '%s does not exist.' % import_id)
            continue

        import_id = str(cc.contact.id)
        person = Person.get_one_by_attrs({'import_id': import_id})
        if not person:
            implog.warn("Could not import ContactsCruise pair because person "
                        '%s does not exist.' % import_id)
            continue

        role = cc.function
        if not role:
            role = 'Chief Scientist'
        try:
            if person in [pi.person for pi in cruise.participants[role]]:
                implog.info(
                    "Updating participant %s %s to %s" % (person, role, cruise))
                continue
        except KeyError:
            pass
        implog.info(
            "Adding participant %s to cruise %s as %s" % (
                person, cruise.id, role))
        cruise.participants.extend(
            cruise, updater.importer, Participant(role, person))


def _import_events(session):
    implog.info("Importing Events")

    updater = _get_updater()

    events = session.query(legacy.Event).all()
    len_events = len(events)
    for i, event in enumerate(events):
        if i % 100 == 0:
            implog.info('{:d}/{:d} = {:f}'.format(
                i, len_events, float(i) / len_events))
        event_id = str(event.ID)
        note = Note.query().filter(Note.import_id == event_id).first()
        if note:
            implog.info("Updating Event %s" % event_id)
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

            person = import_person(updater, event.LastName, event.First_Name)

            note = Note(person, body, action, data_type, summary)
            note.creation_timestamp = _date_to_datetime(event.Date_Entered)
            note.import_id = event_id
            DBSession.add(note)
            DBSession.flush()

            cruises = Cruise.get_by_expocode(event.ExpoCode)
            for cruise in cruises:
                implog.info("Creating Event %s for cruise %s" % (
                    event_id, cruise.get('import_id')))
                cruise.notes.append(note)


_known_bad_old_submissions = [
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
]


def _import_old_submissions(session, downloader):
    implog.info("Importing Old Submissions")
    updater = _get_updater()
    subs = session.query(legacy.OldSubmission).all()

    # Group submissions by folder
    map_submissions = {}
    for sub in subs:
        try:
            submission = map_submissions[sub.Folder]
        except KeyError:
            submission = OldSubmission.query().filter(
                OldSubmission.folder == sub.Folder).first()
            if submission:
                implog.info('Updating OldSubmission %s' % sub.Folder)
            else:
                implog.info('Creating OldSubmission %s' % sub.Folder)
                submission = updater.create_accept(OldSubmission)
                submission.creation_timestamp = sub.created_at
                submission.judgment_timestamp = sub.updated_at
                submission.folder = sub.Folder
                submission.date = _date_to_datetime(sub.Date)
                submission.stamp = sub.Stamp
                submission.line = sub.Line
                submission.submitter = sub.Name
                submission.files = []
                DBSession.flush()
            map_submissions[sub.Folder] = submission

        with downloader.dl(sub.Location) as file:
            if file is None and downloader.dl_files:
                if sub.Location in _known_bad_old_submissions:
                    implog.info(
                        u'Skipping known bad Old Submission: {0}'.format(
                            sub.Location))
                    continue
                else:
                    raise ValueError(
                        u'Unable to find file for old submission: {}'.format(
                            sub.Location))
            if (    file and
                    not any(f.name == sub.Filename for f in submission.files)):
                submission.files.append(FSFile(file, sub.Filename))
            DBSession.add(submission)
            DBSession.flush()


def _import_spatial_groups(session):
    implog.info("Importing Spatial groups")
    updater = _get_updater()
    sgs = session.query(legacy.SpatialGroup).all()
    for sg in sgs:
        collection = import_Collection(updater, sg.area, 'group')
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
        updater.attr(collection, 'basins', basins)

        if not sg.expocode:
            implog.info("Skipping non Cruise for spatial_groups")
            continue

        cruise = Cruise.get_one_by_attrs({'expocode': sg.expocode})
        if cruise:
            implog.info("Updating Cruise %s for spatial_groups" % sg.expocode)
            collections = uniquify(cruise.collections + [collection])
            if cruise.collections != collections:
                ids = [c.id for c in collections]
                updater.attr(cruise, 'collections', ids)


def _import_internal(session):
    """The internal table maps a cruise to a basin."""
    implog.info("Importing Internal")
    updater = _get_updater()
    internals = session.query(legacy.Internal).all()
    for i in internals:
        if not i.expocode:
            implog.info("Skipping internal, no expocode")
            continue
        cruise = Cruise.get_one_by_attrs({'expocode': i.expocode})
        if cruise:
            implog.info("Updating Cruise %s for internal" % i.expocode)
        else:
            implog.info("Creating Cruise %s for internal" % i.expocode)
            cruise = updater.create_accept(Cruise)
        updater.attr(cruise, 'expocode', i.expocode)
        #updater.attr(
        #    cruise, 'import_id', '_'.join(
        #        [cruise.get('import_id', ''), 'internal']))

        # TODO it may be better to map the cruise to the collection and let
        # basin attribute on collection figure out the rest.
        collection = import_Collection(updater, i.Basin, 'basin')
        collections = cruise.get('collections', []) + [collection.id]
        collections = uniquify(collections)
        updater.attr(cruise, 'collections', collections)


def _import_unused_tracks(session):
    implog.info("Importing unused tracks")
    updater = _get_updater()
    ts = session.query(legacy.UnusedTrack).all()
    for t in ts:
        if not t.expocode:
            implog.info(
                u"Skipping unused track {0!r}, no expocode.".format(t.id))
            continue
        cruise = Cruise.get_one_by_attrs({'expocode': t.expocode})
        if cruise:
            implog.info("Updating Cruise %s for unused track" % t.expocode)
        else:
            implog.info("Creating Cruise %s for unused track" % t.expocode)
            cruise = updater.create_accept(Cruise)
        updater.attr(cruise, 'expocode', t.expocode)
        #updater.attr(cruise, 'import_id', '_'.join(
        #    cruise.get('import_id', ''), 'unused_track']))

        collection = import_Collection(updater, t.Basin, 'basin')
        collections = cruise.get('collections', []) + [collection.id]
        collections = uniquify(collections)
        updater.attr(cruise, 'collections', collections)


def _import_unit(updater, unit):
    import_id = str(unit.id)
    u = Unit.get_one_by_attrs({'import_id': import_id})
    if not u:
        u = updater.create_accept(Unit)
        DBSession.add(u)
        DBSession.flush()
        updater.attr(u, 'import_id', import_id)
    updater.attr(u, 'name', unit.name)
    updater.attr(u, 'mnemonic', unit.mnemonic)
    return u


def _import_parameter_descriptions(session):
    implog.info("Importing parameter descriptions")
    updater = _get_updater()
    std_session = std.session()
    try:
        parameters = lcconvert.all_parameters(session, std_session)
        for parameter in parameters:
            p = Parameter.get_one_by_attrs({'name': parameter.name})
            if p:
                implog.info("Updating Parameter %s" % parameter.name)
            else:
                implog.info("Creating Parameter %s" % parameter.name)
                p = updater.create_accept(Parameter)
            updater.attr(p, 'name', parameter.name)
            updater.attr(p, 'full_name', parameter.full_name)
            updater.attr(p, 'name_netcdf', parameter.name_netcdf)
            updater.attr(p, 'description', parameter.description)
            updater.attr(p, 'format', parameter.format)
            if parameter.units:
                updater.attr(
                    p, 'unit', _import_unit(updater, parameter.units).id)
            updater.attr(
                p, 'bounds', (parameter.bound_lower, parameter.bound_upper))
            aliases = [a.name for a in parameter.aliases]
            updater.attr(p, 'aliases', aliases)
    except OperationalError, e:
        implog.error("unable to convert parameters: %s" % e)
        parameters = []
    finally:
        std_session.rollback()
        std_session.close()


def _import_parameter_groups(session):
    std_session = std.session()
    updater = _get_updater()
    groups = session.query(legacy.ParameterGroup).all()
    std_session.close()
    for group in groups:
        g = ParameterOrder.get_one_by_attrs({'name': group.group})
        if not g:
            g = ParameterOrder(updater.importer)
            g.accept(updater.importer)
            DBSession.add(g)
            DBSession.flush()
            updater.attr(g, 'name', group.group)
            order = group.ordered_parameters
            porder = []
            for p in order:
                parameter = Parameter.get_one_by_attrs({'name': p})
                if not parameter:
                    implog.warn("Could not find parameter %s for order" % p)
                    parameter = updater.create_accept(Parameter)
                    updater.attr(parameter, 'name', p)
                    updater.attr(
                        parameter, 'in_groups_but_did_not_exist', True)
                porder.append(parameter.id)
            updater.attr(g, 'order', porder)


def _import_bottle_dbs(session):
    implog.info("Importing Bottle DBs")
    # TODO regenerate bottle parameter information cache
    implog.info("Omitting import in favor of regenerating this information")


def _import_parameter_status(session):
    implog.info("Importing parameter statuses")
    implog.info("Omitting import because information is never used in site "
                 "and probably is replaced by documents.preliminary")


def _import_parameters(session):
    implog.info("Importing parameters (chiscis responsible)")
    updater = _get_updater()

    codes = {}
    for code in session.query(legacy.Codes).all():
        codes[int(code.Code)] = codes_name_to_param_info_code[code.Status]
    codes[0] = None

    parameters = {}
    for param in legacy.CruiseParameterInfo._PARAMETERS:
        parameter = Parameter.get_one_by_attrs({'name': param})
        if parameter:
            implog.info("Found Parameter %s for CPI" % param)
        else:
            implog.info("Created Parameter %s for CPI" % param)
            parameter = Parameter(updater.importer)
            parameter.accept(updater.importer)
            DBSession.add(parameter)
            DBSession.flush()
        updater.attr(parameter, 'name', param)
        updater.attr(parameter, 'import_id', 'cruise_param_info')
        parameters[param] = parameter
    DBSession.flush()

    for p in session.query(legacy.CruiseParameterInfo).all():
        cruise = Cruise.get_one_by_attrs({'expocode': p.ExpoCode})
        if cruise:
            implog.info("Found Cruise %s for CPI" % p.ExpoCode)
        else:
            implog.info("Creating Cruise %s for CPI" % p.ExpoCode)
            cruise = Cruise(updater.importer)
            cruise.accept(updater.importer)
            DBSession.add(cruise)
            DBSession.flush()
        updater.attr(cruise, 'expocode', p.ExpoCode)
        updater.attr(cruise, 'import_id', 'cruise_param_info')
        DBSession.flush()

        param_infos = []
        for param in legacy.CruiseParameterInfo._PARAMETERS:
            parameter = parameters[param]

            status = getattr(p, param)
            try:
                status = codes[int(status)]
            except (TypeError, ValueError):
                if status != None:
                    implog.warn(
                        u"Bad Status %r while importing 'parameters' row "
                        "%d parameter %s" % (status, p.id, param))
                status = None
            except KeyError:
                implog.warn(
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
                implog.warn(e)
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
        DBSession.flush()


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


def _import_submissions(session, downloader):
    implog.info("Importing Submissions")

    updater = _get_updater()

    submissions = Submission.query().all()
    imported_submissions = set([s.get('import_id') for s in submissions])

    # Assimilated cruise
    # We need to create a cruise that does not appear for "assimilated"
    # submissions to be attached to it. This allows them to be marked
    # assimilated.
    cruise = Cruise.get_one_by_attrs({'import_id': 'submissions_assimilated'})
    if not cruise:
        cruise = Cruise(updater.importer)
        DBSession.add(cruise)
        DBSession.flush()
        cruise.set_accept(
            'import_id', 'submissions_assimilated', updater.importer)
        fs_assimilated = FieldStorage()
        fs_assimilated.filename = 'assimilated'
        fs_assimilated.file = pyStringIO('')
        fs_assimilated.file.name = fs_assimilated.filename
        attr = cruise.set_accept(
            'data_suggestion', fs_assimilated, updater.importer)
    else:
        attr = cruise.get_attr('data_suggestion')

    for sub in session.query(legacy.Submission).all():
        import_id = str(sub.id)
        if import_id in imported_submissions:
            implog.info("Updating Submission %s" % import_id)
            continue
        else:
            implog.info("Creating Submission %s" % import_id)
            submission = Submission(updater.importer)

            submission.creation_timestamp = \
                _date_to_datetime(sub.submission_date)

            # Information about submitter
            name = sub.name
            inst = sub.institute
            email = sub.email
            country = sub.country

            submitter, inst = _import_person_inst(
                updater, name, '', inst, email)

            submission.creation_person_id = submitter.id

            country = _import_country(updater, country)
            updater.attr(submitter, 'country', country.id)

            request = BaseRequest.blank('')
            request.date = submission.creation_timestamp
            request.remote_addr = sub.ip
            request.user_agent = sub.user_agent

            submission.request_for = RequestFor(request)
            DBSession.add(submission)
            DBSession.flush()

            expocode = sub.expocode
            ship_name = sub.ship_name
            line = sub.line
            action = sub.action
            argo_action = False
            notes = sub.notes
            file_path = sub.file

            if expocode:
                submission.expocode_ = _ustr2uni(expocode)
            if ship_name:
                submission.ship_name_ = _ustr2uni(ship_name)
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
                implog.info(
                    u'Skipped known missing submission: %s', file_path)
                continue

            with downloader.dl(file_path) as file:
                if not file:
                    DBSession.delete(submission)
                    implog.warn(
                        u'unable to get file for Submission %s', import_id)
                    continue

                file_name = os.path.basename(file_path)
                actual_file = FieldStorage()
                actual_file.filename = file_name
                actual_file.file = file

                # ZipFile.open will clobber the file object so make a copy.
                temp = StringIO()
                copy_chunked(file, temp)
                file.seek(0)

                # unzip multiple_files*.zips that are actually just one file
                if (    file_name.startswith('multiple_files') and
                        file_name.endswith('.zip')):
                    with zipfile.ZipFile(temp) as zf:
                        infos = zf.infolist()
                        if len(infos) == 1:
                            tempzipf = NamedTemporaryFile()
                            zippedf = zf.open(infos[0])
                            copy_chunked(zippedf, tempzipf)
                            actual_file.filename = infos[0].filename
                            actual_file.file = tempzipf
                submission.file = FSFile.from_fieldstorage(actual_file)
                DBSession.flush()

            submission.type = submission_public_to_type(
                sub.public, argo_action)

            # "assimilated" is used to color code the submission table according
            # to whether submission has been put in the queue.
            assimilated = bool(sub.assimilated)
            if assimilated:
                submission.attached = attr

            DBSession.flush()
            try:
                submission.cruise_date = _date_to_datetime(sub.cruise_date)
            except TypeError:
                pass

            updater.attr(submission, 'import_id', import_id)


def _import_queue_files(session, downloader):
    implog.info("Importing queue files")
    updater = _get_updater()

    re_docs = re.compile('Cruise (report|information)', re.IGNORECASE)

    queue_files = session.query(legacy.QueueFile).all()
    for qfile in queue_files:
        cruise = Cruise.get_one_by_attrs({'expocode': qfile.expocode})
        if not cruise:
            implog.warn(
                u"Missing cruise for queue file %s. Skip" % qfile.expocode)
            continue

        unprocessed_input = qfile.unprocessed_input.strip()

        import_id = str(qfile.id)
        qf_file = FSFile.query().filter(
            FSFile.import_id == import_id).first()
        if not qf_file:
            implog.info('Creating Queue File %s' % import_id)

            with downloader.dl(unprocessed_input) as file:
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

                # A file in the "queue" is a file that has been attached to a
                # cruise and no more. We can't really guess the data type
                # correctly 100% with the given information so attach it as a
                # data_suggestion.
                queue_file = updater.attr(
                    cruise, 'data_suggestion', actual_file)
                # Set the import id on the FSFile
                queue_file.attr_value.value.import_id = import_id
                DBSession.flush()

            name = qfile.contact
            if not name:
                submitter = updater.importer
            else:
                submitter, inst = _import_person_inst(
                    updater, name, '', '', '')

            queue_file.creation_person_id = submitter.id
            date_received = None
            if qfile.date_received:
                date_received = _date_to_datetime(qfile.date_received)
            else:
                date_received = downloader.mtime(unprocessed_input)
            queue_file.creation_timestamp = date_received
            DBSession.flush()
        else:
            implog.info('Updating Queue File %s' % import_id)
            queue_file = qf_file.attr_value.attr

        if qfile.cchdo_contact:
            contact = Person.query().\
                filter(Person.identifier == qfile.cchdo_contact).first()
            if contact:
                queue_file.acknowledge(contact)
            else:
                implog.warn(
                    "CCHDO contact %s is not recognized" % qfile.cchdo_contact)

        # merged status codes
        # 0 - unmerged, shown online
        # 1 - merged, shown online
        # 2 - unmerged, hidden from public

        if qfile.merged == 1:
            date_merged = qfile.date_merged
            queue_file.accept(updater.importer)
            if not date_merged:
                implog.warn('No date merged for merged file. Obtaining from '
                            'file timestamp')
                date_merged = downloader.mtime(unprocessed_input)
            else:
                date_merged = _date_to_datetime(date_merged)
            queue_file.judgment_timestamp = date_merged
            DBSession.flush()

        if qfile.merged == 2 or qfile.hidden:
            # file is hidden
            queue_file.reject(updater.importer)

        # processed_input is obsolete according to cberys
        # hidden flag is obsolete according to cberys

        if qfile.notes:
            queue_file.notes.append(
                Note(updater.importer, _ustr2uni(qfile.notes)))

        if qfile.action:
            queue_file.notes.append(
                Note(updater.importer, _ustr2uni(qfile.action),
                    data_type='Action', discussion=True))

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
            queue_file.notes.append(Note(updater.importer,
                                            _ustr2uni(qfile.merge_notes),
                                            discussion=True))


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
    'Sum File': 'sum_woce',
    'WCT CTD File': 'ctd_wct',
    'Woce Bottle': 'bottle_woce',
    'Woce CTD (Zipped)': 'ctdzip_woce',
    'Woce Sum': 'sum_woce',
}


def parse_dt(s):
    try:
        return text_to_obj(s, 'datetime')
    except TypeError:
        # Probably got fed a datetime
        return s
    except ValueError:
        return s


_ignorable_document_types = ['ExpoCode', '.passwd', '.password', 'error_File', ]


def _import_documents_for_cruise(downloader, docs, expocode, cruise_id):
    with lock(downloader.flush_lock):
        updater = _get_updater()
        cruise = Cruise.query().get(cruise_id)
        if not cruise:
            implog.error('Could not find cruise {0}'.format(cruise_id))
            return
    if docs:
        implog.info("Importing documents for %s" % expocode)
    else:
        implog.info("No docs to import for %s" % expocode)
        return

    # Map the list of legacy Documents to keys that pycchdo recognizes
    mapped_docs = {}
    for doc in docs:
        if doc.FileType in _DOCS_TYPE_IGNORE:
            implog.debug(
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
                implog.warn(
                    u'Unmapped doc type %s: %s' % (doc.FileType, doc.FileName))
                continue
        if pycchdo_type == 'bottle_exchange':
            if doc.FileName.endswith('lv_hy1.csv'):
                pycchdo_type = 'large_volume_samples_exchange'

        try:
            mapped_doc = mapped_docs[pycchdo_type]
            if doc.LastModified > mapped_doc.LastModified:
                implog.warning('%s already exists: old %s new %s' % (
                    pycchdo_type, mapped_doc.FileName, doc.FileName))
                mapped_docs[pycchdo_type] = doc
        except (KeyError, TypeError):
            mapped_docs[pycchdo_type] = doc
            implog.debug('Mapped %s %s' % (pycchdo_type, doc.FileName))

    # Add the cruise's directory entry as import record
    try:
        dir = mapped_docs['directory'].FileName
        del mapped_docs['directory']
        with lock(downloader.flush_lock):
            updater.attr(cruise, 'data_dir', dir)
    except KeyError:
        implog.error(
            '%s has no directory registered. Cannot import.' % expocode)
        return

    # Import all files that have been mapped to the cruise
    accounted_files = []
    for data_type, doc in mapped_docs.items():
        if data_type == 'ignore':
            continue

        doc_import_id = str(doc.id)
        with lock(downloader.flush_lock):
            attr = cruise.attr_by_file_import_id(data_type, doc_import_id)
        if attr:
            implog.info('%s already imported' % doc_import_id)
            continue

        preliminary = bool(doc.Preliminary)
        if preliminary:
            implog.info(
                'Marking file %s for %s preliminary' % (data_type, expocode))
            # Nothing else makes changes to <key>_status es so it is safe to
            # assume the only <key>_status is the one we want to change.
            status_key = '%s_status' % data_type
            statuses = uniquify(cruise.get(status_key, []) + ['preliminary'])
            with lock(downloader.flush_lock):
                updater.attr(cruise, status_key, statuses)

        # Check that the file to download is the same size as recorded in db.
        size = int(doc.Size)
        try:
            lstat = downloader.lstat(doc.FileName)
            if lstat.st_size != size:
                implog.warn(
                    'File %s has mismatched size. Expected %s got %s' % (
                        doc.FileName, size, lstat.st_size))
        except (OSError, IOError):
            implog.error('Missing file %s' % doc.FileName)
            continue

        # We don't care about these stamps. Regenerate later.
        stamps = doc.Stamp

        field = FieldStorage()
        field.filename = os.path.basename(doc.FileName)
        field.type = mimetypes.guess_type(doc.FileName)[0]

        with downloader.dl(doc.FileName) as file:
            if not file:
                implog.error('Unable to download %s. Skipping' % doc.FileName)
                continue

            field.file = file
            with lock(downloader.flush_lock):
                attr = updater.attr(cruise, data_type, field)
                attr.attr_value.import_path = doc.FileName
                attr.attr_value.import_id = doc_import_id
                DBSession.flush()

        date_creation = doc.Modified
        date_accepted = doc.LastModified

        # It's possible for date_creation to be a comma separated list.
        # I'm assuming it's lists of modification times - myshen
        if date_creation:
            creations = date_creation.split(',')
            if len(creations) > 1:
                date_creations = map(str, sorted(map(parse_dt, creations)))
                date_creation = date_creations[0]
                with lock(downloader.flush_lock):
                    updater.note(
                        attr, ','.join(date_creations), 'dates_updated')
            else:
                attr.creation_timestamp = date_creation
        if date_accepted:
            attr.judgment_timestamp = parse_dt(date_accepted)

        accounted_files.append(field.filename)
        with lock(downloader.flush_lock):
            DBSession.flush()
    accounted_files.extend(_DOCS_FILES_IGNORE)

    # Import unaccounted files as an archive
    archive_import_id = str(cruise.id)
    with lock(downloader.flush_lock):
        archive_attr = cruise.attrsq('archive').first()
    if archive_attr:
        implog.info('%s archive already imported' % archive_import_id)
        return

    # Use a shorter temp root so long path names don't get too long. Mac OS X
    # limits to 1024 bytes.
    with lock(downloader.su_lock):
        local_dir = tempfile.mkdtemp(dir='/tmp')
    implog.debug(
        'allocated local tempdir to collect unaccounted %s' % local_dir)

    remote_dir = os.path.dirname(doc.FileName)
    try:
        dirlist = downloader.listdir(remote_dir)
    except (OSError, IOError):
        implog.error(
            'Could not list remote dir %s to find unaccounted files' % 
            remote_dir)
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
        implog.info('Not accounted: %s' % entry)

        remote_path = os.path.join(remote_dir, entry)
        local_path = os.path.join(local_dir, entry)

        implog.debug(
            u'Downloading directory {0} to {1}'.format(remote_path, local_path))

        r_lstat = downloader.lstat(remote_path)
        if stat.S_ISDIR(r_lstat.st_mode):
            try:
                downloader.dl_dir(remote_path, local_path)
            except IOError, e:
                implog.error('Unable to download unaccounted dir %s' %
                             remote_path)
                implog.error(repr(e))
            except OSError, e:
                implog.error('Unable to download unaccounted dir %s' %
                             remote_path)
                implog.error(repr(e))
        else:
            try:
                with downloader.dl(remote_path) as file:
                    with open(local_path, 'wb') as ostream:
                        copy_chunked(file, ostream) 
                    file.seek(0)
            except OSError, e:
                implog.error('Unable to download unaccounted file %s' %
                             remote_path)
                implog.error(repr(e))
            except IOError, e:
                implog.error('Unable to download unaccounted file %s' %
                             remote_path)
                implog.error(repr(e))
        copy_stat(downloader, r_lstat, local_path)

    if any_unaccounted:
        unaccounted_archive = StringIO()
        ua_tar = tarfile.open(mode='w:bz2', fileobj=unaccounted_archive)
        with su(su_lock=downloader.su_lock):
            with pushd(local_dir):
                ua_tar.add('.')
            ua_tar.close()
            shutil.rmtree(local_dir)
        unaccounted_archive.seek(0)

        fs_archive = FieldStorage()
        fs_archive.filename = 'archive.tar.bz2'
        fs_archive.type = mimetypes.guess_type(fs_archive.filename)
        fs_archive.file = unaccounted_archive

        with lock(downloader.flush_lock):
            archive_attr = updater.attr(cruise, 'archive', fs_archive)
            archive_attr.attr_value.import_id = archive_import_id
            archive_attr.permissions_read = ['staff', ]

            DBSession.flush()
        unaccounted_archive.close()

    implog.debug('Imported docs for %s' % cruise.get('expocode', ''))


class DocumentsImporter(Thread):
    def __init__(self, *args):
        Thread.__init__(self)
        self.daemon = True
        self.args = args
        self.downloader = args[0]

    def run(self):
        _import_documents_for_cruise(*self.args)

        # Close out the transaction for this thread. This is done here in case
        # of fast return from import method.
        transaction.commit()
        DBSession.remove()


def _import_documents(session, downloader):
    implog.info("Importing documents")

    # Instead of importing the documents table, go the other way around and
    # import documents for each cruise
    # TODO FIXME what about the files with no ExpoCode? or ExpoCode == 'NULL'?
    # package those up?
    expocode_attrs = _Attr.query().filter(_Attr.key == 'expocode').\
        filter(_Attr.accepted == True).all()
    expocode_cruise_ids = [(a.value, a.obj_id) for a in expocode_attrs]

    implog.debug(u'Found {0} expocodes; Initializing threads'.format(
        len(expocode_cruise_ids)))

    docs_by_expocode = {}
    docs = session.query(legacy.Document).\
        order_by(legacy.Document.LastModified.desc()).all()
    for doc in docs:
        if doc.ExpoCode:
            try:
                docs_by_expocode[doc.ExpoCode].append(doc)
            except KeyError:
                docs_by_expocode[doc.ExpoCode] = [doc]

    DBSession.remove()

    previous_su_lock = downloader.su_lock
    previous_flush_lock = downloader.flush_lock
    downloader.su_lock = Lock()
    downloader.flush_lock = Lock()

    importers = []
    for expocode, cruise_id in expocode_cruise_ids:
        try:
            docs = docs_by_expocode[expocode]
        except KeyError:
            continue
        importers.append(
            DocumentsImporter(downloader, docs, expocode, cruise_id))
    _run_importers(importers, remote_downloads=False)

    downloader.flush_lock = previous_flush_lock
    downloader.su_lock = previous_su_lock


class FakeWebObRequest(object):
    def __init__(self, date=None, remote_addr=None):
        self.date = date
        self.remote_addr = remote_addr


def _import_argo_files(session, downloader):
    implog.info("Importing Argo files")
    updater = _get_updater()
    argo_files = session.query(legacy.ArgoFile).all()

    for file in argo_files:
        filename = file.filename

        argo_file = ArgoFile.query().\
            filter(ArgoFile.creation_timestamp == file.created_at).first()
        if not argo_file:
            implog.info(
                u'Creating Argo File ({0}, {1})'.format(
                    filename, file.created_at))
            user = Person.get_one_by_attrs({'import_id': str(file.user.id)})
            if not user:
                user = updater.importer
            argo_file = ArgoFile(user)
            argo_file.creation_timestamp = file.created_at
            argo_file.accept(user)
            DBSession.add(argo_file)
            DBSession.flush()
        else:
            implog.info(u'Updating Argo File (%s, %s)' % (
                filename, file.created_at))
        argo_file.text_identifier = file.expocode
        argo_file.description = file.description
        argo_file.display = file.display

        remote_path = os.path.join('/data/argo/files', filename)
        implog.debug(remote_path)

        # Special case for missing.txt because there is no actual file.
        if filename != 'missing.txt':
            lstat = downloader.lstat(remote_path)
            fs_argo = FieldStorage()
            fs_argo.filename = filename
            fs_argo.type = mimetypes.guess_type(filename)[0]
            if stat.S_ISLNK(lstat.st_mode):
                # Attempt to find the cruise and corresponding file type to link
                symlink_target = downloader.readlink(remote_path)
                implog.debug(u'ArgoFile {0} is link to {1}'.format(
                    file.id, symlink_target))

                # Get the ExpoCode from the symlink target's directory
                expopath = os.path.join(
                    os.path.dirname(symlink_target), 'ExpoCode')
                expocode = None
                with downloader.dl(expopath) as expo:
                    if expo:
                        expocode = expo.read().strip()
                    else:
                        implog.error(
                            u'Unable to get ExpoCode for linked ArgoFile {0}. '
                            'Skip.'.format(file.id))
                        continue

                cruise = Cruise.get_one_by_attrs({'expocode': expocode})
                if expocode and cruise:
                    file_type = libcchdo.fns.guess_file_type(symlink_target)
                    if file_type:
                        implog.debug(u'Guessed file type to be {}'.format(
                            file_type))
                        argo_file.link(cruise, file_type)
                        continue
                    else:
                        implog.debug(
                            u'Finding file in imported documents to link')
                        fsfile = FSFile.query().filter(
                            FSFile.import_path == symlink_target).first()
                        if fsfile:
                            attr = fsfile.attr_value.attr
                            if attr:
                                argo_file.link(cruise, attr.key)
                                continue
                implog.warn(
                    u'Unable to find cruise {0} to link ArgoFile {1} to. '
                    'Attaching actual file.'.format(expocode, file.id))

            # File is not a link or was unable to find cruise so just download
            # and attach the file
            with downloader.dl(remote_path) as f:
                if f:
                    fs_argo.file = f
                    argo_file.file = FSFile.from_fieldstorage(fs_argo)
                else:
                    implog.error(u'Unable to attach argo file by download')

                DBSession.flush()

        if file.downloads:
            requests = []
            for dl in file.downloads:
                requests.append(
                    RequestFor(FakeWebObRequest(
                                   date=dl.created_at, remote_addr=dl.ip)))
            argo_file.requests_for = requests
        DBSession.flush()


def _get_updater():
    implog.info("Get/Create CCHDO Importer to take blame")
    return Updater(import_person(None, 'importer', 'CCHDO', 'CCHDO_importer'))


def import_(import_gid, args):
    # libcchdo does not need to generate its local cache of parameter
    # information. That will be done during the import. Saves a bit of time.
    libcchdo.check_cache = False

    implog.info("Connecting to cchdo db")
    with db_session(legacy.session()) as session:
        if not args.files_only:
            _import_users(session)
            _import_contacts(session)
            _import_collections(session)

            _import_cruises(session)

            _import_track_lines(session)
            _import_collections_cruises(session)
            _import_contacts_cruises(session)

            _import_events(session)

            _import_spatial_groups(session)
            _import_internal(session)
            _import_unused_tracks(session)

            _import_parameter_descriptions(session)
            _import_parameter_groups(session)
            _import_bottle_dbs(session)
            _import_parameter_status(session)
            _import_parameters(session)

        with sftp(remote_host) as ssh_sftp:
            dl_files = not args.skip_downloads
            downloader = Downloader(
                dl_files, ssh_sftp, import_gid,
                local_rewriter=rewrite_dl_path_to_local, su_lock=Lock())
            _import_submissions(session, downloader)
            _import_old_submissions(session, downloader)
            _import_queue_files(session, downloader)
            _import_documents(session, downloader)
            _import_argo_files(session, downloader)
        transaction.commit()
