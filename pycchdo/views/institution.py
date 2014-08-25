import transaction

from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
from pycchdo.models.serial import Institution
from pycchdo.models.searchsort import sort_list
from pycchdo.views import staff, load_cruises_for


def _institutions(request):
    institutions = Institution.query().filter(Institution.accepted).all()
    institutions = sorted(institutions, key=lambda c: c.name)
    return institutions


def institutions_index(request):
    institutions = paged(request, _institutions(request))
    return {'institutions': institutions}


def institutions_index_json(request):
    institutions = [i.to_dict() for i in _institutions(request)]
    return institutions


def _get_institution(request):
    institution_id = request.matchdict.get('institution_id')
    return load_cruises_for(Institution.query()).get(institution_id)


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('institution_show', institution_id=id))


def institution_show(request):
    expanded = request.params.get('expanded', '')
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()
    cruises = institution.cruises
    cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    cruises = paged(request, cruises)
    return {'institution': institution, 'cruises': cruises, 'expanded': expanded}


def institution_archive(request):
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()
    return staff.archive(request, institution.cruises)


def institution_edit(request):
    institution = _get_institution(request)
    if not institution:
        raise HTTPNotFound()

    name = request.params.get('name', '')

    if institution.name != name:
        institution.set(request.user, 'name', name)

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

    institution.merge(request.user, mergee)
    transaction.commit()

    request.session.flash('Merged institution with %s' % mergee, 'action_taken')
    return redirect_response
