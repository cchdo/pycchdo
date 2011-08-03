from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def countries_index(request):
    return {'countries': models.Country.map_mongo(models.Country.find())}


def country_show(request):
    coll_id = request.matchdict.get('country_id')
    country = models.Country.get_id(coll_id)
    if not country:
        return HTTPNotFound()
    return {'country': country}
