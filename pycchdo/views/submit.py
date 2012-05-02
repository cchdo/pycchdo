from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPBadRequest, HTTPUnauthorized
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from pycchdo import models
from pycchdo import helpers as h
from pycchdo.views.session import require_signin
from . import *


def _send_confirmation(request, d):
        cchdo_email = 'cchdo@ucsd.edu'
        recipients = [
            request.registry.settings.get('submission_confirmation_recipient',
                                          request.user.email), cchdo_email]

        d['user_name'] = request.user.full_name()
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
        # TODO

        body_parts = []
        body = """\
Dear %(name)s:

Thank you for your submission to the CCHDO.

This is an automated confirmation. However, replying to the sender will reach 
all senior CCHDO staff.

Your submitted %(file_noun)s:
%(file_list)s

%(public_description)s.

The following actions were specified:
%(actions)s

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
            body_parts.append('Dates: ' + d['cruise_dates'])
        if d['notes']:
            body_parts.append('Notes: ' + d['notes'])
        body_parts.append('\nThank you again for your submission.')
        body = '\n'.join(body_parts)

        message = Message(
            subject="[CCHDO] Submission by %(name)s: %(id)s".format(
                name=d['user_name'],
                id=' '.join([d['woce_line'], d['identifier']])),
            sender=cchdo_email,
            recipients=recipients,
            body=body,
        )
        # XXX actually send the message!
        print str(message)
        #mailer = get_mailer(request)
        #mailer.send(message)


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
        d['cruise_dates'] = request.params.get('cruise_dates', None)
        d['notes'] = request.params.get('notes', None)

        d['type_merge_data'] = request.params.get('type_merge_data', None)
        d['type_place_online'] = request.params.get('type_place_online', None)
        d['type_update_params'] = request.params.get('type_update_params', None)
        d['public_status'] = request.params.get('public', 'nonpublic')

        # Persist in session for form errors
        for k, v in d.items():
            h.form_entered(request, k, v)

        files = []
        file_keys = filter(lambda k: k.startswith('files'),
                           request.POST.keys())

        for fk in file_keys:
            f = request.POST[fk]
            try:
                f.filename
                f.file
            except AttributeError:
                # TODO handle if files don't have names...shouldn't be possible?
                continue
            files.append(f)

        d['file_names'] = [file.filename for file in files]
        h.form_entered(request, 'files', d['file_names'])

        if len(files) < 1:
            request.response.status = 400
            request.session.flash('You must submit at least one file',
                                  'form_error_files')
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
        for file in files:
            s = models.Submission(user)
        #    s.save()
        #    s.set_accept('expocode', d['identifier'], user)
        #    s.set_accept('line', d['woce_line'], user)
        #    s.set_accept('ship_name', d['ship'], user)
        #    s.set_accept('cruise_date', d['cruise_dates'], user)
        #    s.set_accept('action', d['action_list'], user)
        #    s.set_accept('public', d['public'] == 'public', user)
        #    s.add_note(models.Note(user, d['notes']).save())
        #    s.store_file(file)
            submissions.append(s)
            # TODO record submitter useragent and ip

        # TODO ensure safety of data records and notify users to email
        # cberysgo@ucsd.edu in case of failure

        _send_confirmation(request, d)

        sample_submission = submissions[0]
        return render_to_response(
            'pycchdo:templates/submit_confirmation.jinja2',
            {'files': files, 'file_names': d['file_names'],
             'submission': sample_submission}, request=request)
    raise HTTPBadRequest()

