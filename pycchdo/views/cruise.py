import datetime
import logging
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

import pycchdo.models as models
import pycchdo.helpers as h

from . import *
from session import require_signin


def allowed_attrs_select(cls):
    sel = []
    for k, v in cls.allowed_attrs.items():
        sel.append(([(x, cls.allowed_attrs_human_names[x]) for x in v], k))
    return sel


CRUISE_ATTRS_SELECT = allowed_attrs_select(models.Cruise)


def cruises_index(request):
    seahunt = request.params.get('seahunt_only', False)
    allow_seahunt = request.params.get('allow_seahunt', False)
    if seahunt:
        cruises = models.Cruise.get_all({'accepted': False})
    elif allow_seahunt:
        cruises = models.Cruise.get_all()
    else:
        cruises = models.Cruise.get_all({'accepted': True})
    cruises = sorted(cruises, key=lambda c: c.expocode or c.id)
    cruises = _paged(request, cruises)
    return {'cruises': cruises}


def _suggest_file(request, cruise_obj):
    try:
        type = request.params['type']
        if not type in models.data_file_descriptions.keys():
            logging.warn('Attempted to suggest file with improper type')
            request.response_status_int = 400
            request.session.flash(
                'Invalid file type %s.' % type, 'help')
            request.session.flash(
                'File type must be one of %s' % \
                ', '.join(models.data_file_descriptions.keys()), 'help')
            return
    except KeyError:
        logging.warn('Attempted to suggest file without type')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your file submission was missing a type.', 'help')
        return
    try:
        note = models.Note(request.user, request.params['notes'])
    except KeyError:
        note = None

    try:
        add_file_action = request.params['add_file_action']
    except KeyError:
        logging.warn('Attempted to modify file without action')
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
            logging.warn('Attempted to suggest file without file')
            request.response_status = '400 Bad Request'
            request.session.flash(
                'You did not select a file. Please try again.', 'help')
            return
        cruise_obj.set(type, file, request.user, note)
    elif add_file_action == 'Delete file':
        cruise_obj.delete(type, request.user, note)


def _edit_attr(request, cruise_obj):
    try:
        key = request.params['key']
        # Allow any Cruise attrs in addition to file_type_status attrs
        allowed_list = models.Cruise.allowed_attrs_list + \
            ['%s_status' % x for x in models.data_file_descriptions.keys()]
        if key not in allowed_list:
            logging.warn('Attempted to edit attribute with illegal key')
            request.response_status = '400 Bad Request'
            request.session.flash(
                'The attribute key must be one of %s.' % \
                ', '.join(sorted(allowed_list)),
                'help')
            return
    except KeyError:
        logging.warn('Attempted to edit attribute without key')
        request.response_status = '400 Bad Request'
        request.session.flash('You must specify a key to edit', 'help')
        return
    try:
        edit_action = request.params['edit_action']
    except KeyError:
        logging.warn('Attempted to edit attribute without a specified action')
        request.response_status = '400 Bad Request'
        request.session.flash('You must specify what to do to %s' % key, 'help')
        return

    try:
        note = models.Note(request.user, request.params['notes'])
    except KeyError:
        note = None

    if edit_action == 'Set':
        try:
            value = request.params['value']
        except KeyError:
            logging.warn('Attempted to edit attribute without value')
            request.response_status = '400 Bad Request'
            request.session.flash(
                'You did not give a value for the attribute.', 'help')
            return

        value_type = models.Cruise.attr_type(key)
        try:
            value = text_to_obj(value, value_type)
        except ValueError:
            request.response_status = '400 Bad Request'
            request.session.flash('Bad value for attribute %s' % key, 'help')
            return

        cruise_obj.set(key, value, request.user, note)
        request.session.flash(
            'Suggested that %s should become %s' % (key, value), 'action_taken')
    elif edit_action == 'Delete':
        cruise_obj.delete(key, request.user, note)
        request.session.flash(
            'Suggested that %s be deleted' % key, 'action_taken')
    elif edit_action == 'Mark reviewed':
        # Remove a cruise file type's preliminary status
        if not h.has_mod(request):
            request.response.status = '403 Forbidden'
            request.session.flash(
                'You must be a moderator to mark files as reviewed', 'help')
            return
        status = cruise_obj.get(key)
        try:
            status = status.remove(u'preliminary')
            cruise_obj.set_accept(key, status, request.user)
            request.session.flash(
                'Marked %s for %s as reviewed' % (key.replace('_status', ''),
                                                  cruise_obj.expocode),
                'action_taken')
        except ValueError:
            request.session.flash(
                '%s for %s is already marked reviewed' % (
                    key.replace('_status', ''), cruise_obj.expocode),
                'help')
    elif edit_action == 'Set participants':
        if key == 'participants':
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

            failed = False
            new_rpis = []
            for i, rpi in sorted(rpis.items()):
                if rpi['role'] or rpi['person'] or rpi['institution']:
                    if rpi['person']:
                        person_id = rpi['person']
                        try:
                            person = models.Person.get_id(person_id)
                            if not person:
                                failed = True
                                request.session.flash(
                                    'Person %s does not exist' % person_id,
                                    'help')
                                continue
                            rpi['person'] = person.id
                        except ValueError:
                            failed = True
                            request.session.flash(
                                'Invalid person id %s' % person_id, 'help')
                    if rpi['institution']:
                        institution_id = rpi['institution']
                        try:
                            institution = models.Institution.get_id(
                                institution_id)
                            if not institution:
                                failed = True
                                request.session.flash(
                                    'Institution %s does not exist' % \
                                    institution_id, 'help')
                                continue
                            rpi['institution'] = institution.id
                        except ValueError:
                            failed = True
                            request.session.flash(
                                'Invalid institution id %s' % institution_id, 'help')
                    new_rpis.append(rpi)

            if failed:
                return
            cruise_obj.set('participants', new_rpis, request.user, note)
            request.session.flash('Suggested updated participants for this cruise',
                                  'action_taken')
        else:
            request.session.flash('Invalid action to take on %s' % key, 'help')
    elif edit_action == 'Delete all participants':
        if key == 'participants':
            cruise_obj.delete('participants', request.user, note)
            request.session.flash('Suggested that participants be cleared',
                                  'action_taken')
        else:
            request.session.flash('Invalid action to take on %s' % key, 'help')
    else:
        request.session.flash('Unknown edit action: %s' % edit_action, 'help')


