import datetime
import logging

from pyramid.httpexceptions import HTTPBadRequest

import pycchdo.models as models

from . import *
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
            request.session.flash('help',
                                  'Invalid file type. Please try again.')
            return
    except KeyError:
        logging.warn('Attempted to suggest file without type')
        request.response_status = '400 Bad Request'
        request.session.flash('help', 'Your file submission was missing '
                                      'a type. Please try again.')
        return
    try:
        file = request.params['file']
        if file == '':
            raise KeyError()
    except KeyError:
        logging.warn('Attempted to suggest file without file')
        request.response_status = '400 Bad Request'
        request.session.flash('help',
            'You did not select a file. Please try again.')
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
        request.session.flash('help',
            'Your note was missing parts. Please try again.')
        return

    try:
        public = request.params['public']
    except KeyError:
        public = False

    file_obj = models._Attr.get_id(file_id)
    if not file_obj:
        request.response_status = '404 Not Found'
        request.session.flash('help',
            'The file you tried to add a note to could not be found.')
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
        request.session.flash('help', 'Your note was missing parts. Please '
                                      'try again.')
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
        # TODO
        pass

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
    history = []
    if cruise_obj:
        # TODO collecting these takes a while
        cruise['collections'] = ', '.join(flatten(
            [c.names for c in cruise_obj.collections()]))
        cruise['date_start'] = cruise_obj.date_start()
        cruise['date_end'] = cruise_obj.date_end()
        if cruise['date_start'] and cruise['date_end']:
            cruise['cruise_dates'] = '/'.join(map(str, (cruise['date_start'],
                                                        cruise['date_end'])))
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
        }
        data_files['netcdf'] = {
            'ctdzip_netcdf': getAttr(cruise_obj, 'ctdzip_netcdf'),
            'bottlezip_netcdf': getAttr(cruise_obj, 'bottlezip_netcdf'),
        }
        data_files['woce'] = {
            'sum_woce': getAttr(cruise_obj, 'sum_woce'),
            'bottle_woce': getAttr(cruise_obj, 'bottle_woce'),
            'ctdzip_woce': getAttr(cruise_obj, 'ctdzip_woce'),
        }
        data_files['large_volume'] = {
        }
        data_files['trace_metals'] = {
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

