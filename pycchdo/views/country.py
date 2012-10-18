from pyramid.httpexceptions import (
    HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized)

from . import *
import pycchdo.helpers as h
from pycchdo.models import Country
from pycchdo.views import staff


def countries_index(request):
    countries = sorted(
        Country.query().all(), key=lambda x: x.name)
    return {'countries': countries}


def countries_index_json(request):
    countries = sorted(
        Country.query().all(), key=lambda x: x.name)
    countries = [c.to_nice_dict() for c in countries]
    return countries


def _get_country(request):
    c_id = request.matchdict.get('country_id')
    country = Country.query().get(c_id)
    if not country:
        countries = Country.get_all_by_attrs({'iso_3166-1': c_id})
        if len(countries) > 0:
            country = countries[0]
    return country


def _redirect_response(request, id):
    raise HTTPSeeOther(
        location=request.route_path('country_show', country_id=id))


def country_show(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()
    cruises = country.cruises(accepted_only=False)
    return {'country': country, 'cruises': cruises}


def country_archive(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()
    return staff.archive(request, country.cruises())


def country_edit(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()

    name = request.params.get('name', '')
    iso2 = request.params.get('iso_3166-1_alpha-2', '')
    iso3 = request.params.get('iso_3166-1_alpha-3', '')

    if country.name != name:
        country.set_accept('iso_3166-1', name, request.user)
    if country.iso_code() != iso2:
        country.set_accept('iso_3166-1_alpha-2', iso2, request.user)
    if country.iso_code(3) != iso3:
        country.set_accept('iso_3166-1_alpha-3', iso3, request.user)

    return _redirect_response(request, country.id)


def country_merge(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    if not h.has_mod(request):
        raise HTTPUnauthorized()

    country = _get_country(request)
    if not country:
        raise HTTPNotFound()

    redirect_response = _redirect_response(request, country.id)

    try:
        mergee_id = request.params['mergee_country_id']
    except KeyError:
        request.session.flash('No mergee country given', 'help')
        return redirect_response
    mergee = Country.query().get(mergee_id)
    if not mergee:
        request.session.flash('Invalid mergee country %s given' % mergee_id, 'help')
        return redirect_response

    request.session.flash(mergee.people(), 'help')

    cruises = set(country.cruises()).union(mergee.cruises())
    for cruise in cruises:
        cruise.set_accept(Country.cruise_associate_key, country.id, request.user)
    people = country.people()
    for person in people:
        if person.country != country.id:
            person.country = country.id
            person.save()
    request.session.flash('Merged country with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
