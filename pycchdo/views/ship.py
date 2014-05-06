import transaction

from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
from pycchdo.models.serial import Ship
from pycchdo.models.searchsort import sort_list
from pycchdo.views import staff


def ships_index(request):
    ships = Ship.query().all()
    ships = sorted(ships, key=lambda s: s.name)
    return {'ships': ships}


def ships_index_json(request):
    ships = Ship.query().all()
    ships = sorted(ships, key=lambda s: s.name)
    return [s.to_dict() for s in ships]


def _get_ship(request):
    ship_id = request.matchdict.get('ship_id')
    return Ship.query().get(ship_id)


def _redirect_response(request, id):
    return HTTPSeeOther(location=request.route_path('ship_show', ship_id=id))


def ship_show(request):
    ship = _get_ship(request)
    if not ship:
        raise HTTPNotFound()
    cruises = ship.cruises
    cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    return {'ship': ship, 'cruises': cruises}


def ship_archive(request):
    ship = _get_ship(request)
    if not ship:
        raise HTTPNotFound()
    return staff.archive(request, ship.cruises)


def ship_edit(request):
    ship = _get_ship(request)
    if not ship:
        raise HTTPNotFound()

    name = request.params.get('name', '')

    if ship.name != name:
        ship.set(request.user, 'name', name)

    return _redirect_response(request, ship.id)


def ship_merge(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    if not h.has_mod(request):
        raise HTTPUnauthorized()

    ship = _get_ship(request)
    if not ship:
        raise HTTPNotFound()

    redirect_response = _redirect_response(request, ship.id)

    try:
        mergee_id = request.params['mergee_ship_id']
    except KeyError:
        request.session.flash('No mergee ship given', 'help')
        return redirect_response
    mergee = Ship.query().get(mergee_id)
    if not mergee:
        request.session.flash('Invalid mergee ship %s given' % mergee_id, 'help')
        return redirect_response

    ship.merge(request.user, mergee)
    transaction.commit()

    transaction.begin()
    request.session.flash('Merged ship with %s' % mergee, 'action_taken')
    return redirect_response
