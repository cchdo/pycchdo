import datetime
import os

from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPSeeOther
from pyramid.response import Response
from pyramid.path import AssetResolver

from webob.multidict import MultiDict

import geojson.mapping

from pykml.factory import KML_ElementMaker as KML
from pykml.factory import ATOM_ElementMaker as ATOM
from pykml.factory import GX_ElementMaker as GX

from lxml import etree

from webhelpers import text as whtext

from sqlalchemy.ext.associationproxy import _AssociationList

from libcchdo.fns import uniquify

from pycchdo.models.file_types import data_file_descriptions
from pycchdo.models.serial import (
    DBSession,
    Change, Cruise, Note, Person, Institution, FSFile,
    Participants, Participant,
    )
import pycchdo.helpers as h

from . import *
from pycchdo.views.session import require_signin
from pycchdo.views.obj import _obj_new
from pycchdo.views import log, staff


_DISALLOWED_CRUISE_ATTR_TYPES = [
    'ParticipantsType', 'ParameterInformations', 'File',
]


_DISALLOWED_CRUISE_ATTR_KEYS = [
    'data_dir', 'import_id', 'data_suggestion', 'archive', 'track',
]


def _allowed_attrs_select(cls, disallowed_types=[], disallowed_keys=[]):
    sel = []
    for k, v in cls.allowed_attrs.items():
        if k in disallowed_types:
            continue
        keys = []
        for x in v:
            if x in disallowed_keys:
                continue
            keys.append((x, cls.allowed_attrs_human_names[x]))
        if keys:
            sel.append((keys, k))
    return sel


def cruise_attrs_select():
    return _allowed_attrs_select(
        Cruise, _DISALLOWED_CRUISE_ATTR_TYPES, _DISALLOWED_CRUISE_ATTR_KEYS)


def _cruises(request, subtypes=None, defer_load=False):
    seahunt = request.params.get('seahunt_only', False)
    allow_seahunt = request.params.get('allow_seahunt', False)
    if seahunt:
        query = Cruise.query().filter(Cruise.accepted == False).filter(Cruise.ts_j == None)
    elif allow_seahunt:
        query = Cruise.query()
    else:
        query = Cruise.query().filter(Cruise.accepted == True)

    cruises = query.all()
    cruises = sorted(cruises, key=lambda c: c.uid)
    if not defer_load:
        h.reduce_specificity(request, *cruises)
    return cruises


def cruises_index(request):
    cruises = paged(request, _cruises(request, defer_load=True))
    h.reduce_specificity(request, *cruises)
    return {'cruises': cruises}


def cruises_index_json(request):
    if request.params.get('pending_years'):
        return Cruise.pending_years()
    elif request.params.get('id'):
        id = request.params.get('id')
        try:
            cruise = Cruise.get_by_id(id)
        except ValueError:
            raise HTTPBadRequest()
        return _cruise_to_json(cruise)
    elif request.params.get('ids'):
        ids = [x.strip() for x in request.params.get('ids').split(',')]
        try:
            cruises = [Cruise.get_by_id(cruise_id) for cruise_id in ids]
        except ValueError:
            raise HTTPBadRequest()
        return [_cruise_to_json(cruise) for cruise in cruises]
    elif request.params.get('contributions'):
        return _contributions(request)
    elif request.params.get('contribution_kmzs'):
        return _contribution_kmzs(request)

    cruises = [c.to_dict() for c in _cruises(request)]
    return cruises


def cruises_archive(request):
    return staff.archive(
        request, _cruises(request), formats=['woce', 'exchange'])


def _suggest_file(request, cruise_obj):
    try:
        type = request.params['type']
        if not type in data_file_descriptions.keys():
            log.warn('Attempted to suggest file with improper type')
            request.response_status_int = 400
            request.session.flash(
                'Invalid file type %s.' % type, 'help')
            request.session.flash(
                'File type must be one of %s' % \
                ', '.join(data_file_descriptions.keys()), 'help')
            return
    except KeyError:
        log.warn('Attempted to suggest file without type')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your file submission was missing a type.', 'help')
        return
    try:
        note = Note(request.user, request.params['notes'])
    except KeyError:
        note = None

    try:
        add_file_action = request.params['add_file_action']
    except KeyError:
        log.warn('Attempted to modify file without action')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'You must specify what to do to that file type.', 'help')
        return

    if add_file_action == 'Set file':
        try:
            file = request.params['file']
            if file == '':
                raise KeyError()
        except KeyError:
            log.warn('Attempted to suggest file without file')
            request.response_status = '400 Bad Request'
            request.session.flash(
                'You did not select a file. Please try again.', 'help')
            return
        change = cruise_obj.sugg(request.user, type, file)
    elif add_file_action == 'Delete file':
        change = cruise_obj.delete(request.user, type)

    if note is not None:
        change._notes.append(note)


