from cgi import FieldStorage
import os

import sqlalchemy as S
import sqlalchemy.orm
import sqlalchemy.ext.declarative

from geoalchemy import *

from shapely import wkb

from pycchdo.importers import *
from pycchdo.importers.cchdo import *
import pycchdo.models as models


Base = S.ext.declarative.declarative_base()
_metadata = Base.metadata


cred = ['seahunt_web', 'll0yd315']


rails_root = os.path.join(os.path.sep, 'srv', 'project_seahunt')


url = S.engine.url.URL('postgresql', cred[0], cred[1], 'goship.ucsd.edu',
                       database='seahunt')


engine = S.create_engine(url, use_native_unicode=False)


sessionmaker = S.orm.sessionmaker(bind=engine)


contacts_cruises = S.Table('contacts_cruises', _metadata,
    S.Column('contact_id', S.ForeignKey('contacts.id')),
    S.Column('cruise_id', S.ForeignKey('cruises.id')),
    S.Column('id', S.Integer, primary_key=True),
    S.Column('notes', S.Unicode),
    S.Column('relationship', S.Unicode),
)


contacts_programs = S.Table('contacts_programs', _metadata,
    S.Column('contact_id', S.ForeignKey('contacts.id')),
    S.Column('program_id', S.ForeignKey('programs.id')),
)


