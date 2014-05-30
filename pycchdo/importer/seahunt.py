from cgi import FieldStorage
import os
import re

import transaction

import sqlalchemy as S
import sqlalchemy.orm
import sqlalchemy.ext.declarative

from geoalchemy import GeometryColumn
from geoalchemy import LineString as LS

from shapely import wkb

from pycchdo.importer import *
from pycchdo.importer.cchdo import *
import pycchdo.models as models
from pycchdo.models.serial import (
    store_context, 
    Cruise, Person, Obj, Institution, Country, Ship, Collection, 
    Participant, Participants, 
    )


Base = S.ext.declarative.declarative_base()
_metadata = Base.metadata


cred = ['seahunt_web', 'll0yd315']


docs_root = os.path.join(os.path.sep, 'Users', 'myshen', 'seahunt', 'docs')


url = S.engine.url.URL(
    'postgresql', cred[0], cred[1], 'sui.ucsd.edu', port=55432,
    database='seahunt')


engine = S.create_engine(url, use_native_unicode=False)


sessionmaker = S.orm.sessionmaker(bind=engine)


def session():
    return sessionmaker()


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


class SCountry(Base):
    __tablename__ = 'countries'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    abbreviation = S.Column(S.Unicode)
    country_code = S.Column(S.Unicode)

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class SInstitution(Base):
    __tablename__ = 'institutions'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    full_name = S.Column(S.Unicode)
    phone = S.Column(S.Unicode)
    address = S.Column(S.Unicode)
    url = S.Column(S.Unicode)

    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        SCountry, backref=S.orm.backref('institutions', order_by=id,
                                       lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class SContact(Base):
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
        SInstitution, backref=S.orm.backref('contacts', order_by=id, lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class SProgram(Base):
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
        SInstitution, backref=S.orm.backref('programs', order_by=id,
                                           lazy='dynamic'))
    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        SCountry, backref=S.orm.backref('programs', order_by=id,
                                       lazy='dynamic'))
    contact_id = S.Column(S.ForeignKey('contacts.id'))
    contact = S.orm.relation(
        SContact, backref=S.orm.backref('programs', order_by=id,
                                       lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class SShip(Base):
    __tablename__ = 'ships'

    id = S.Column(S.Integer, primary_key=True)
    name = S.Column(S.Unicode)
    full_name = S.Column(S.Unicode)
    shipcode = S.Column(S.Unicode)
    url = S.Column(S.Unicode)

    country_id = S.Column(S.ForeignKey('countries.id'))
    country = S.orm.relation(
        SCountry, backref=S.orm.backref('ships', order_by=id,
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


class SCruise(Base, TrackHolder):
    __tablename__ = 'cruises'

    id = S.Column(S.Integer, primary_key=True)
    location_notes = S.Column(S.Unicode)
    cruise_dates = S.Column(S.Unicode)
    date_start = S.Column(S.DateTime)
    date_end = S.Column(S.DateTime)
    frequency = S.Column(S.Unicode)
    identifier = S.Column(S.Unicode)
    track = GeometryColumn(LS(2))
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
        SCountry, backref=S.orm.backref('cruises', order_by=id, lazy='dynamic'))
    ship_id = S.Column(S.ForeignKey('ships.id'))
    ship = S.orm.relation(
        SShip, backref=S.orm.backref('cruises', order_by=id, lazy='dynamic'))

    contacts = S.orm.relationship(
        'SContact', secondary=contacts_cruises, backref='cruises')
    institutions = S.orm.relationship(
        'SInstitution', secondary=cruises_institutions, backref='cruises')
    programs = S.orm.relationship(
        'SProgram', secondary=cruises_programs, backref='cruises')

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


class Alias(Base):
    __tablename__ = 'aliases'

    id = S.Column(S.Integer, primary_key=True)
    alias = S.Column(S.Unicode)

    cruise_id = S.Column(S.ForeignKey('cruises.id'))
    cruise = S.orm.relation(
        SCruise, backref=S.orm.backref('aliases', order_by=id, lazy='dynamic'))

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
        SCruise, backref=S.orm.backref('resources', order_by=id,
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

    track = GeometryColumn(LS(2))

    file_file_name = S.Column(S.Unicode)
    file_content_type = S.Column(S.Unicode)
    file_file_size = S.Column(S.Integer)
    file_updated_at = S.Column(S.DateTime)

    cruise_id = S.Column(S.ForeignKey('cruises.id'))
    cruise = S.orm.relation(
        SCruise, backref=S.orm.backref('suggestions', order_by=id,
                                      lazy='dynamic'))

    created_at = S.Column(S.TIMESTAMP)
    updated_at = S.Column(S.TIMESTAMP)


def _ensure_cruise(cruise, updater):
    import_id = 'seahunt{0}'.format(cruise.id)
    ccc = Cruise.query().filter(Cruise.import_id == import_id).first()
    if ccc:
        log.info('Updating Seahunt Cruise %s: %s' % (import_id, ccc.id))
    else:
        log.info('Creating Seahunt Cruise %s' % import_id)
        ccc = Cruise.propose(updater.importer).obj
    ccc.import_id = import_id
    return ccc


def _import_cruise(updater, cruise, downloader):
    c = _ensure_cruise(cruise, updater)
    cc = c.change
    cc.acknowledge(updater.importer)
    cc.ts_c = cruise.created_at
    cc.ts_ack = cruise.updated_at

    aliases = [a.alias for a in cruise.aliases.all()]
    if cruise.identifier:
        updater.attr(c, 'expocode', cruise.identifier)
    else:
        if aliases:
            updater.attr(c, 'expocode', aliases[0])
            aliases = aliases[1:]
    if aliases:
        updater.attr(c, 'aliases', aliases)
    if cruise.expocode:
        updater.attr(c, 'expocode', cruise.expocode, accept=False)
    if cruise.status:
        updater.attr(c, 'statuses', [cruise.status])
    if cruise.location_notes:
        updater.attr(c, 'ports', [cruise.location_notes])
    if cruise.frequency:
        updater.attr(c, 'frequency', cruise.frequency)
    if cruise.location_key_words:
        updater.attr(c, 'ports', cruise.location_key_words, accept=False)

    if cruise.country:
        country = _import_country(cruise.country, updater)
        updater.attr(c, 'country', country)

    if cruise.ship:
        ship = _import_ship(cruise.ship, updater)
        updater.attr(c, 'ship', ship)

    if cruise.contacts:
        participants = Participants()
        for contact in cruise.contacts:
            participants.add(Participant.create(
                'contact', _import_contact(contact, updater)))
        if participants != c.participants:
            c.set(updater.importer, 'participants', participants)

    if cruise.institutions:
        institutions = []
        for inst in cruise.institutions:
            institutions.append(_import_inst(inst, updater))
        if institutions != c.institutions:
            updater.attr(c, 'institutions', institutions)

    collections = []
    if cruise.basin:
        basin = import_Collection(updater, cruise.basin, 'basin')
        collections.append(basin)

    for program in cruise.programs:
        collections.append(_import_program(program, updater))

    if collections:
        updater.attr(c, 'collections', collections)

    for resource in cruise.resources:
        _import_resource(resource, updater, downloader)

    ds = None
    de = None
    if cruise.date_start:
        ds = updater.attr(c, 'date_start', cruise.date_start)
    if cruise.date_end:
        de = updater.attr(c, 'date_end', cruise.date_end)
    if cruise.cruise_dates and (ds or de):
        if ds and not de:
            updater.attr(c, 'date_end', cruise.cruise_dates)
        elif de and not ds:
            updater.attr(c, 'date_start', cruise.cruise_dates)
        else:
            updater.attr(c, 'date_start', cruise.cruise_dates, accept=False)
    if cruise.track:
        updater.attr(c, 'track', cruise.get_track())
    return c


def _import_cruises(downloader, sesh, updater):
    cruises = sesh.query(SCruise).all()
    for c in cruises:
        _import_cruise(updater, c, downloader)


def _ensure_inst(updater, inst_id):
    import_id = 'seahunt%d' % inst_id
    institution = Institution.query().filter(
        Institution.import_id == import_id).first()
    if institution:
        log.info("Updating Seahunt Institution {0}: {1}".format(
            import_id, institution))
    else:
        log.info("Creating Institution %s" % import_id)
        institution = Institution.create(updater.importer).obj
        institution.import_id = import_id
    return institution


def _import_inst(inst, updater):
    institution = _ensure_inst(updater, inst.id)
    delta = institution.change
    delta.acknowledge(updater.importer)
    delta.ts_c = inst.created_at
    delta.ts_ack = inst.updated_at

    names = filter(None, [inst.name, inst.full_name])
    if names:
        log.info(names[0])
        updater.attr(institution, 'name', names[0])
        for name in names[1:]:
            updater.attr(institution, 'name', name, accept=False)

    if inst.phone:
        updater.attr(institution, 'phone', inst.phone)
    if inst.address:
        updater.attr(institution, 'address', inst.address)
    if inst.url:
        updater.attr(institution, 'url', inst.url)
    if inst.country:
        country = _import_country(inst.country, updater)
        updater.attr(institution, 'country', country)
    return institution


def _import_institutions(sesh, updater):
    institutions = sesh.query(SInstitution).all()
    for inst in institutions:
        _import_inst(inst, updater)


def _ensure_country(updater, country_id):
    import_id = 'seahunt%d' % country_id
    c = Country.query().filter(
        Country.import_id == import_id).first()
    if c:
        log.info("Updating Country %s: %s" % (import_id, c.id))
    else:
        log.info("Creating Country %s" % import_id)
        c = Country.create(updater.importer).obj
        c.import_id = import_id
    return c


def _import_country(country, updater):
    c = _ensure_country(updater, country.id)
    c.name = country.name
    c.alpha2 = country.country_code
    return c


def _import_contact(contact, updater):
    import_id = 'seahunt%d' % contact.id
    p = Person.query().filter(
        Person.import_id == import_id).first()
    if p:
        log.info('Updating Seahunt Contact %s: %s' % (import_id, p.id))
    else:
        log.info('Creating Seahunt Contact %s' % import_id)
        p = import_person(updater, import_id, None, identifier=import_id)
        p.ts_c = contact.created_at
        p.import_id = import_id

    if contact.first_name:
        p.name_first = contact.first_name
    if contact.last_name:
        p.name_last = contact.last_name
    if contact.first_name or contact.last_name:
        p.name = ' '.join(filter(None, [p.name_first, p.name_last]))
    if contact.email:
        p.email = contact.email
    if contact.institution:
        inst = _import_inst(contact.institution, updater)
        updater.attr(p, 'institution', inst)

    if contact.title:
        updater.attr(p, 'title', contact.title)
    if contact.job_title:
        updater.attr(p, 'job_title', contact.job_title)
    if contact.phone:
        updater.attr(p, 'phone', contact.phone)
    if contact.fax:
        updater.attr(p, 'fax', contact.fax)
    if contact.address:
        updater.attr(p, 'address', contact.address)

    programs = []
    for program in contact.programs:
        programs.append(_import_program(program, updater))
    if programs:
        updater.attr(p, 'programs', programs)

    if contact.notes:
        updater.note(p, contact.notes)
    return p


def _import_contacts(sesh, updater):
    contacts = sesh.query(SContact).all()
    for contact in contacts:
        _import_contact(contact, updater)


def _ensure_ship(updater, ship_id):
    import_id = 'seahunt%d' % ship_id
    s = Ship.query().filter(
        Ship.import_id == import_id).first()
    if not s:
        s = Ship.create(updater.importer).obj
        s.import_id = import_id
    return s


def _import_ship(ship, updater):
    s = _ensure_ship(updater, ship.id)
    s.ts_c = _date_to_datetime(ship.created_at)
    if ship.full_name:
        updater.attr(s, 'name', ship.full_name)
    if ship.shipcode:
        updater.attr(s, 'nodc_platform_code', ship.shipcode)
    if ship.url:
        updater.attr(s, 'url', ship.url)
    if ship.country:
        country = _import_country(ship.country, updater)
        updater.attr(s, 'country', country)
    return s


def _import_program(program, updater):
    import_id = 'seahunt%d' % program.id
    col = Collection.query().filter(
        Collection.import_id == import_id).first()
    if not col:
        col = updater.create_accept(Collection)
        col.ts_c = program.created_at
        col.import_id = import_id

    updater.attr(col, 'names', filter(None, [program.name, program.notes]))
    if program.dates:
        attr = updater.attr(col, 'date_start', program.dates, accept=False)
        attr.accept(updater.importer, program.realdate_start)
    updater.attr(col, 'date_end', program.realdate_end)
    updater.attr(col, 'url', program.url)

    if program.institution_id:
        updater.attr(
            col, 'institution',
            _ensure_inst(updater, program.institution_id))
    if program.country_id:
        updater.attr(
            col, 'country', _ensure_country(updater, program.country_id))
    return col


def _import_resource(resource, updater, downloader):
    if not resource.cruise:
        log.error('Resource %s is missing cruise' % resource.id)
        return None
    cruise = _ensure_cruise(resource.cruise, updater)
    if resource.type == 'URLResource':
        a = cruise.set(updater.importer, 'link', resource.url)
        updater.note(a, resource.description, resource.note)
        a.ts_c = resource.created_at
    elif resource.type == 'NoteResource':
        updater.note(cruise, resource.note, resource.description)
    elif (resource.type == 'FileResource' or
          resource.type == 'ThumbMapResource' or
          resource.type == 'MapResource'):
        file = FieldStorage()
        file.filename = resource.file_file_name
        file.type = resource.file_content_type
        if not file.type:
            file.type = guess_mime_type(file.filename)
        cruise_id = cruise.import_id.replace('seahunt', '')
        path = os.path.join(docs_root, 'ids', cruise_id,
                            file.filename)
        with downloader.dl(path) as downloaded:
            if downloaded:
                file.file = downloaded
                with su():
                    if resource.type == 'FileResource':
                        a = updater.attr(cruise, 'data_suggestion', file)
                    elif resource.type == 'ThumbMapResource':
                        a = updater.attr(cruise, 'map_thumb', file)
                    elif resource.type == 'MapResource':
                        a = updater.attr(cruise, 'map_full', file)
                a.ts_c = resource.file_updated_at
                if resource.description or resource.note:
                    updater.note(a, resource.note, resource.description)
    else:
        log.error('Unknown resource type %s' % resource.type)


def _import_suggestion_contact(name, email, updater):
    if name is None and email is None:
        return None
    if name is None:
        name = email
    import_id = 'seahunt%s' % name
    person = Person.query().filter(
        Person.import_id == import_id).first()
    if not person:
        person = Person.create().obj
        person.set_id_names(name=name)
        person.email = email
        person.import_id = import_id
    return person


def _import_suggestion(suggestion, updater):
    if suggestion.moderated:
        return None

    person = _import_suggestion_contact(
        suggestion.entry_contact, suggestion.entry_email, updater)
    if not person:
        person = updater.importer

    suggestion.id = '_suggestion%d' % suggestion.id
    cruise = _ensure_cruise(suggestion, updater)

    cruise.import_id = 'seahunt%s' % str(suggestion.id)

    updater.attr(cruise, 'expocode', suggestion.name, accept=False)
    updater.attr(cruise, 'ports', [suggestion.location], accept=False)
    updater.attr(cruise, 'date_start', suggestion.cruise_dates, accept=False)
    updater.attr(cruise, 'country', suggestion.country, accept=False)
    updater.attr(cruise, 'ship', suggestion.ship, accept=False)
    updater.attr(cruise, 'link', suggestion.url, accept=False)
    updater.note(cruise, suggestion.notes)
    updater.note(cruise, suggestion.programs, 'programs')
    updater.note(cruise, suggestion.contacts, 'contacts')

    updater.attr(
        cruise, 'institutions', suggestion.institutions.split(','),
        accept=False)
    if suggestion.track:
        updater.attr(cruise, 'track', suggestion.get_track(), accept=False)
    return cruise


def _import_suggestions(sesh, updater):
    suggestions = sesh.query(Suggestion).all()
    for suggestion in suggestions:
        _import_suggestion(suggestion, updater)


def clear():
    log.info('Clearing all Seahunt imports')

    person = Person.query().\
        filter(Person.name_last == 'importer').\
        filter(Person.name_first == 'Seahunt').first()

    attrs = _Attr.get_all_by_attrs(
        {'key': 'import_id', 'value': re.compile('seahunt.*')})
    objs = [x.obj for x in attrs]

    if person:
        objs = objs + Obj.query().filter(Obj.p_c == person).all()

    plog = ProgressLog(objs)
    for obj in objs:
        obj.remove()
        plog.log()

    max_id = Obj.query().order(Obj.ts_c.desc()).first().id

    log.info('Cleared Seahunt imports')
    return 


def import_(import_gid, fsstore, args):
    dl_files = not args.skip_downloads

    log.info("Get/Create Seahunt Importer to take blame")
    updater = Updater(
        import_person(None, 'importer', 'Seahunt', 'Seahunt_importer'))

    log.info('Connecting to seahunt db')
    with db_session(session()) as sesh, store_context(fsstore):
        su = (sesh, updater)

        with conn_dl('sui.ucsd.edu', args.skip_downloads,
                     import_gid) as downloader:
            log.info('Importing cruises')
            _import_cruises(downloader, sesh, updater)
        if not args.files_only:
            log.info('Importing institutions')
            _import_institutions(*su)
            log.info('Importing contacts')
            _import_contacts(*su)
            log.info('Importing suggestions')
            _import_suggestions(*su)
        transaction.commit()
    log.info('seahunt import done')
