from datetime import datetime
from tempfile import SpooledTemporaryFile
from contextlib import contextmanager

import transaction

from pyramid.renderers import render_to_response
from pyramid.security import remember
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPUnauthorized, exception_response
    )

from pycchdo import helpers as h
from pycchdo.mail import send_submission_confirmation, get_email_addresses
from pycchdo.models.serial import (
    DBSession, FSFile, Submission, Note, RequestFor, store_context, Person
    )
from pycchdo.views.session import require_signin
from pycchdo.log import getLogger
from . import *


log = getLogger(__name__)


@contextmanager
def _generate_multiple_files_file(files):
    with SpooledTemporaryFile() as temp:
        with ZipFile(temp, 'w', compression=ZIP_DEFLATED) as zfile:
            for fff in files:
                zfile.writestr(fff.filename, fff.file.read())
        temp.seek(0)
        yield FSFile(temp, 'multiple_files.zip', 'application/zip')


def _create_submission(request, d):
    direct_name = request.params['name']
    direct_email = request.params['email']
    user = None
    if h.has_edit(request):
        user = request.user
        if (user.name != direct_name) or (user.email != direct_email):
            user = None
    if not user:
        direct_name = request.params['name']
        direct_email = request.params['email']
        person = Person.create().obj
        person.set_id_names(name=direct_name)
        person.email = direct_email
        pid = person.id
        transaction.commit()
        user = Person.query().get(pid)
        request.user = user
        
    sub = Submission.propose(user).obj

    if len(d['files']) > 1:
        with _generate_multiple_files_file(d['files']) as fsf:
            sub.value = fsf
    else:
        sub.value = FSFile.from_fieldstorage(d['files'][0])
    DBSession.flush()

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
    if d['notes']:
        sub.notes.append(Note(user, d['notes']))
    change = sub.change
    change.requests.append(RequestFor(request))

    return sub


def _get_form_input(request):
    d = {}
    d['name'] = request.params.get('name', '')
    d['institution'] = request.params.get('institution', '')
    d['country'] = request.params.get('country', '')
    d['email'] = request.params.get('email', '')

    d['identifier'] = request.params.get('identifier', '')
    d['woce_line'] = request.params.get('woce_line', '')
    d['ship'] = request.params.get('ship', '')
    try:
        d['cruise_dates'] = datetime.strptime(
            request.params.get('cruise_dates', ''), '%Y-%m-%d')
    except ValueError:
        d['cruise_dates'] = ''
    d['notes'] = request.params.get('notes', '')

    d['type_merge_data'] = request.params.get('type_merge_data', '')
    d['type_place_online'] = request.params.get('type_place_online', '')
    d['type_update_params'] = request.params.get('type_update_params', '')
    d['public_status'] = request.params.get('public', 'non_public')

    # Persist in session for form errors
    for k, v in d.items():
        h.form_entered(request, k, v)

    doomed = False
    if d['name'].strip() == "":
        request.session.flash('A name is required', 'form_error_name')
        doomed = True
    if d['email'].strip() == "":
        request.session.flash('An email is required', 'form_error_email')
        doomed = True
    if doomed:
        raise HTTPBadRequest()

    uploaded = [v for k, v in request.POST.items() if k.startswith('files[')]

    d['file_names'] = []
    d['files'] = []
    for fst in uploaded:
        try:
            d['file_names'].append(fst.filename)
            fst.file
        except AttributeError, err:
            log.debug(str(request))
            log.error(
                u'Submission has bad FieldStorage: {0!r} {1!r}'.format(
                fst, err))
            request.session.flash(
                'There was a problem with the files. Please contact '
                'the CCHDO for help.', 'form_error_files')
            raise HTTPBadRequest()
        d['files'].append(fst)
    h.form_entered(request, 'files', d['file_names'])

    if len(d['files']) < 1:
        log.debug(repr(request))
        log.error(u'No files submitted')
        request.session.flash(
            'At least one file must be selected', 'form_error_files')
        raise HTTPBadRequest()

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

    return d


def response_from_submission_request(request):
    d = _get_form_input(request)
    submission = _create_submission(request, d)
    send_submission_confirmation(request, d, submission)

    from_addr = get_email_addresses(request, 'from_address')[0]
    return {'from_addr': from_addr, 'files': d['files'], 'file_names':
         d['file_names'], 'submission': submission}


def submit(request):
    method = http_method(request)
    if method == 'GET':
        if h.has_edit(request):
            request.session.flash(request.user.name, 'form_entered_name')
            request.session.flash(request.user.email, 'form_entered_email')
        return {}
    elif method == 'POST':
        try:
            response = response_from_submission_request(request)
        except HTTPBadRequest:
            request.response.status = 400
            request.session.flash('Please correct the errors below', 'error')
            return {}
        response = render_to_response(
            'pycchdo:templates/submit_confirmation.jinja2',
            response, request=request)
        response.headerlist.extend(remember(request, str(request.user.id)))
        return response
    raise exception_response(405)