def _add_note_to_attr(request):
    try:
        attr_id = request.params['attr_id']
        note = request.params['note']
    except KeyError:
        logging.warn('Attempted to add note with missing attributes')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your note was missing an id or the note body. Please try again.',
            'help')
        return

    try:
        public = request.params['public']
    except KeyError:
        public = False

    attr_obj = models._Attr.get_id(attr_id)
    if not attr_obj:
        request.response_status = '404 Not Found'
        request.session.flash(
            'The attribute you tried to add a note to could not be found.', 'help')
        return

    attr_obj.add_note(models.Note(request.user, note, discussion=not public))


def _add_note_to_file(request):
    try:
        file_id = request.params['file_id']
        note = request.params['note']
    except KeyError:
        logging.warn('Attempted to add note with missing attributes')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your note was missing parts. Please try again.', 'help')
        return

    try:
        public = request.params['public']
    except KeyError:
        public = False

    file_obj = models._Attr.get_id(file_id)
    if not file_obj:
        request.response_status = '404 Not Found'
        request.session.flash(
            'The file you tried to add a note to could not be found.', 'help')
        return

    file_obj.add_note(models.Note(request.user, note, discussion=not public))


def _add_note(request, cruise_obj):
    try:
        data_type = request.params['note_data_type']
        action = request.params['note_action']
        summary = request.params['note_summary']
        note = request.params['note_note']
    except KeyError:
        logging.warn('Attempted to add note with missing attributes')
        request.response_status = '400 Bad Request'
        request.session.flash('Your note was missing parts. Please try again.',
                              'help')
        return

    try:
        public = request.params['note_discussion']
    except KeyError:
        public = False

    cruise_obj.add_note(models.Note(request.user, note, action, data_type,
                                    summary, not public))


def _get_cruise(cruise_id):
    try:
        cruise_obj = models.Cruise.get_id(cruise_id)
    except ValueError:
        cruise_obj = None

    # If the id is not an ObjectId, try searching based on ExpoCode
    if not cruise_obj:
        cruises = models.Cruise.get_by_attrs(expocode=cruise_id)
        if len(cruises) > 0:
            cruise_obj = cruises[0]
        else:
            raise ValueError()
    return cruise_obj


