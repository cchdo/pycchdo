import datetime

from pyramid.httpexceptions import HTTPSeeOther, HTTPBadRequest, HTTPNotFound

import pycchdo.models as models

from . import *
from session import require_signin


def index(request):
    """ List of the repository

    If details is set to anything and the current user is an admin_argo, also
    display download logs.
    
    """
    details = request.params.get('details', False)
    method = http_method(request)

    if method == 'POST':
        return _create(request)
    elif method == 'GET':
        all_argo_files = models.ArgoFile.all()
        argo_files = models.ArgoFile.map_mongo(all_argo_files)
        return {'argo_files': argo_files}


def new(request):
    """ Form for new file """
    return {}


def entity(request):
    id = request.matchdict['id']
    argo_file = models.ArgoFile.get_id(id)
    if not argo_file:
        raise HTTPNotFound()

    method =  http_method(request)
    if method == 'PUT':
        expocode = request.params.get('expocode', '')
        display = request.params.get('display', False)
        description = request.params.get('description', '')

        argo_file.text_identifier = expocode
        argo_file.display = bool(display)
        argo_file.description = description

        raise HTTPSeeOther(location='/argo')
    elif method == 'DELETE':
        argo_file.remove()
        raise HTTPSeeOther(location=request.referrer)
    return {'argo_file': argo_file}


def _create(request):
    if not request.user:
        return require_signin(request)

    expocode = request.params.get('expocode', '')
    date = request.params.get('date', '')
    ship = request.params.get('ship', '')
    display = request.params.get('display', False)
    description = request.params.get('description', '')
    file = request.params.get('file', None)

    request.session.flash(expocode, 'form_entered_argo_expocode')
    request.session.flash(date, 'form_entered_argo_date')
    request.session.flash(ship, 'form_entered_argo_ship')
    request.session.flash(display, 'form_entered_argo_display')
    request.session.flash(description, 'form_entered_argo_description')

    if file is None or file == '':
        request.session.flash('A file to upload is required', 'form_error_argo_file')
        raise HTTPSeeOther(location=request.referrer)

    if not expocode:
        text_id = '%s_%s' % (ship, date)
    else:
        text_id = expocode

    argo_file = models.ArgoFile(request.user)
    argo_file.text_identifier = text_id
    argo_file.description = description
    argo_file.display = bool(display)
    argo_file.store(file)
    argo_file.save()

    request.session.pop_flash('form_entered_argo_expocode')
    request.session.pop_flash('form_entered_argo_date')
    request.session.pop_flash('form_entered_argo_ship')
    request.session.pop_flash('form_entered_argo_display')
    request.session.pop_flash('form_entered_argo_description')

    request.session.flash('Added Argo file to Argo secure file repository.', 'action_taken')
    raise HTTPSeeOther(location='/argo')
