from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
import pycchdo.models as models
from pycchdo.views import staff


def institutions_index(request):
    institutions = sorted(models.Institution.get_all(), key=lambda x: x.name)
    institutions = _paged(request, institutions)
    return {'institutions': institutions}


def institutions_index_json(request):
    institutions = sorted(models.Institution.get_all(), key=lambda x: x.name)
    institutions = [i.to_nice_dict() for i in institutions]
    return institutions


def _get_institution(request):
    institution_id = request.matchdict.get('institution_id')
    return models.Institution.get_id(institution_id)


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('institution_show', institution_id=id))


def institution_show(request):
    institution = _get_institution(request)
    if not institution:
        return HTTPNotFound()
    return {'institution': institution}


def institution_archive(request):
    institution = _get_institution(request)
    if not institution:
        return HTTPNotFound()
    return staff.archive(request, institution.cruises())


def institution_edit(request):
    institution = _get_institution(request)
    if not institution:
        return HTTPNotFound()

    name = request.params.get('name', '')

    if institution.name != name:
        institution.set_accept('name', name, request.user)

    return _redirect_response(request, institution.id)


def institution_merge(request):
    if _http_method(request) != 'PUT':
        return HTTPBadRequest()

    if not h.has_mod(request):
        return HTTPUnauthorized()

    institution = _get_institution(request)
    if not institution:
        return HTTPNotFound()

    redirect_response = _redirect_response(request, institution.id)

    try:
        mergee_id = request.params['mergee_institution_id']
    except KeyError:
        request.session.flash('No mergee institution given', 'help')
        return redirect_response
    mergee = models.Institution.get_id(mergee_id)
    if not mergee:
        request.session.flash(
            'Invalid mergee institution %s given' % mergee_id, 'help')
        return redirect_response

    cruises = set(institution.cruises()).union(mergee.cruises())
    for cruise in cruises:
        participants = cruise.get('participants')
        for p in participants:
            if p['institution'] == mergee.id:
                p['institution'] = institution.id
        cruise.set_accept(models.Institution.cruise_associate_key,
                          participants, request.user)
    people = mergee.people()
    for person in people:
        person.institution = institution.id
        person.save()
    request.session.flash(
        'Merged institution with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
