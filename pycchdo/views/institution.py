from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def institutions_index(request):
    return {'institutions': models.Institution.map_mongo(models.Institution.find())}


def institution_show(request):
    coll_id = request.matchdict.get('institution_id')
    institution = models.Institution.get_id(coll_id)
    if not institution:
        return HTTPNotFound()
    return {'institution': institution}
