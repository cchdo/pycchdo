import transaction

from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from . import *
import pycchdo.helpers as h
from pycchdo.models import Collection
from pycchdo.models.types import TextList, Unicode
from pycchdo.models.models import (
    preload_cached_avs, disjoint_load_collection_attrs, )
from pycchdo.models.searchsort import sort_list
from pycchdo.views import log, staff


def collections_index(request):
    collections = preload_cached_avs(Collection, Collection.query()).all()
    disjoint_load_collection_attrs(collections)
    collections = sorted(collections, key=lambda c: c.name)
    collections = paged(request, collections)
    return {'collections': collections}


def collections_index_json(request):
    collections = preload_cached_avs(Collection, Collection.query()).all()
    disjoint_load_collection_attrs(collections)
    collections = sorted(collections, key=lambda c: c.name)
    collections = [c.to_nice_dict() for c in collections]
    return collections


def _get_collection(request):
    coll_id = request.matchdict.get('collection_id')
    collection =  preload_cached_avs(Collection, Collection.query()).get(coll_id)
    disjoint_load_collection_attrs([collection])
    return collection


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('collection_show', collection_id=id))


def collection_show(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    cruises = collection.cruises(accepted_only=False)
    cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    return {'collection': collection, 'cruises': cruises}


def collection_archive(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    return staff.archive(request, collection.cruises())


def collection_edit(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()

    cruises = collection.cruises(accepted_only=False)
    response = {'collection': collection, 'cruises': cruises}

    try:
        names = text_to_obj(request.params.get('names', ''), TextList)
    except ValueError:
        request.session.flash(
            'Invalid collection names. Please ensure names are a list (x,y,z)',
            'help')
        return response

    if collection.get('names') != names:
        collection.set_accept('names', names, request.user)

    try:
        type = text_to_obj(request.params.get('type', ''), Unicode)
    except ValueError:
        request.session.flash('Invalid collection type', 'help')
        return response

    if collection.type != type:
        collection.set_accept('type', type, request.user)

    try:
        basins = text_to_obj(request.params.get('basins', ''), TextList)
    except ValueError:
        request.session.flash(
            'Invalid collection basins. Please ensure basins are a list (x,y,z)',
            'help')
        return response

    if collection.get('basins') != basins:
        collection.set_accept('basins', basins, request.user)

    coll_id = collection.id
    transaction.commit()
    return _redirect_response(request, coll_id)


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
    mergee = preload_cached_avs(Collection, Collection.query()).get(mergee_id)
    disjoint_load_collection_attrs([mergee])
    if not mergee:
        request.session.flash(
            u'Invalid mergee collection {0} given'.format(mergee_id), 'help')
        return redirect_response

    try:
        collection.merge(request.user, mergee)
    except TypeError:
        request.session.flash('Invalid mergee collection found', 'help')
        return redirect_response
    transaction.commit()

    request.session.flash('Merged collection with %s' % mergee, 'action_taken')
    return redirect_response
