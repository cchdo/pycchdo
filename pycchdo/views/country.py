from pyramid.httpexceptions import (
    HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized)

import transaction

from sqlalchemy.exc import DataError

from . import *
import pycchdo.helpers as h
from pycchdo.models.serial import DBSession, Country
from pycchdo.models.searchsort import sort_list
from pycchdo.views import staff


def _countries(request):
    countries = Country.query().filter(Country.accepted).all()
    countries = sorted(countries, key=lambda c: c.name)
    return countries


def countries_index(request):
    return {'countries': _countries(request)}


def countries_index_json(request):
    countries = [c.to_dict() for c in _countries(request)]
    return countries


def _get_country(request):
    c_id = request.matchdict.get('country_id')
    try:
        return Country.query().get(c_id)
    except DataError:
        transaction.begin()
        try:
            return Country.query().filter(Country.name == c_id).first()
        except DataError:
            return None


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('country_show', country_id=id))


def country_show(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()
    cruises = country.cruises
    cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    return {'country': country, 'cruises': cruises}


def country_archive(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()
    return staff.archive(request, country.cruises)


def country_edit(request):
    country = _get_country(request)
    if not country:
        raise HTTPNotFound()

    name = request.params.get('name', '')
    iso2 = request.params.get('iso_3166-1_alpha-2', '')
    iso3 = request.params.get('iso_3166-1_alpha-3', '')

    country.name = name
    country.alpha2 = iso2
    country.alpha3 = iso3

    country_id = country.id
    transaction.commit()
    return _redirect_response(request, country_id)


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
        request.session.flash(
            'Invalid mergee country %s given' % mergee_id, 'help')
        return redirect_response

    country.merge(request.user, mergee)
    transaction.commit()

    request.session.flash('Merged country with %s' % mergee, 'action_taken')
    return redirect_response
