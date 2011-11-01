from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def countries_index(request):
    return {'countries': models.Country.map_mongo(models.Country.find())}


def country_show(request):
    c_id = request.matchdict.get('country_id')
    country = models.Country.get_id(c_id)
    if not country:
        countries = models.Country.get_by_attrs({'iso_3166-1': c_id})
        if len(countries) > 0:
            country = countries[0]
    if not country:
        return HTTPNotFound()
    return {'country': country}
