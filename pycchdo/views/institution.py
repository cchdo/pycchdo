from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
from pycchdo.models import Institution
from pycchdo.views import staff


def institutions_index(request):
    institutions = sorted(Institution.query().all(), key=lambda x: x.name)
    institutions = paged(request, institutions)
    return {'institutions': institutions}


def institutions_index_json(request):
    institutions = sorted(Institution.query().all(), key=lambda x: x.name)
    institutions = [i.to_nice_dict() for i in institutions]
    return institutions


def _get_institution(request):
    institution_id = request.matchdict.get('institution_id')
    return Institution.query().get(institution_id)


def _redirect_response(request, id):
    raise HTTPSeeOther(
        location=request.route_path('institution_show', institution_id=id))


def institution_show(request):
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()
    cruises = institution.cruises(accepted_only=False)
    return {'institution': institution, 'cruises': cruises}


def institution_archive(request):
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()
    return staff.archive(request, institution.cruises())


def institution_edit(request):
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()

    name = request.params.get('name', '')

    if institution.name != name:
        institution.set_accept('name', name, request.user)

    return _redirect_response(request, institution.id)


def institution_merge(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    if not h.has_mod(request):
        raise HTTPUnauthorized()

    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()

    redirect_response = _redirect_response(request, institution.id)

    try:
        mergee_id = request.params['mergee_institution_id']
    except KeyError:
        request.session.flash('No mergee institution given', 'help')
        return redirect_response
    mergee = Institution.query().get(mergee_id)
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
        cruise.set_accept(Institution.cruise_associate_key,
                          participants, request.user)
    people = mergee.people()
    for person in people:
        person.institution = institution.id
        person.save()
    request.session.flash(
        'Merged institution with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
