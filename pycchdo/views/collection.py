from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
import pycchdo.models as models
from pycchdo.views import staff


def collections_index(request):
    collections = sorted(models.Collection.get_all(), key=lambda c: c.name)
    collections = paged(request, collections)
    return {'collections': collections}


def collections_index_json(request):
    collections = sorted(models.Collection.get_all(), key=lambda c: c.name)
    collections = [c.to_nice_dict() for c in collections]
    return collections


def _get_collection(request):
    coll_id = request.matchdict.get('collection_id')
    return models.Collection.get_id(coll_id)


def _redirect_response(request, id):
    raise HTTPSeeOther(
        location=request.route_path('collection_show', collection_id=id))


def collection_show(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    return {'collection': collection}


def collection_archive(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    return staff.archive(request, collection.cruises())


def collection_edit(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()

    try:
        names = text_to_obj(request.params.get('names', ''), 'text_list')
    except ValueError:
        request.session.flash(
            'Invalid collection names. Please ensure names are a list (x,y,z)',
            'help')
        return {'collection': collection}

    if collection.names != names:
        collection.set_accept('names', names, request.user)

    try:
        type = text_to_obj(request.params.get('type', ''), 'text')
    except ValueError:
        request.session.flash('Invalid collection type', 'help')
        return {'collection': collection}

    if collection.type != type:
        collection.set_accept('type', type, request.user)

    try:
        basins = text_to_obj(request.params.get('basins', ''), 'text_list')
    except ValueError:
        request.session.flash(
            'Invalid collection basins. Please ensure basins are a list (x,y,z)',
            'help')
        return {'collection': collection}

    if collection.get('basins') != basins:
        collection.set_accept('basins', basins, request.user)

    return _redirect_response(request, collection.id)


def collection_merge(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    if not h.has_mod(request):
        raise HTTPUnauthorized()

    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()

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

    try:
        collection.merge(request.user, mergee)
    except TypeError:
        request.session.flash('Invalid mergee collection found', 'help')
        return redirect_response

    request.session.flash('Merged collection with %s' % mergee, 'action_taken')
    return redirect_response
