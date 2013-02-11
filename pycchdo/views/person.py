from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from sqlalchemy.orm import joinedload_all

import transaction

from . import *
import pycchdo.helpers as h
from pycchdo.models import Person, DBSession
from pycchdo.models.models import preload_person
from pycchdo.views.staff import staff_signin_required
from pycchdo.views import staff


def people_index(request):
    people = preload_person(Person, Person.query()).\
        order_by(Person.name_last).all()
    people = paged(request, people)
    return {'people': people}


def people_index_json(request):
    people = preload_person(Person, Person.query()).\
        order_by(Person.name_last).all()
    people = [p.to_nice_dict() for p in people]
    return people


def _get_person(request):
    person_id = request.matchdict.get('person_id')
    return preload_person(Person, Person.query()).get(person_id)


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('person_show', person_id=id))


def person_show(request):
    person = _get_person(request)
    if not person:
        raise HTTPNotFound()
    cruises = person.cruises(accepted_only=False)
    return {'person': person, 'cruises': cruises}


def person_archive(request):
    person = _get_person(request)
    if not person:
        raise HTTPNotFound()
    return staff.archive(request, person.cruises())


@staff_signin_required
def person_edit(request):
    person = _get_person(request)
    person_id = person.id
    if not person:
        raise HTTPNotFound()

    identifier = request.params.get('identifier', '')
    name = request.params.get('name', '')
    name_first = request.params.get('name_first', '')
    name_last = request.params.get('name_last', '')
    try:
        institution = text_to_obj(request.params.get('institution', ''), 'id')
    except:
        request.response.status = 400
        h.form_errors_for(request, 'institution', 'Bad institution id')
        return {'person': person}
    try:
        country = text_to_obj(request.params.get('country', ''), 'id')
    except:
        request.response.status = 400
        h.form_errors_for(request, 'country', 'Bad country id')
        return {'person': person}

    email = request.params.get('email', '')
    try:
        permissions = text_to_obj(request.params.get('permissions', ''), 'text_list')
    except:
        request.response.status = 400
        h.form_errors_for(request, 'permissions', 'Bad permissions format')
        return {'person': person}

    person.identifier = identifier
    person.name = name
    person.name_first = name_first
    person.name_last = name_last
    if institution:
        person.institution = institution
    if country:
        person.country = country
    person.email = email
    if permissions:
        person.permissions = permissions

    transaction.commit()
    return _redirect_response(request, person_id)


@staff_signin_required
def person_merge(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    if not h.has_mod(request):
        raise HTTPUnauthorized()

    person = _get_person(request)
    if not person:
        raise HTTPNotFound()

    redirect_response = _redirect_response(request, person.id)

    try:
        mergee_id = request.params['mergee_person_id']
    except KeyError:
        request.session.flash('No mergee person given', 'help')
        return redirect_response
    mergee = preload_person(Person, Person.query()).get(mergee_id)
    if not mergee:
        request.session.flash(
            u'Invalid mergee person {0} given'.format(mergee_id), 'help')
        return redirect_response

    if not person.identifier:
        person.identifier = mergee.identifier
    if not person.name:
        person.name = mergee.name
    if not person.name_first:
        person.name_first = mergee.name_first
    if not person.name_last:
        person.name_last = mergee.name_last
    if not person.institution and mergee.institution:
        person.set_accept('institution', mergee.institution.id, request.user)
    if not person.country and mergee.country:
        person.set_accept('country', mergee.country.id, request.user)
    if not person.email:
        person.email = mergee.email
    if not person.permissions:
        person.permissions = mergee.permissions

    person.merge(request.user, mergee)
    transaction.commit()

    request.session.flash(
        u'Merged person with {0}'.format(mergee_id), 'action_taken')
    return redirect_response