def _edit_attr(request, cruise_obj):
    try:
        key = request.params['key']
        allowed_list = []
        for attrs, category in cruise_attrs_select():
            allowed_list.extend([attr[0] for attr in attrs])
        if key not in allowed_list:
            log.warn('Attempted to edit attribute with illegal key')
            request.response_status = '400 Bad Request'
            request.session.flash(
                'The attribute key must be one of {0}.'.format(
                    ', '.join(sorted(allowed_list))), 'help')
            return
    except KeyError:
        log.warn('Attempted to edit attribute without key')
        request.response_status = '400 Bad Request'
        request.session.flash('You must specify a key to edit', 'help')
        return
    try:
        edit_action = request.params['edit_action']
    except KeyError:
        log.warn('Attempted to edit attribute without a specified action')
        request.response_status = '400 Bad Request'
        request.session.flash('You must specify what to do to %s' % key, 'help')
        return

    note = None
    try:
        str_note = request.params['notes']
        if str_note:
            note = Note(request.user, str_note)
    except KeyError:
        pass

    if edit_action == 'Set':
        try:
            value = request.params['value']
        except KeyError:
            log.info(
                u'{0!r} attempted to edit attribute without value'.format(
                request.user))
            request.response_status = '400 Bad Request'
            request.session.flash(
                'No value given for the attribute.', 'help')
            return

        value_type = Cruise.attr_type(key)
        try:
            value = text_to_obj(value, value_type)
        except ValueError, e:
            log.error(
                u'Unable to suggest value {0} for attribute {1}:\n{2!r}'.format(
                value, key, e
                ))
            request.response_status = '400 Bad Request'
            request.session.flash(
                u'Bad value for attribute {0}'.format(key), 'help')
            return

        change = cruise_obj.sugg(request.user, key, value)
        if note:
            change._notes.append(note)
        request.session.flash(
            u'Suggested that {0} should become {1}'.format(key, value),
            'action_taken')
    elif edit_action == 'Delete':
        change = cruise_obj.delete(request.user, key)
        if note:
            change._notes.append(note)
        request.session.flash(
            u'Suggested that {0} be deleted'.format(key), 'action_taken')
    elif edit_action == 'Mark reviewed':
        # Remove a cruise data type's preliminary status
        if not h.has_mod(request):
            request.response.status = '403 Forbidden'
            request.session.flash(
                'You must be a moderator to mark data as reviewed', 'help')
            return
        status = cruise_obj.get(key)
        try:
            status.remove(u'preliminary')
            cruise_obj.set(request.user, key, status)
            request.session.flash(
                'Marked {0} for {1} as reviewed'.format(
                    key.replace('_status', ''), cruise_obj.uid),
                'action_taken')
        except ValueError:
            request.session.flash(
                '{0} for {1} is already marked reviewed'.format(
                    key.replace('_status', ''), cruise_obj.uid),
                'help')
    elif edit_action == 'Mark preliminary':
        # Add preliminary status to a cruise data type
        if not h.has_mod(request):
            request.response.status = '403 Forbidden'
            request.session.flash(
                'You must be a moderator to mark files as preliminary', 'help')
            return
        status = uniquify(cruise_obj.get(key, []) + [u'preliminary'])
        try:
            cruise_obj.set(request.user, key, status)
            request.session.flash(
                'Marked {0} for {1} as preliminary'.format(
                    key.replace('_status', ''), cruise_obj.uid),
                'action_taken')
        except ValueError:
            request.session.flash(
                '{0} for {1} is already marked reviewed'.format(
                    key.replace('_status', ''), cruise_obj.uid),
                'help')
    elif edit_action == 'Set participants':
        if key != 'participants':
            request.session.flash(
                u'Invalid action to take on {0}'.format(key), 'help')
            return

        rpis = {}
        keys = ['role', 'person', 'institution']
        for key, value in request.params.items():
            for k in keys:
                if key.startswith(k):
                    id = key[len(k):]
                    try:
                        rpis[id][k] = value
                    except KeyError:
                        rpis[id] = {k: value}
        participants = _rpi_to_participants(rpis)
        if participants is None:
            return

        change = cruise_obj.sugg(request.user, 'participants', participants)
        if change and note:
            change._notes.append(note)
        request.session.flash(
            u'Suggested updated participants for this cruise',
            'action_taken')
    elif edit_action == 'Delete all participants':
        if key == 'participants':
            change = cruise_obj.delete(request.user, 'participants')
            if change and note:
                change._notes.append(note)
            request.session.flash(
                u'Suggested that participants be cleared', 'action_taken')
        else:
            request.session.flash(
                u'Invalid action to take on {0}'.format(key), 'help')
    else:
        request.session.flash(
            u'Unknown edit action: {0}'.format(edit_action), 'help')


