import transaction

from pyramid.httpexceptions import HTTPUnauthorized, HTTPSeeOther, HTTPNotFound

from . import *
from pycchdo.helpers import has_argo, has_staff
from pycchdo.util import timestamp_now
from pycchdo.models.serial import (
    DBSession, ArgoFile, Change, RequestFor, FSFile,
    )
from pycchdo.views.session import signin_required, require_signin


def _check_signin_argo(request):
    if request.user is None:
        request.session.flash(u'Please sign in to view Argo SFR', 'help')
        return require_signin(request)
    if not has_argo(request):
        request.session.flash(
            (u'You are not authorized to view the Argo SFR. '
             'Please contact the CCHDO to request permissions.'), 'error')
        raise HTTPUnauthorized()
    return None


def _check_signin_argo_staff(request):
    if not _check_signin_argo(request):
        if not has_staff(request):
            request.session.flash(
                (u'You are not authorized to edit the Argo SFR. '
                 'Please contact the CCHDO to request permissions.'), 'error')
            raise HTTPUnauthorized()
    return None


def signin_required_argo(view_callable):
    return signin_required(_check_signin_argo)(view_callable)


def signin_required_argo_staff(view_callable):
    return signin_required(_check_signin_argo_staff)(view_callable)


@signin_required_argo
def index(request):
    """List of the repository
    
    """
    method = http_method(request)

    if method == 'POST':
        return _create(request)
    elif method == 'GET':
        argo_files = ArgoFile.query().join(ArgoFile._changes).\
            order_by(Change.ts_c.asc())
        if not has_staff(request):
            argo_files = argo_files.filter(ArgoFile.display)
        argo_files = argo_files.all()
        return {'argo_files': argo_files}


@signin_required_argo
def file(request):
    """Return the file."""
    id = request.matchdict['id']
    af = ArgoFile.query().get(id)
    if not af:
        raise HTTPNotFound()

    request.date = timestamp_now()
    af.requests_for.append(RequestFor(request))
    transaction.commit()

    transaction.begin()
    af = ArgoFile.query().get(id)
    return file_response(request, af.value)


@signin_required_argo
def new(request):
    """Form for new file."""
    return {}


def entity(request):
    """Update an ArgoFile."""
    id = request.matchdict['id']
    argo_file = ArgoFile.query().get(id)
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
        transaction.commit()
        request.session.flash(u'Saved changes to Argo file.', 'action_taken')
        raise HTTPSeeOther(location='/argo.html')
    elif method == 'DELETE':
        DBSession.delete(argo_file)
        transaction.commit()
        request.session.flash(u'Deleted Argo file.', 'action_taken')
        raise HTTPSeeOther(location=request.referrer)
    return {'argo_file': argo_file}


def _create(request):
    _check_signin_argo_staff(request)

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
        request.session.flash(
            'A file to upload is required', 'form_error_argo_file')
        raise HTTPSeeOther(location=request.referrer)

    if not expocode:
        text_id = '%s_%s' % (ship, date)
    else:
        text_id = expocode

    argo_file = ArgoFile(request.user)
    argo_file.text_identifier = text_id
    argo_file.description = description
    argo_file.display = bool(display)
    argo_file.file = FSFile.from_fieldstorage(file)

    print argo_file
    print argo_file.__dict__
    DBSession.add(argo_file)
    transaction.commit()

    request.session.pop_flash('form_entered_argo_expocode')
    request.session.pop_flash('form_entered_argo_date')
    request.session.pop_flash('form_entered_argo_ship')
    request.session.pop_flash('form_entered_argo_display')
    request.session.pop_flash('form_entered_argo_description')

    request.session.flash(
        'Added Argo file to Argo secure file repository.', 'action_taken')
    raise HTTPSeeOther(location='/argo.html')
