import datetime
import logging

from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound

from webob.multidict import MultiDict

import pycchdo.models as models
import pycchdo.helpers as h

from . import *
from pycchdo.models.search import search
from pycchdo.models.models import data_file_human_names
from session import require_signin


CRUISE_ATTRS = MultiDict([
    ['Text', ['expocode', 'link']], 
    ['Datetime', ['date_start', 'date_end']], 
    ['Text List', ['aliases']],
    ['ID', ['ship', 'country']],
    ['ID List', ['collections']],
])


CRUISE_ATTRS_LIST = flatten(CRUISE_ATTRS.values())


CRUISE_ATTRS_HUMAN_NAMES = {
    'expocode': 'ExpoCode',
    'link': 'Expedition Link',
    'aliases': 'Aliases',
    'ship': 'Ship',
    'country': 'Country',
    'collections': 'Collections',
    'date_start': 'Start Date',
    'date_end': 'End Date',
}


CRUISE_ATTRS_SELECT = []
for k, v in CRUISE_ATTRS.items():
    CRUISE_ATTRS_SELECT.append(
        ([(x, CRUISE_ATTRS_HUMAN_NAMES[x]) for x in v], k))


FILE_GROUPS = MultiDict([
    ['Exchange', ['bottle_exchange', 'bottlezip_exchange', 'ctdzip_exchange']],
    ['NetCDF', ['bottlezip_netcdf', 'ctdzip_netcdf']],
    ['WOCE', ['bottle_woce', 'ctdzip_woce', 'sum_woce']],
    ['Map', ['map_thumb', 'map_full']],
    ['Documentation', ['doc_txt', 'doc_pdf']],
])


FILE_GROUPS_SELECT = []
for k, v in FILE_GROUPS.items():
    FILE_GROUPS_SELECT.append(
        ([(x, data_file_human_names[x]) for x in v], k))
FILE_GROUPS_SELECT.append('Other')


def cruises_index(request):
    return {'cruises': models.Cruise.map_mongo(models.Cruise.find())}


def _suggest_file(request, cruise_obj):
    try:
        type = request.params['type']
        if not type in models.data_file_descriptions.keys():
            logging.warn('Attempted to suggest file with improper type')
            request.response_status_int = 400
            request.session.flash(
                'Invalid file type %s. Please try again.' % type, 'help')
            request.session.flash(
                'File type must be one of %s' % \
                ', '.join(models.data_file_descriptions.keys()), 'help')
            return
    except KeyError:
        logging.warn('Attempted to suggest file without type')
        request.response_status = '400 Bad Request'
        request.session.flash(
            'Your file submission was missing a type. Please try again.',
            'help')
        return
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
    try:
        note = models.Note(request.user, request.params['notes'])
    except KeyError:
        note = None
    cruise_obj.set(type, file, request.user, note)


def _edit_attr(request, cruise_obj):
    try:
        key = request.params['key']
        if key not in CRUISE_ATTRS_LIST:
            logging.warn('Attempted to edit attribute with illegal key')
            request.response_status = '400 Bad Request'
            request.session.flash('The attribute key must be one of %r' % \
                                  sorted(CRUISE_ATTRS_LIST),
                                  'help')
            return
    except KeyError:
        logging.warn('Attempted to edit attribute without key')
        request.response_status = '400 Bad Request'
        request.session.flash('You must specify a key to edit', 'help')
        return
    try:
        value = request.params['value']
    except KeyError:
        logging.warn('Attempted to edit attribute without value')
        request.response_status = '400 Bad Request'
        request.session.flash('You did not give a value for the attribute.',
                              'help')
        return
    try:
        note = models.Note(request.user, request.params['notes'])
    except KeyError:
        note = None

    value_type = [k for k, v in CRUISE_ATTRS.iteritems() 
                  if key in v][0].lower().replace(' ', '_')
    value = text_to_obj(value, value_type)

    cruise_obj.set(key, value, request.user, note)
    request.session.flash('Suggested that %s should become %s' % (key, value),
                          'action_taken')


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


def cruise_show(request):
    try:
        cruise_id = request.matchdict['cruise_id']
    except KeyError:
        return HTTPBadRequest()
    cruise_obj = models.Cruise.get_id(cruise_id)

    # If the id is not an ObjectId, try searching based on ExpoCode
    if not cruise_obj:
        cruises = models.Cruise.get_by_attrs(expocode=cruise_id)
        if len(cruises) > 0:
            cruise_obj = cruises[0]
        else:
            return HTTPNotFound()

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
            if attr.key in CRUISE_ATTRS_LIST:
                suggested_attrs.append(attr)

        as_received = []
        for file in cruise_obj.pending_tracked_data():
            d = {
                'file': file,
                'date': file.creation_stamp.timestamp.strftime('%F'),
            }
            if request.user:
                d['notes'] = file.notes
            else:
                d['notes'] = file.notes_public
            as_received.append(d)
        merged = []
        for file in cruise_obj.accepted_tracked_merged_data():
            d = {
                'file': file,
                'date': file.judgment_stamp.timestamp.strftime('%F'),
            }
            if request.user:
                d['notes'] = file.notes
            else:
                d['notes'] = file.notes_public
            merged.append(d)
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

