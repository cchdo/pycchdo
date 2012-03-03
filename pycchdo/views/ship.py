from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
import pycchdo.models as models


def ships_index(request):
    return {'ships': sorted(models.Ship.get_all(), key=lambda s: s.name)}


def ships_index_json(request):
    ships = sorted(models.Ship.get_all(), key=lambda s: s.name)
    return [s.to_nice_dict() for s in ships]


def _get_ship(request):
    ship_id = request.matchdict.get('ship_id')
    return models.Ship.get_id(ship_id)


def _redirect_response(request, id):
    return HTTPSeeOther(location=request.route_path('ship_show', ship_id=id))


def ship_show(request):
    ship = _get_ship(request)
    if not ship:
        return HTTPNotFound()
    return {'ship': ship}


def ship_edit(request):
    ship = _get_ship(request)
    if not ship:
        return HTTPNotFound()

    name = request.params.get('name', '')

    if ship.name != name:
        ship.set_accept('name', name, request.user)

    return _redirect_response(request, ship.id)


def ship_merge(request):
    if _http_method(request) != 'PUT':
        return HTTPBadRequest()

    if not h.has_mod(request):
        return HTTPUnauthorized()

    ship = _get_ship(request)
    if not ship:
        return HTTPNotFound()

    redirect_response = _redirect_response(request, ship.id)

    try:
        mergee_id = request.params['mergee_ship_id']
    except KeyError:
        request.session.flash('No mergee ship given', 'help')
        return redirect_response
    mergee = models.Ship.get_id(mergee_id)
    if not mergee:
        request.session.flash('Invalid mergee ship %s given' % mergee_id, 'help')
        return redirect_response

    cruises = set(ship.cruises()).union(mergee.cruises())
    for cruise in cruises:
        cruise.set_accept(models.Ship.cruise_associate_key, ship.id, request.user)
    request.session.flash('Merged ship with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
