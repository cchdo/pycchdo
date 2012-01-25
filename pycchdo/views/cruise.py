import datetime
import logging

from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPSeeOther

from webob.multidict import MultiDict

import pycchdo.models as models
import pycchdo.helpers as h

from . import *
from pycchdo.models.search import search
from session import require_signin


def allowed_attrs_select(cls):
    sel = []
    for k, v in cls.allowed_attrs.items():
        sel.append(([(x, cls.allowed_attrs_human_names[x]) for x in v], k))
    return sel


CRUISE_ATTRS_SELECT = allowed_attrs_select(models.Cruise)


def cruises_index(request):
    seahunt = request.params.get('seahunt_only', False)
    if seahunt:
        cruises = models.Cruise.get_all({'accepted': False})
    else:
        cruises = models.Cruise.get_all()
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
                'The attribute key must be one of %r' % sorted(allowed_list),
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
        request.session.flash('You must specify what to do to the key', 'help')
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
        value = text_to_obj(value, value_type)

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
        # TODO collecting these takes a while
        cruise['date_start'], cruise['date_end'], cruise['cruise_dates'] = \
            h.cruise_dates(cruise_obj)
        cruise['link'] = cruise_obj.get('link')

        def getAttr(self, key):
            try:
                return self.get_attr(key)
            except KeyError:
                return None

        # TODO collecting the datafiles takes forever
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
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
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
    print a
    if not a:
        return HTTPNotFound()
    return _file_response(a.file)


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
    return _file_response(a.file)
