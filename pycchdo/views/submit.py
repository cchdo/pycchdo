from datetime import datetime

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPBadRequest, HTTPUnauthorized

from pycchdo import helpers as h
from pycchdo.mail import send_submission_confirmation
from pycchdo.models.serial import DBSession, FSFile, Submission, Note
from pycchdo.views.session import require_signin
from pycchdo.log import getLogger
from . import *


log = getLogger(__name__)


def submit(request):
    method = http_method(request)
    if method == 'GET':
        if h.has_edit(request):
            return {}
        request.session.flash(PLEASE_SIGNIN_MESSAGE, 'help')
        request.referrer = request.url
        return require_signin(request)
    elif method == 'POST':
        if not h.has_edit(request):
            raise HTTPUnauthorized()

        d = {}
        d['name'] = request.params.get('name', None)
        d['institution'] = request.params.get('institution', None)
        d['country'] = request.params.get('country', None)
        d['email'] = request.params.get('email', None)

        d['identifier'] = request.params.get('identifier', None)
        d['woce_line'] = request.params.get('woce_line', None)
        d['ship'] = request.params.get('ship', None)
        try:
            d['cruise_dates'] = datetime.strptime(
                request.params.get('cruise_dates', ''), '%Y-%m-%d')
        except ValueError:
            d['cruise_dates'] = None
        d['notes'] = request.params.get('notes', None)

        d['type_merge_data'] = request.params.get('type_merge_data', None)
        d['type_place_online'] = request.params.get('type_place_online', None)
        d['type_update_params'] = request.params.get('type_update_params', None)
        d['public_status'] = request.params.get('public', 'nonpublic')

        # Persist in session for form errors
        for k, v in d.items():
            h.form_entered(request, k, v)

        uploaded = [v for k, v in request.POST.items() if k.startswith('files')]

        d['file_names'] = []
        files = []
        for f in uploaded:
            try:
                d['file_names'].append(f.filename)
                f.file
            except AttributeError:
                # TODO handle if files don't have names...shouldn't be possible?
                continue
            files.append(f)
        h.form_entered(request, 'files', d['file_names'])

        if len(files) < 1:
            request.response.status = 400
            request.session.flash(
                'You must submit at least one file', 'form_error_files')
            return {}

        action_list = []
        if d['type_merge_data']:
            action_list.append('merge_data')
        if d['type_place_online']:
            action_list.append('place_online')
        if d['type_update_params']:
            action_list.append('update_params')
        if d['public_status'] == 'nonpublic_argo':
            action_list.append('argo')
        d['action_list'] = action_list

        user = request.user
        submissions = []

        # TODO create one bulk one
        # Create one submission per file with duplicated information
        for file in files:
            sub = Submission(user)
            DBSession.add(sub)
            if d['identifier']:
                sub.expocode = d['identifier']
            if d['woce_line']:
                sub.line = d['woce_line']
            if d['ship']:
                sub.ship_name = d['ship']
            if d['cruise_dates']:
                sub.cruise_date = d['cruise_dates']
            if d['action_list']:
                sub.action = ', '.join(d['action_list'])
            if d['public_status']:
                sub.type = d['public_status']
            sub.value = FSFile.from_fieldstorage(file)
            if d['notes']:
                sub.notes.append(Note(user, d['notes']))
            DBSession.flush()
            submissions.append(sub)
            # TODO record submitter useragent and ip

        send_submission_confirmation(request, d, submissions)

        sample_submission = submissions[0]
        return render_to_response(
            'pycchdo:templates/submit_confirmation.jinja2',
            {'from_addr': from_addr, 'files': files, 'file_names':
             d['file_names'], 'submission': sample_submission}, request=request)
    raise HTTPBadRequest()