class Country(Base):
    __tablename__ = 'countries'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    abbreviation = S.Column(S.Unicode)
    country_code = S.Column(S.Unicode)

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Institution(Base):
    __tablename__ = 'institutions'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    full_name = S.Column(S.Unicode)
    phone = S.Column(S.Unicode)
    address = S.Column(S.Unicode)
    url = S.Column(S.Unicode)

    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        Country, backref=S.orm.backref('institutions', order_by=id,
                                       lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Contact(Base):
    __tablename__ = 'contacts'

    id = S.Column(S.Integer, primary_key=True)
    first_name = S.Column(S.Unicode)
    last_name = S.Column(S.Unicode)
    title = S.Column(S.Unicode)
    job_title = S.Column(S.Unicode)
    email = S.Column(S.Unicode)
    phone = S.Column(S.Unicode)
    fax = S.Column(S.Unicode)
    address = S.Column(S.Unicode)
    notes = S.Column(S.Unicode)

    institution_id = S.Column(S.ForeignKey('institutions.id'))
    institution = S.orm.relation(
        Institution, backref=S.orm.backref('contacts', order_by=id, lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Program(Base):
    __tablename__ = 'programs'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    notes = S.Column(S.Unicode)
    dates = S.Column(S.Unicode)
    realdate_start = S.Column(S.DateTime)
    realdate_end = S.Column(S.DateTime)
    url = S.Column(S.Unicode)

    institution_id = S.Column(S.ForeignKey('institutions.id'))
    institution = S.orm.relation(
        Institution, backref=S.orm.backref('programs', order_by=id,
                                           lazy='dynamic'))
    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        Country, backref=S.orm.backref('programs', order_by=id,
                                       lazy='dynamic'))
    contact_id = S.Column(S.ForeignKey('contacts.id'))
    contact = S.orm.relation(
        Contact, backref=S.orm.backref('programs', order_by=id,
                                       lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Ship(Base):
    __tablename__ = 'ships'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    full_name = S.Column(S.Unicode)
    shipcode = S.Column(S.Unicode)
    url = S.Column(S.Unicode)

    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        Country, backref=S.orm.backref('ships', order_by=id,
                                       lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


cruises_institutions = S.Table('cruises_institutions', _metadata,
    S.Column('cruise_id', S.ForeignKey('cruises.id')),
    S.Column('institution_id', S.ForeignKey('institutions.id')),
)


cruises_programs = S.Table('cruises_programs', _metadata,
    S.Column('cruise_id', S.ForeignKey('cruises.id')),
    S.Column('program_id', S.ForeignKey('programs.id')),
)


class TrackHolder():
    def get_track(self):
        if self.track:
            return wkb.loads(str(self.track.geom_wkb))
        return None


class Cruise(Base, TrackHolder):
    __tablename__ = 'cruises'

    id = S.Column(S.Integer, primary_key=True)
    location_notes = S.Column(S.Unicode)
    cruise_dates = S.Column(S.Unicode)
    date_start = S.Column(S.DateTime)
    date_end = S.Column(S.DateTime)
    frequency = S.Column(S.Unicode)
    identifier = S.Column(S.Unicode)
    track = GeometryColumn(LineString(2))
    expocode = S.Column(S.Unicode)
    country = S.Column(S.Unicode)
    ship_code = S.Column(S.Unicode)
    basin = S.Column(S.Unicode)
    year = S.Column(S.Integer)
    file_location = S.Column(S.Unicode)
    location_key_words = S.Column(S.Unicode)
    status = S.Column(S.Unicode)

    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        Country, backref=S.orm.backref('cruises', order_by=id, lazy='dynamic'))
    ship_id = S.Column(S.ForeignKey('ships.id'))
    ship = S.orm.relation(
        Ship, backref=S.orm.backref('cruises', order_by=id, lazy='dynamic'))

    institutions = S.orm.relationship(
        'Institution', secondary=cruises_institutions, backref='cruises')
    programs = S.orm.relationship(
        'Program', secondary=cruises_programs, backref='cruises')

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Alias(Base):
    __tablename__ = 'aliases'

    id = S.Column(S.Integer, primary_key=True)
    alias = S.Column(S.Unicode)

    cruise_id = S.Column(S.ForeignKey('cruises.id'))
    cruise = S.orm.relation(
        Cruise, backref=S.orm.backref('aliases', order_by=id, lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Resource(Base):
    __tablename__ = 'resources'

    id = S.Column(S.Integer, primary_key=True)
    type = S.Column(S.Unicode)
    description = S.Column(S.Unicode)
    url = S.Column(S.Unicode)
    note = S.Column(S.Unicode)

    file_file_name = S.Column(S.Unicode)
    file_content_type = S.Column(S.Unicode)
    file_file_size = S.Column(S.Integer)
    file_updated_at = S.Column(S.DateTime)

    cruise_id = S.Column(S.ForeignKey('cruises.id'))
    cruise = S.orm.relation(
        Cruise, backref=S.orm.backref('resources', order_by=id,
                                      lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Suggestion(Base, TrackHolder):
    __tablename__ = 'suggestions'

    id  = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    location = S.Column(S.Unicode)
    cruise_dates = S.Column(S.Unicode)
    country = S.Column(S.Unicode)
    ship = S.Column(S.Unicode)
    url = S.Column(S.Unicode)
    notes = S.Column(S.Unicode)
    programs = S.Column(S.Unicode)
    contacts = S.Column(S.Unicode)
    institutions = S.Column(S.Unicode)
    entry_contact = S.Column(S.Unicode)
    entry_email = S.Column(S.Unicode)
    moderated = S.Column(S.Boolean, nullable=False, default=False)

    track = GeometryColumn(LineString(2))

    file_file_name = S.Column(S.Unicode)
    file_content_type = S.Column(S.Unicode)
    file_file_size = S.Column(S.Integer)
    file_updated_at = S.Column(S.DateTime)

    cruise_id = S.Column(S.ForeignKey('cruises.id'))
    cruise = S.orm.relation(
        Cruise, backref=S.orm.backref('suggestions', order_by=id,
                                      lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


def session():
    return sessionmaker()


def _ensure_cruise(cruise, importer):
    import_id = 'seahunt%s' % str(cruise.id)
    cs = models.Cruise.get_by_attrs(import_id=import_id)
    if len(cs) > 0:
        c = cs[0]
        implog.info('Updating Seahunt Cruise %s: %s' % (import_id, c.id))
    else:
        implog.info('Creating Seahunt Cruise %s' % import_id)
        c = models.Cruise(importer)
        c.save()
    update_attr(c, 'import_id', import_id, importer)
    return c


def _import_cruise(session, importer, cruise, sftp_goship):
    c = _ensure_cruise(cruise, importer)

    c.acknowledge(importer)
    c.creation_stamp.timestamp = cruise.created_at
    c.pending_stamp.timestamp = cruise.updated_at
    c.save()

    aliases = [a.alias for a in cruise.aliases.all()]
    if cruise.identifier:
        update_attr(c, 'expocode', cruise.identifier, importer)
    else:
        if aliases:
            update_attr(c, 'expocode', aliases[0], importer)
            aliases = aliases[1:]
    if aliases:
        update_attr(c, 'aliases', aliases, importer)
    if cruise.expocode:
        update_attr(c, 'expocode', cruise.expocode, importer, accept=False)
    if cruise.status:
        update_attr(c, 'statuses', [cruise.status], importer)
    if cruise.location_notes:
        update_attr(c, 'ports', [cruise.location_notes], importer)
    if cruise.frequency:
        update_attr(c, 'frequency', cruise.frequency, importer)
    if cruise.location_key_words:
        update_attr(c, 'ports', cruise.location_key_words, importer,
                    accept=False)

    if cruise.country:
        country = _import_country(cruise.country, importer)
        update_attr(c, 'country', country.id, importer)

    if cruise.ship:
        ship = _import_ship(cruise.ship, importer)
        update_attr(c, 'ship', ship.id, importer)

    collections = []
    if cruise.basin:
        basin = _import_Collection(importer, cruise.basin, 'basin')
        collections.append(basin)
    for program in cruise.programs:
        collections.append(_import_program(program, importer))

    if collections:
        update_attr(c, 'collections', [c.id for c in collections], importer)

    for resource in cruise.resources:
        _import_resource(resource, importer, sftp_goship)

    ds = None
    de = None
    if cruise.date_start:
        ds = update_attr(c, 'date_start', cruise.date_start, importer)
    if cruise.date_end:
        de = update_attr(c, 'date_end', cruise.date_end, importer)
    if cruise.cruise_dates and (ds or de):
        if ds and not de:
            update_attr(c, 'date_end', cruise.cruise_dates, importer)
        elif de and not ds:
            update_attr(c, 'date_start', cruise.cruise_dates, importer)
        else:
            update_attr(c, 'date_start', cruise.cruise_dates, importer,
                        accept=False)

    if cruise.track:
        update_attr(c, 'track', cruise.get_track(), importer)
    return c


def _import_cruises(sftp_goship, session, importer):
    cruises = session.query(Cruise).all()
    for c in cruises:
        _import_cruise(session, importer, c, sftp_goship)


def _import_inst(inst, importer):
    import_id = 'seahunt%d' % inst.id
    institutions = models.Institution.get_by_attrs(import_id=import_id)
    if len(institutions) > 0:
        institution = institutions[0]
        implog.info("Updating Seahunt Institution %s: %s" % (import_id,
                                                             institution.id))
    else:
        implog.info("Creating Institution %s" % import_id)
        institution = models.Institution(importer)
        institution.save()
        institution.set_accept('import_id', import_id, importer)

    institution.acknowledge(importer)
    institution.creation_stamp.timestamp = inst.created_at
    institution.pending_stamp.timestamp = inst.updated_at

    names = filter(None, [inst.name, inst.full_name])
    if names:
        implog.info(names[0])
        update_attr(institution, 'name', names[0], importer)
        for name in names[1:]:
            update_attr(institution, 'name', name, importer, accept=False)

    if inst.phone:
        update_attr(institution, 'phone', inst.phone, importer)
    if inst.address:
        update_attr(institution, 'address', inst.address, importer)
    if inst.url:
        update_attr(institution, 'url', inst.url, importer)
    if inst.country:
        country = _import_country(inst.country, importer)
        update_attr(institution, 'country', country.id, importer)

    for cruise in inst.cruises:
        c = _ensure_cruise(cruise, importer)
        insts = c.get('institutions', [])
        insts.append(institution.id)
        update_attr(c, 'institutions', insts, importer)
    return institution


def _import_institutions(session, importer):
    institutions = session.query(Institution).all()
    for inst in institutions:
        _import_inst(inst, importer)


def _import_country(country, importer):
    import_id = 'seahunt%d' % country.id
    countries = models.Country.get_by_attrs(import_id=import_id)
    if len(countries) > 0:
        c = countries[0]
        implog.info("Updating Country %s: %s" % (import_id, c.id))
    else:
        implog.info("Creating Country %s" % import_id)
        c = models.Country(importer)
        c.save()
        update_attr(c, 'import_id', import_id, importer)

    update_attr(c, 'iso_3166-1', country.name, importer)
    update_attr(c, 'iso_3166-alpha-2', country.country_code, importer)
    return c


def _import_contact(contact, importer):
    import_id = 'seahunt%d' % contact.id
    people = models.Person.get_by_attrs(import_id=import_id)
    if len(people) > 0:
        p = people[0]
    else:
        p = models.Person()
        p.creation_stamp.timestamp = contact.created_at
        p.save()
        p.set_accept('import_id', import_id, importer)

    if contact.first_name:
        p.name_first = contact.first_name
    if contact.last_name:
        p.name_last = contact.last_name
    if contact.email:
        p.email = contact.email
    if contact.institution:
        inst = _import_inst(contact.institution, importer)
        p.institution = inst.id
    p.save()

    if contact.title:
        update_attr(p, 'title', contact.title, importer)
    if contact.job_title:
        update_attr(p, 'job_title', contact.job_title, importer)
    if contact.phone:
        update_attr(p, 'phone', contact.phone, importer)
    if contact.fax:
        update_attr(p, 'fax', contact.fax, importer)
    if contact.address:
        update_attr(p, 'address', contact.address, importer)

    programs = []
    for program in contact.programs:
        programs.append(_import_program(program, importer))
    if programs:
        update_attr(p, 'programs', [x.id for x in programs], importer)

    if contact.notes:
        update_note(p, contact.notes, p)
    return p


def _import_contacts(session, importer):
    contacts = session.query(Contact).all()
    for contact in contacts:
        _import_contact(contact, importer)


def _import_ship(ship, importer):
    import_id = 'seahunt%d' % ship.id
    ships = models.Ship.get_by_attrs(import_id=import_id)
    if len(ships) > 0:
        s = ships[0]
    else:
        s = models.Ship(importer)
        s.creation_stamp.timestamp = _date_to_datetime(ship.created_at)
        s.save()

    if ship.full_name:
        update_attr(s, 'name', ship.full_name, importer)
    if ship.shipcode:
        update_attr(s, 'nodc_platform_code', ship.shipcode, importer)
    if ship.url:
        update_attr(s, 'url', ship.url, importer)
    if ship.country:
        country = _import_country(ship.country, importer)
        update_attr(s, 'country', country.id, importer)
    return s


def _import_program(program, importer):
    import_id = 'seahunt%d' % program.id
    programs = models.Collection.get_by_attrs(import_id=import_id)
    if len(programs) > 0:
        p = programs[0]
    else:
        p = models.Collection(importer)
        p.creation_stamp.timestamp = program.created_at
        p.save()

    update_attr(p, 'names', filter(None, [program.name, program.notes]),
                importer)
    update_attr(p, 'date_start', program.name, importer)
    update_attr(p, 'date_end', program.name, importer)
    update_attr(p, 'url', program.name, importer)
    update_attr(p, 'institution', program.name, importer)
    update_attr(p, 'country', program.name, importer)
    update_attr(p, 'name', program.name, importer)
    return p


def _import_resource(resource, importer, sftp_goship):
    if not resource.cruise:
        return None
    cruise = _ensure_cruise(resource.cruise, importer)
    if resource.type == 'URLResource':
        update_attr(
            cruise, 'link', resource.url,
            importer, note=resource.description, note_data_type=resource.note)
    elif resource.type == 'NoteResource':
        update_note(cruise, resource.note, importer, resource.description)
    elif (resource.type == 'FileResource' or
          resource.type == 'ThumbMapResource' or
          resource.type == 'MapResource'):
        file = FieldStorage()
        file.filename = resource.file_file_name
        file.type = resource.file_content_type
        cruise_id = cruise.get('import_id').replace('seahunt', '')
        path = os.path.join(rails_root, 'public', 'docs', 'ids', cruise_id,
                            file.filename)
        with sftp_dl(sftp_goship, path) as downloaded:
            file.file = downloaded
            if resource.type == 'FileResource':
                a = update_attr(cruise, 'data_suggestion', file, importer)
            elif resource.type == 'ThumbMapResource':
                a = update_attr(cruise, 'map_thumb', file, importer)
            elif resource.type == 'MapResource':
                a = update_attr(cruise, 'map_full', file, importer)
        a.creation_stamp.timestamp = resource.file_updated_at
        a.save()
        if resource.description or resource.note:
            update_note(a, resource.note, importer, resource.description)
    else:
        implog.error('Unknown resource type %s' % resource.type)


def _import_suggestion_contact(name, email, importer):
    if name is None and email is None:
        return None
    if name is None:
        name = email
    import_id = 'seahunt%s' % name
    people = models.Person.get_by_attrs(import_id=import_id)
    if len(people) > 0:
        person = people[0]
    else:
        person = models.Person(name_first=name, name_last='seahunt',
                               email=email)
        person.save()
        update_attr(person, 'import_id', import_id, importer)
    return person


def _import_suggestion(suggestion, importer):
    if suggestion.moderated:
        return None

    person = _import_suggestion_contact(
        suggestion.entry_contact, suggestion.entry_email, importer)
    if not person:
        person = importer

    suggestion.id = '_suggestion%d' % suggestion.id
    cruise = _ensure_cruise(suggestion, person)

    update_attr(cruise, 'import_id', 'seahunt%s' % str(suggestion.id), importer)

    update_attr(cruise, 'expocode', suggestion.name, person, accept=False)
    update_attr(cruise, 'ports', [suggestion.location], person, accept=False)
    update_attr(cruise, 'date_start', suggestion.cruise_dates, person,
                accept=False)
    update_attr(cruise, 'country', suggestion.country, person, accept=False)
    update_attr(cruise, 'ship', suggestion.ship, person, accept=False)
    update_attr(cruise, 'url', suggestion.url, person, accept=False)
    update_note(cruise, suggestion.notes, person)
    update_note(cruise, suggestion.programs, person, 'programs')
    update_note(cruise, suggestion.contacts, person, 'contacts')
    update_attr(cruise, 'institutions', suggestion.institutions.split(','),
                person, accept=False)
    if suggestion.track:
        update_attr(cruise, 'track', suggestion.get_track(), importer,
                    accept=False)
    return cruise


def _import_suggestions(session, importer):
    suggestions = session.query(Suggestion).all()
    for suggestion in suggestions:
        _import_suggestion(suggestion, importer)


def import_(*args):
    with sftp('goship.ucsd.edu') as (ssh_goship, sftp_goship):
        _import_cruises(sftp_goship, *args)
    _import_institutions(*args)
    _import_contacts(*args)
    _import_suggestions(*args)
