from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def collections_index(request):
    return {'collections': models.Collection.map_mongo(models.Collection.find())}


def collection_show(request):
    coll_id = request.matchdict.get('collection_id')
    collection = models.Collection.get_id(coll_id)
    if not collection:
        return HTTPNotFound()
    return {'collection': collection}