def _rpi_obj_get_from_id_str(cls, id_str):
    """Abstract way to get Person or Institution for Participant with warnings.

    """
    try:
        id = int(id_str)
        obj = cls.query().get(id)
        if not obj:
            request.session.flash(
                u'{cls} {id} does not exist'.format(cls=cls, id=id), 'help')
            return None
        return obj
    except (TypeError, ValueError), e:
        log.error(
            u'attempt to get participant {cls} {id}'.format(cls=cls, id=id))
        request.session.flash(
            u'Invalid {cls} id {id}'.format(cls=cls, id=id), 'help')
        return None


def _rpi_to_participants(rpis):
    """Convert dictionary of role, person, institution tuples into Participants.

    Returns::
        list of Participants or None if errors occured

    If any people or institutions do not exist, the error will be flashed and
    the method will return None instead of a list.

    """
    failed = False
    participants = []
    for i, rpi in sorted(rpis.items()):
        role = rpi['role']
        person = rpi['person']
        institution = rpi['institution']

        if not (role or person or institution):
            continue
        
        if person:
            person = _rpi_obj_get_from_id_str(Person, person)
            if person is None:
                failed = True
        else:
            failed = True
            continue
        if institution:
            institution = _rpi_obj_get_from_id_str(Institution, institution)
            if institution is None:
                failed = True
        else:
            institution = None
        participants.append(Participant.create(role, person, institution))
    if failed:
        participants = None
    return participants


def _add_note_to_attr(request):
    try:
        attr_id = request.params['attr_id']
        note = request.params['note']
    except KeyError:
        log.warn('Attempted to add note with missing attributes')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your note was missing an id or the note body. Please try again.',
            'help')
        return

    try:
        public = request.params['public']
    except KeyError:
        public = False

    attr_obj = Change.query().get(attr_id)
    if not attr_obj:
        request.response_status = '404 Not Found'
        request.session.flash(
            'The attribute you tried to add a note to could not be found.', 'help')
        return

    attr_obj._notes.append(Note(request.user, note, discussion=not public))


def _add_note_to_file(request):
    try:
        file_id = request.params['file_id']
        note = request.params['note']
    except KeyError:
        log.warn('Attempted to add note with missing attributes')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your note was missing parts. Please try again.', 'help')
        return

    try:
        public = request.params['public']
    except KeyError:
        public = False

    file_obj = Change.query().get(file_id)
    if not file_obj:
        request.response_status = '404 Not Found'
        request.session.flash(
            'The file you tried to add a note to could not be found.', 'help')
        return

    file_obj._notes.append(Note(request.user, note, discussion=not public))


def _add_note(request, cruise_obj):
    try:
        data_type = request.params['note_data_type']
        action = request.params['note_action']
        summary = request.params['note_summary']
        note = request.params['note_note']
    except KeyError:
        log.warn('Attempted to add note with missing attributes')
        request.response.status = '400 Bad Request'
        request.session.flash('Your note was missing parts. Please try again.',
                              'help')
        return

    try:
        public = request.params['note_discussion']
    except KeyError:
        public = False

    cruise_obj.change._notes.append(
        Note(request.user, note, action, data_type, summary, not public))