def cruise_show(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
    try:
        cruise_obj = _get_cruise(cruise_id)
    except ValueError:
        return HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))

    method = _http_method(request)

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

    cruise = {}
    data_files = {}
    history = []
    if cruise_obj:
        cruise['date_start'], cruise['date_end'], cruise['cruise_dates'] = \
            h.cruise_dates(cruise_obj)
        cruise['link'] = cruise_obj.get('link')

        def getAttr(self, key):
            try:
                return self.get_attr(key)
            except KeyError:
                return None

        data_files = {}
        data_files['map'] = {
            'full': getAttr(cruise_obj, 'map_full'),
            'thumb': getAttr(cruise_obj, 'map_thumb'),
        }
        data_files['exchange'] = {
            'ctdzip_exchange': getAttr(cruise_obj, 'ctdzip_exchange'),
            'bottle_exchange': getAttr(cruise_obj, 'bottle_exchange'),
            'large_volume_samples_exchange': getAttr(
                cruise_obj, 'large_volume_samples_exchange'),
            'trace_metals_exchange': getAttr(
                cruise_obj, 'trace_metals_woce'),
        }
        data_files['netcdf'] = {
            'ctdzip_netcdf': getAttr(cruise_obj, 'ctdzip_netcdf'),
            'bottlezip_netcdf': getAttr(cruise_obj, 'bottlezip_netcdf'),
        }
        data_files['woce'] = {
            'bottle_woce': getAttr(cruise_obj, 'bottle_woce'),
            'ctdzip_woce': getAttr(cruise_obj, 'ctdzip_woce'),
            'sum_woce': getAttr(cruise_obj, 'sum_woce'),
            'large_volume_samples_woce': getAttr(
                cruise_obj, 'large_volume_samples_woce'),
        }
        data_files['doc'] = {
            'doc_txt': getAttr(cruise_obj, 'doc_txt'),
            'doc_pdf': getAttr(cruise_obj, 'doc_pdf'),
        }

        if request.user:
            history = cruise_obj.notes
        else:
            history = cruise_obj.notes_public

        unjudged = cruise_obj.unjudged_tracked()
        suggested_attrs = []
        for attr in unjudged:
            if attr.key in models.Cruise.allowed_attrs_list:
                suggested_attrs.append(attr)

        if h.has_mod(request):
            # Only show unacknowledged suggestions to mods
            as_received = cruise_obj.unjudged_tracked_data()
        else:
            as_received = cruise_obj.pending_tracked_data()
        merged = cruise_obj.accepted_tracked_data()
        updates = {
            'attrs': suggested_attrs,
            'as_received': as_received,
            'merged': merged,
        }

    return {
        'cruise': cruise_obj,
        'cruise_dict': cruise,
        'data_files': _collapsed_dict(data_files) or {},
        'history': history,
        'updates': _collapsed_dict(updates, []) or {},
        'CRUISE_ATTRS_SELECT': CRUISE_ATTRS_SELECT,
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


def cruise_new(request):
    if not request.user:
        request.session.flash(PLEASE_SIGNIN_MESSAGE, 'help')
        request.referrer = request.url
        return require_signin(request)
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        cruise_id = ''
    return {'cruise_id': cruise_id}


def map_full(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
    try:
        cruise_obj = _get_cruise(cruise_id)
    except ValueError:
        return HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))

    a = cruise_obj.get_attr('map_full')
    if not a:
        return HTTPNotFound()
    return _file_response(request, a.file)


def map_thumb(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
    try:
        cruise_obj = _get_cruise(cruise_id)
    except ValueError:
        return HTTPSeeOther(
            location=request.route_path('cruise_new', cruise_id=cruise_id))
    a = cruise_obj.get_attr('map_thumb')
    if not a:
        return HTTPNotFound()
    return _file_response(request, a.file)


def _cruise_to_json(cruise):
    obj = {
        'type': 'Cruise',
        'id': str(cruise.id),
        'obj_url': h.path_cruise(cruise), 
    }
    for attr_key in cruise.allowed_attrs_list:
        v = cruise.__getattr__(attr_key)
        if v:
            if type(v) is not list:
                obj[attr_key] = str(v)
            else:
                obj[attr_key] = map(str, v)

    track = cruise.track
    if track:
        obj['track'] = dict(geojson.mapping.to_mapping(track))
    return obj


def kml(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
    try:
        cruise = _get_cruise(cruise_id)
    except ValueError:
        return HTTPSeeOther(
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
        str_if_exists(cruise.link, H.p(h.whh.tags.link_to('$[website]'))),

        H.table(
            str_if_exists(cruise.ports,
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
    append_data_if_exists('website', cruise.link)
    if cruise.ports:
        append_data_if_exists('ports', ' to '.join(cruise.ports))
    append_data_if_exists('dates', '/'.join(h.cruise_dates(cruise)[:2]))
    append_data_if_exists('country', h.link_country(cruise.country))
    append_data_if_exists('ship', h.link_ship(cruise.ship))
    if cruise.participants:
        pi_table = H()
        for role, pis in cruise.participants.items():
            for pi in pis:
                person = pi['person']
                inst = pi['institution']
                pi_table += H.tr(H.td(h.link_person(person)), H.td(role))
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
    pending_cruises = models.Cruise.get_all({'accepted': False})
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
    kmz_dir = AssetResolver('pycchdo').resolve(
        static_path).abspath()
    return [request.route_url('catchall_static',
                              subpath=os.path.join(static_path, x)
                             ) for x in os.listdir(kmz_dir)]


def json(request):
    if request.params.get('pending_years'):
        return models.Cruise.pending_years()
    elif request.params.get('id'):
        id = request.params.get('id')
        try:
            cruise = _get_cruise(id)
        except ValueError:
            return HTTPBadRequest()
        return _cruise_to_json(cruise)
    elif request.params.get('ids'):
        ids = [x.strip() for x in request.params.get('ids').split(',')]
        try:
            cruises = [_get_cruise(cruise_id) for cruise_id in ids]
        except ValueError:
            return HTTPBadRequest()
        return [_cruise_to_json(cruise) for cruise in cruises]
    elif request.params.get('contributions'):
        return _contributions(request)
    elif request.params.get('contribution_kmzs'):
        return _contribution_kmzs(request)
    return HTTPBadRequest()
