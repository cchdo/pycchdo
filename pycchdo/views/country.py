from pyramid.httpexceptions import (
    HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized)

import transaction

from sqlalchemy.exc import DataError

from . import *
import pycchdo.helpers as h
from pycchdo.models import DBSession, Country
from pycchdo.models.models import preload_cached_avs
from pycchdo.views import staff


def countries_index(request):
    countries = preload_cached_avs(Country, Country.query()).all()
    countries = sorted(countries, key=lambda x: x.name)
    return {'countries': countries}


def countries_index_json(request):
    countries = preload_cached_avs(Country, Country.query()).all()
    countries = sorted(countries, key=lambda x: x.name)
    countries = [c.to_nice_dict() for c in countries]
    return countries


def _get_country(request):
    c_id = request.matchdict.get('country_id')
    try:
        return preload_cached_avs(Country, Country.query()).get(c_id)
    except DataError:
        transaction.begin()
        try:
            return preload_cached_avs(
                Country,
                Country.query().filter(Country.iso_3166_1 == c_id)).first()
        except DataError:
            return None


def _redirect_response(request, id):
    return HTTPSeeOther(
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

    country.iso_3166_1 = name
    country.iso_3166_1_alpha_2 = iso2
    country.iso_3166_1_alpha_3 = iso3

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
    mergee = preload_cached_avs(Country, Country.query()).get(mergee_id)
    if not mergee:
        request.session.flash(
            'Invalid mergee country %s given' % mergee_id, 'help')
        return redirect_response

    country.merge(request.user, mergee)
    transaction.commit()

    request.session.flash('Merged country with %s' % mergee, 'action_taken')
    return redirect_response
