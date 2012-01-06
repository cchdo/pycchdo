from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
import pycchdo.models as models


def collections_index(request):
    collections = models.Collection.map_mongo(models.Collection.find())
    collections = _paged(request, collections)
    return {'collections': collections}


def _get_collection(request):
    coll_id = request.matchdict.get('collection_id')
    return models.Collection.get_id(coll_id)


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('collection_show', collection_id=id))


def collection_show(request):
    collection = _get_collection(request)
    if not collection:
        return HTTPNotFound()
    return {'collection': collection}


def collection_edit(request):
    collection = _get_collection(request)
    if not collection:
        return HTTPNotFound()

    names = text_to_obj(request.params.get('names', ''), 'text_list')

    if collection.names != names:
        collection.set_accept('names', names, request.user)

    return _redirect_response(request, collection.id)


def collection_merge(request):
    if _http_method(request) != 'PUT':
        return HTTPBadRequest()

    if not h.has_mod(request):
        return HTTPUnauthorized()

    collection = _get_collection(request)
    if not collection:
        return HTTPNotFound()

    redirect_response = _redirect_response(request, collection.id)

    try:
        mergee_id = request.params['mergee_collection_id']
    except KeyError:
        request.session.flash('No mergee collection given', 'help')
        return redirect_response
    mergee = models.Collection.get_id(mergee_id)
    if not mergee:
        request.session.flash('Invalid mergee collection %s given' % mergee_id,
                              'help')
        return redirect_response

    names = set(collection.names).union(mergee.names)
    collection.set_accept('names', list(names), request.user)
    cruises = set(collection.cruises()).union(mergee.cruises())
    for cruise in cruises:
        colls = cruise.collections
        try:
            colls.remove(mergee)
        except ValueError:
            pass
        try:
            colls.index(collection)
        except ValueError:
            colls.append(collection)
        cruise.set_accept(models.Collection.cruise_associate_key,
                          [c.id for c in colls], request.user)
    request.session.flash('Merged collection with %s' % mergee, 'action_taken')
    mergee.remove()

    return redirect_response
