import datetime
import logging

from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound

import pycchdo.models as models
import pycchdo.helpers as h

from . import *
from ..models.search import search
from session import require_signin


def flatten(l):
    return [item for sublist in l for item in sublist]


def cruises_index(request):
    return {'cruises': models.Cruise.map_mongo(models.Cruise.find())}


def _suggest_file(request, cruise_obj):
    try:
        type = request.params['type']
        if not type in models.data_file_descriptions.keys():
            logging.warn('Attempted to suggest file with improper type')
            request.response_status_int = 400
            request.session.flash(
                'Invalid file type. Please try again.', 'help')
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
    cruise_obj.set(type, file, request.user)


def _add_note_to_file(request):
    print 'hello. adding note to file'
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
            return HTTPBadRequest()

    method = _http_method(request)

    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        if request.params['action'] == 'suggest_file':
            _suggest_file(request, cruise_obj)
    elif method == 'POST':
        if not request.user:
            return require_signin(request)
        if request.params['action'] == 'add_note':
            _add_note(request, cruise_obj)
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

        def getAttr(cruise_obj, type):
            id = None
            for c in cruise_obj.accepted_tracked():
                if c['key'] == type:
                    id = c['_id']
            return models._Attr.get_id(id)

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

        # TODO also list attr history?
        if request.user:
            history = cruise_obj.notes
        else:
            history = cruise_obj.notes_public

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
            'as_received': as_received,
            'merged': merged,
        }

    return {
        'cruise': cruise_obj,
        'cruise_dict': cruise,
        'data_files': _collapsed_dict(data_files) or {},
        'history': history,
        'updates': updates,
        }