def cruise_show(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    try:
        cruise_obj = Cruise.get_by_id(cruise_id)
    except ValueError, err:
        raise HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))

    # If the uid is different, redirect to it
    uid = unicode(cruise_obj.uid)
    if uid != unicode(cruise_id):
        raise HTTPSeeOther(
            location=request.route_path('cruise_show', cruise_id=uid))

    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        if request.params['action'] == 'suggest_file':
            _suggest_file(request, cruise_obj)
        if request.params['action'] == 'edit_attr':
            _edit_attr(request, cruise_obj)
    elif method == 'POST':
        if not request.user:
            return require_signin(request)
        if request.params['action'] == 'add_note':
            _add_note(request, cruise_obj)
        if request.params['action'] == 'add_note_to_attr':
            _add_note_to_attr(request)
        if request.params['action'] == 'add_note_to_file':
            _add_note_to_file(request)

    history = []
    if cruise_obj:
        h.reduce_specificity(request, cruise_obj)
        if request.user:
            history = cruise_obj.notes
        else:
            history = cruise_obj.notes_public

        # Only show non-acknowledged suggestions to mods
        if h.has_mod(request):
            sugg_state = 'unjudged'
        else:
            sugg_state = 'pending'

        orderer = lambda change: change.order_by(Change.ts_c.desc())
        # Only non-data suggestions
        unjudged = cruise_obj.changes(
            sugg_state, data=False, query_modifier=orderer)
        suggested_attrs = [
            change for change in unjudged \
            if change.attr in Cruise.allowed_attrs_list]

        as_received = cruise_obj.changes(
            sugg_state, data=True, query_modifier=orderer)
        merged = cruise_obj.changes(
            'accepted', data=True, query_modifier=orderer)
        updates = {
            'attrs': suggested_attrs,
            'as_received': as_received,
            'merged': merged,
        }

    return {
        'cruise': cruise_obj,
        'data_files': h.collect_data_files(cruise_obj),
        'history': history,
        'updates': collapse_dict(updates, []) or {},
        'CRUISE_ATTRS_SELECT': cruise_attrs_select(),
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


def cruise_show_json(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    try:
        cruise_obj = Cruise.get_by_id(cruise_id)
    except ValueError:
        raise HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))
    return cruise_obj


def cruise_new(request):
    if not request.user:
        request.session.flash(PLEASE_SIGNIN_MESSAGE, 'help')
        request.referrer = request.url
        return require_signin(request)

    if http_method(request) == 'PUT':
        obj = _obj_new(request)
        return {'cruise_id': obj['obj']}

    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        cruise_id = ''
    return {'cruise_id': cruise_id}


def map_full(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    try:
        cruise_obj = Cruise.get_by_id(cruise_id)
    except ValueError:
        raise HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))

    data = cruise_obj.get('map_full', None)
    if not data:
        raise HTTPNotFound()
    return file_response(request, data)


def map_thumb(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    try:
        cruise_obj = Cruise.get_by_id(cruise_id)
    except ValueError:
        raise HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))
    a = cruise_obj.get('map_thumb', None)
    if not a:
        raise HTTPNotFound()
    return file_response(request, a)


def _cruise_to_json(cruise):
    obj = {
        'type': 'Cruise',
        'id': str(cruise.id),
        'obj_url': h.path_cruise(cruise), 
    }
    for attr_key, value in cruise._allowed_attrs_dict().items():
        v = cruise.get(attr_key)
        if v:
            if isinstance(v, FSFile):
                obj[attr_key] = v.id
            elif isinstance(v, list) or isinstance(v, _AssociationList):
                try:
                    obj[attr_key] = map(unicode, v)
                except TypeError:
                    obj[attr_key] = unicode(v)
            else:
                obj[attr_key] = unicode(v)

    track = cruise.track
    if track:
        obj['track'] = dict(geojson.mapping.to_mapping(track))
    return obj


