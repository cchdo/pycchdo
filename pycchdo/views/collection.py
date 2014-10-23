import transaction

from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPUnauthorized

from sqlalchemy.orm import defer, load_only, noload, joinedload, subqueryload

from . import *
import pycchdo.helpers as h
from pycchdo.models.serial import Collection
from pycchdo.models.search import _cruises_load_options
from pycchdo.models.types import TextList, Unicode
from pycchdo.models.searchsort import sort_list
from pycchdo.views import log, staff, load_cruises_for


def _collections(request):
    query = Collection.query().filter(Collection.accepted).\
            options(*_cruises_load_options)
    collections = query.all()
    collections = sorted(collections, key=lambda c: c.name)
    return collections


def collections_index(request):
    collections = paged(request, _collections(request))
    return {'collections': collections}


def collections_index_json(request):
    collections = [c.to_dict() for c in _collections(request)]
    return collections


def _get_collection(request):
    coll_id = request.matchdict.get('collection_id')
    try:
        collection = load_cruises_for(Collection.query()).\
            get(coll_id)
    except ValueError:
        raise HTTPBadRequest()
    return collection


def _redirect_response(request, id):
    return HTTPSeeOther(
        location=request.route_path('collection_show', collection_id=id))


def collection_show(request):
    expanded = request.params.get('expanded', '')
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    cruises = collection.cruises
    cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    cruises = paged(request, cruises)
    return {'collection': collection, 'cruises': cruises, 'expanded': expanded}


def collection_archive(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()
    return staff.archive(request, collection.cruises)


def collection_edit(request):
    collection = _get_collection(request)
    if not collection:
        raise HTTPNotFound()

    cruises = collection.cruises
    response = {'collection': collection, 'cruises': cruises}

    try:
        names = text_to_obj(request.params.get('names', ''), TextList)
    except ValueError:
        request.session.flash(
            'Invalid collection names. Please ensure names are a list (x,y,z)',
            'help')
        return response

    if collection.get('names') != names:
        collection.set(request.user, 'names', names)

    try:
        type = text_to_obj(request.params.get('type', ''), Unicode)
    except ValueError:
        request.session.flash('Invalid collection type', 'help')
        return response

    if collection.type != type:
        collection.set(request.user, 'type', type)

    try:
        oceans = text_to_obj(request.params.get('oceans', ''), TextList)
    except ValueError:
        request.session.flash(
            'Invalid collection oceans. Please ensure oceans are a list (x,y,z)',
            'help')
        return response

    if collection.get('oceans') != oceans:
        collection.set(request.user, 'oceans', oceans)

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
    mergee = Collection.query().get(mergee_id)
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
