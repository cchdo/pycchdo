from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def ships_index(request):
    return {'ships': models.Ship.map_mongo(models.Ship.find())}


def ship_show(request):
    coll_id = request.matchdict.get('ship_id')
    ship = models.Ship.get_id(coll_id)
    if not ship:
        return HTTPNotFound()
    return {'ship': ship}
