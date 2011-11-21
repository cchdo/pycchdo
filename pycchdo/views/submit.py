from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPBadRequest, HTTPUnauthorized
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from pycchdo import models
from . import *


def submit(request):
    method = _http_method(request)
    if method == 'GET':
        if request.user or request.session.get('anonymous', False):
            return {}
        request.session.flash(
            'Please help us better process your data by leaving a way to '
            'contact you.', 'help')
        request.referrer = request.url
        return require_signin(request)
    elif method == 'POST':
#        if not request.user and not request.session.get('anonymous', False):
#            return HTTPUnauthorized()
#        name = request.params.get('name', None)
#        institution = request.params.get('institution', None)
#        country = request.params.get('country', None)
#        email = request.params.get('email', None)
#
#        identifier = request.params.get('identifier', None)
#        woce_line = request.params.get('woce_line', None)
#        ship = request.params.get('ship', None)
#        cruise_dates = request.params.get('cruise_dates', None)
#        notes = request.params.get('notes', None)
#
#        h.form_entered(request, 'identifier', identifier)
#        h.form_entered(request, 'woce_line', woce_line)
#        h.form_entered(request, 'ship', ship)
#        h.form_entered(request, 'cruise_dates', cruise_dates)
#        h.form_entered(request, 'notes', notes)
#
#        type_merge_data = request.params.get('type_merge_data', None)
#        type_place_online = request.params.get('type_place_online', None)
#        type_update_params = request.params.get('type_update_params', None)
#        type_argo = request.params.get('type_argo', None)
#        public = request.params.get('public', 'nonpublic')
#
#        h.form_entered(request, 'type_merge_data', type_merge_data)
#        h.form_entered(request, 'type_place_online', type_place_online)
#        h.form_entered(request, 'type_update_params', type_update_params)
#        h.form_entered(request, 'type_argo', type_argo)
#        h.form_entered(request, 'nonpublic', public == 'nonpublic')
#
#        files = []
#        file_keys = filter(lambda k: k.startswith('files'),
#                           request.POST.keys())
#
#        for fk in file_keys:
#            f = request.POST[fk]
#            try:
#                f.filename
#                f.file
#            except AttributeError:
#                continue
#            files.append(f)
#
#        h.form_entered(request, 'files', [file.filename for file in files])
#
#        action_list = []
#        if type_merge_data:
#            action_list.append('merge_data')
#        if type_place_online:
#            action_list.append('place_online')
#        if type_update_params:
#            action_list.append('update_params')
#        if type_argo:
#            action_list.append('argo')
#
#        user = request.user
#        if not user:
#            user = models.Person.get_one({'identifier': '_anonymous'})
#            if not user:
#                user = models.Person('_anonymous', 'Anonymous')
#                user.save()
#        for file in files:
#            s = models.Submission(user)
#            s.save()
#            s.set_accept('expocode', identifier)
#            s.set_accept('line', woce_line)
#            s.set_accept('ship_name', ship)
#            s.set_accept('cruise_date', cruise_dates)
#            s.set_accept('action', action_list)
#            s.set_accept('public', public)
#            s.add_note(models.Note(user, notes).save())
#            s.store_file(file)
#            # TODO record submitter useragent and ip
#        # TODO ensure safety of data records and notify users to email
#        # cberysgo@ucsd.edu in case of failure
#
#        mailer = get_mailer(request)
#        message = Message(
#            subject="[CCHDO] Submission by name: [line, expocode].join(' ')",
#            sender="cchdo@ucsd.edu",
#            recipients=["synmantics@gmail.com"],
#            body="""\
#Dear <%= @submission.name %>:
#
#Thank you for your submission to the CCHDO.
#
#This is an automated confirmation. However, replying to the sender will reach all senior CCHDO staff.
#
#<% submitted_files = submitted_file_names(@submission.file) -%>
#Your submitted <%= 'file'.smart_pluralize(submitted_files.length) %>:
#<%= submitted_files.join("\n") %>
#
#will be <%= @submission.public %>.
#
#The following actions were specified:
#<%= @submission.action %>
#
#Further information collected with your submission:
#Institute: <%= @submission.institute %>
#Country: <%= @submission.Country %>
#ExpoCode: <%= @submission.ExpoCode %> Line: <%= @submission.Line %>
#Date: <%= @submission.cruise_date %> 
#Notes: <%= @submission.notes %>
#
#Thank you again for your submission.
#"""
#        )
#        mailer.send(message)

        sample_submission = models.Submission(request.user)
        files = []

        return render_to_response(
            'pycchdo:templates/submit_confirmation.jinja2',
            {'files': files, 'submission': sample_submission}, request=request)
    return HTTPBadRequest()