def kml(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    try:
        cruise = Cruise.get_by_id(cruise_id)
    except ValueError:
        raise HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))

    kml = KML.kml()

    cruise_nice_name = h.cruise_nice_name(cruise)
    kmldoc = KML.Document(
        KML.name(cruise_nice_name),
        KML.description(request.route_url('cruise_show', cruise_id=cruise_id)),
    )
    kml.append(kmldoc)

    cruise_placemark = KML.Placemark(
        KML.name(cruise_nice_name),
    )
    cruise_description = etree.Element('description')
    cruise_description.text = etree.CDATA(h.cruise_summary(cruise))
    cruise_placemark.append(cruise_description)
    kmldoc.append(cruise_placemark)

    cruise_style = KML.Style(
        KML.IconStyle(
            KML.Icon(
                KML.href(request.static_url(
                    'pycchdo:static/cchdomap/images/cruise_start_icon.png')),
            )
        ),
        KML.LineStyle(
            KML.color('ff66ff66'),
            KML.width(5),
        ),
    )
    cruise_placemark.append(cruise_style)

    def str_if_exists(x, str):
        if x:
            return str
        return ''

    H = h.whh.HTML

    image_url = None
    if cruise.get('map_thumb'):
        image_url = request.route_path('cruise_map_thumb',
                                       cruise_id=cruise.uid)
    balloon_text = H(
        H.tag('h1', '$[name]'),
        str_if_exists(
            image_url,
            H.p(H.img(src='$[image]'), 
                  style='border: 1px solid black; border-left: 0; '
                        'border-right: 0;')),
        H.p('$[description]', style="max-width: 25em;"),
        str_if_exists(cruise.get('link'), H.p(h.whh.tags.link_to('$[website]'))),

        H.table(
            str_if_exists(cruise.get('ports'),
                          H.tr(H.td('Ports'), H.td('$[ports]'))),
            str_if_exists(cruise.date_start or cruise.date_end,
                          H.tr(H.td('Dates'), H.td('$[dates]'))),
            str_if_exists(cruise.country,
                          H.tr(H.td('Country'), H.td('$[country]'))),
            str_if_exists(cruise.ship, H.tr(H.td('Ship'), H.td('$[ship]'))),
            str_if_exists(cruise.collections,
                          H.tr(H.td('Collections'), H.td('$[collections]'))),
            str_if_exists(cruise.chief_scientists,
                          H.tr(H.td('Contacts'), H.td('$[contacts]'))),
            str_if_exists(cruise.institutions,
                          H.tr(H.td('Institutions'), H.td('$[institutions]'))),
        ),
    )
    cruise_style_balloon = KML.BalloonStyle(
        KML.textColor('ff000000'),
        KML.displayMode('default'),
    )
    cruise_style.append(cruise_style_balloon)

    cruise_style_balloon_text = etree.Element('text')
    cruise_style_balloon_text.text = etree.CDATA(balloon_text)
    cruise_style_balloon.append(cruise_style_balloon_text)

    cruise_edata = KML.ExtendedData()

    def append_data_if_exists(name, x):
        if x:
            data = KML.Data(name=name)
            value = etree.Element('value')
            value.text = etree.CDATA(unicode(x))
            data.append(value)
            cruise_edata.append(data)

    append_data_if_exists('image', image_url)
    append_data_if_exists('website', cruise.get('link'))
    ports = cruise.get('ports')
    if ports:
        append_data_if_exists('ports', h.ports_to_nice(ports, cruise))
    append_data_if_exists('dates', '/'.join(h.cruise_dates(cruise)[:2]))
    append_data_if_exists('country', h.link_country(cruise.country))
    append_data_if_exists('ship', h.link_ship(cruise.ship))
    if cruise.participants:
        pi_table = H()
        for part in list(cruise.participants):
            person = part.person
            inst = part.institution
            pi_table += H.tr(H.td(h.link_person(person)), H.td(part.role))
        table = H.table(
            H.tr(H.th('Person'), H.th('Role')),
            pi_table,
        )
        append_data_if_exists('contacts', table)
    append_data_if_exists(
        'collections',
        whtext.series([h.link_collection(c) for c in cruise.collections]))
    append_data_if_exists(
        'institutions',
        whtext.series([h.link_institution(i) for i in cruise.institutions]))
    cruise_placemark.append(cruise_edata)

    def shape_coords_to_kml_coords(coords):
        return ' '.join(
            [','.join(map(str, coord)) for coord in coords])

    track = cruise.track
    if track:
        centroid = track.centroid.coords[0]
        lookat = KML.LookAt(
            KML.longitude(centroid[0]),
            KML.latitude(centroid[1]),
            KML.altitude(0),
            KML.heading(0),
            KML.tilt(0),
            KML.range(9.6e6),
            KML.altitudeMode('relativeToGround'),
        )
        cruise_placemark.append(lookat)
        multigeom = KML.MultiGeometry(
            KML.Point(
                KML.coordinates(shape_coords_to_kml_coords([track.coords[0]]))
            ),
            KML.LineString(
                KML.tessellate(1),
                KML.coordinates(shape_coords_to_kml_coords(track.coords))
            ),
        )
        cruise_placemark.append(multigeom)
    else:
        lookat = KML.LookAt(
            KML.latitude(0),
            KML.longitude(0),
            KML.altitude(0),
            KML.heading(0),
            KML.tilt(0),
            KML.range(9.6e6),
            KML.altitudeMode('relativeToGround'),
        )
        cruise_placemark.append(lookat)
        point = KML.Point(
            KML.coordinates('0,0,0'),
        )
        cruise_placemark.append(point)

    response = Response(etree.tostring(kml, pretty_print=True))
    return response


def _contributions(request):
    pending_cruises = Cruise.query().filter(Cruise.accepted == False).all()
    def has_track(c):
        try:
            c.get_attr('track')
            return True
        except KeyError:
            return False
    pending_with_tracks = filter(has_track, pending_cruises)
    return [request.route_url('cruise_kml', cruise_id=c.uid)
            for c in pending_with_tracks]


def _contribution_kmzs(request):
    static_path = 'static/contrib'
    kmz_dir = request.registry.settings['contributed_kmls_path']
    return [request.route_url('catchall_static',
                              subpath=os.path.join(static_path, x)
                             ) for x in os.listdir(kmz_dir)]
