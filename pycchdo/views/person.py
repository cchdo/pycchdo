from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
import pycchdo.models as models


def people_index(request):
    people = sorted(models.Person.get_all(), key=lambda x: x.name_last)
    people = _paged(request, people)
    return {'people': people}


def _get_person(request):
    person_id = request.matchdict.get('person_id')
    return models.Person.get_id(person_id)


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('person_show', person_id=id))


def person_show(request):
    person = _get_person(request)
    if not person:
        return HTTPNotFound()
    return {'person': person}


def person_edit(request):
    person = _get_person(request)
    if not person:
        return HTTPNotFound()

    identifier = request.params.get('identifier', '')
    name_first = request.params.get('name_first', '')
    name_last = request.params.get('name_last', '')
    institution = text_to_obj(request.params.get('institution'), 'id')
    country = text_to_obj(request.params.get('country'), 'id')
    email = request.params.get('email', '')

    person.identifier = identifier
    person.name_first = name_first
    person.name_last = name_last
    if institution:
        person.institution = institution
    if country:
        person.country = country
    person.email = email

    person.save()

    return _redirect_response(request, person.id)


def person_merge(request):
    if _http_method(request) != 'PUT':
        return HTTPBadRequest()

    if not h.has_mod(request):
        return HTTPUnauthorized()

    person = _get_person(request)
    if not person:
        return HTTPNotFound()

    redirect_response = _redirect_response(request, person.id)

    try:
        mergee_id = request.params['mergee_person_id']
    except KeyError:
        request.session.flash('No mergee person given', 'help')
        return redirect_response
    mergee = models.Person.get_id(mergee_id)
    if not mergee:
        request.session.flash('Invalid mergee person %s given' % mergee_id,
                              'help')
        return redirect_response

    if not person.identifier:
        person.identifier = mergee.identifier
    if not person.name_first:
        person.name_first = mergee.name_first
    if not person.name_last:
        person.name_last = mergee.name_last
    if not person.institution_:
        person.institution_ = mergee.institution_
    if not person.country_:
        person.country_ = mergee.country_
    if not person.email:
        person.email = mergee.email
    person.save()

    cruises = set(person.cruises()).union(mergee.cruises())
    for cruise in cruises:
        participants = cruise.get('participants')
        for p in participants:
            if p['person'] == mergee.id:
                p['person'] = person.id
        cruise.set_accept(models.Person.cruise_associate_key, participants,
                          request.user)
    request.session.flash('Merged person with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
