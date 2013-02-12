from datetime import datetime

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPBadRequest, HTTPUnauthorized
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from pycchdo import models
from pycchdo import helpers as h
from pycchdo.models import DBSession, FSFile
from pycchdo.views.session import require_signin
from pycchdo.log import ColoredLogger
from . import *


log = ColoredLogger(__name__)


def _send_confirmation(request, d):
    recipient = request.registry.settings.get(
        'submission_confirmation_recipient')
    recipients = [request.user.email, recipient]

    d['user_name'] = request.user.name
    d['file_noun'] = h.whtext.plural(
        len(d['file_names']), 'file', 'files', False)

    if d['public_status'] == 'public':
        d['public_description'] = 'will be public.'
    elif d['public_status'] == 'non_public':
        d['public_description'] = 'will *not* be public.'
    elif d['public_status'] == 'non_public_argo':
        d['public_description'] = \
            'will be available for use exclusively by the Argo program.'
    d['file_list'] = '\n'.join(d['file_names'])
    d['actions'] = '\n'.join(d['action_list'])

    body_parts = []
    body = """\
Dear {user_name}:

Thank you for your submission to the CCHDO.

This is an automated confirmation. However, replying to the sender will reach 
all senior CCHDO staff.

Your submitted {file_noun}:
{file_list}

{public_description}.

The following actions were specified:
{actions}

Additional information collected with your submission:
""".format(d)
    if d['institution']:
        body_parts.append('Institution: ' + d['institution'])
    if d['country']:
        body_parts.append('Country: ' + d['country'])
    if d['identifier'] or d['woce_line']:
        parts = []
        if d['identifier']:
            parts.append('ExpoCode: ' + d['identifier'])
        if d['woce_line']:
            parts.append('Line: ' + d['woce_line'])
        body_parts.append(' '.join(parts))
    if d['ship']:
        body_parts.append('Ship: ' + d['ship'])
    if d['cruise_dates']:
        body_parts.append(
            'Dates: ' + datetime.strftime(d['cruise_dates'], '%Y-%m-%d'))
    if d['notes']:
        body_parts.append('Notes: ' + d['notes'])
    body_parts.append('\nThank you again for your submission.')

    body += '\n'.join(body_parts)

    message = Message(
        subject="[CCHDO] Submission by {name}: {id}".format(
            name=d['user_name'],
            id=' '.join([d['woce_line'], d['identifier']])),
        sender=cchdo_email,
        recipients=recipients,
        body=body,
    )
    mailer = get_mailer(request)
    mailer.send(message)


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
        # Create one submission per file with duplicated information
        for file in files:
            sub = models.Submission(user)
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
                sub.action = repr(d['action_list'])
            if d['public_status']:
                sub.type = d['public_status']
            sub.file = FSFile.from_fieldstorage(file)
            if d['notes']:
                sub.notes.append(models.Note(user, d['notes']))
            DBSession.flush()
            submissions.append(sub)
            # TODO record submitter useragent and ip

        _send_confirmation(request, d)

        sample_submission = submissions[0]
        return render_to_response(
            'pycchdo:templates/submit_confirmation.jinja2',
            {'files': files, 'file_names': d['file_names'],
             'submission': sample_submission}, request=request)
    raise HTTPBadRequest()

