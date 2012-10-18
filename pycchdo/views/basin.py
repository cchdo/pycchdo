import os.path
import re

from pyramid.request import Request
from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound

from sqlalchemy import distinct

from pycchdo.views.toplevel import catchall_static
import pycchdo.models as models
from pycchdo.models import Collection
from pycchdo.log import ColoredLogger


log = ColoredLogger(__name__)


static_basins = ['atlantic', 'pacific', ]
allowed_basins = ['arctic', 'indian', 'southern', ]
basins = allowed_basins + static_basins


def _sorted_by_name(collections):
    return sorted(collections, key=lambda c: c.name)


def _arctic():
    """Provide a list of collections with cruises in the Arctic circle.

    """
    default = []
    collections = Collection.get_all_by_attrs({
        'names': re.compile('.*arctic.*', re.IGNORECASE)
        })

    coll_cruises = set()
    for coll in collections:
        coll_cruises |= set(coll.cruises())
    coll_cruise_ids = [c.id for c in coll_cruises]

    one_away_collection_ids = set()
    for coll_cruise in coll_cruises:
        one_away_collection_ids |= set(coll_cruise.get('collections'))

    one_away_collections = Collection.by_ids(
        list(one_away_collection_ids)).all()
    woce_collections = filter(
        lambda c: c.get('type') == 'WOCE line', one_away_collections)
    collections = _sorted_by_name(woce_collections)

    return {'default': collections}


def _indian():
    ind = []
    sou = []
    atl = []
    # Currently, only indian basin page is generated from spatial groups
    colls = Collection.get_all_by_attrs({'basins': 'indian'}) + \
            Collection.get_all_by_attrs({'basins': 'southern'}) + \
            Collection.get_all_by_attrs({'basins': 'atlantic'})
    for sgs in colls:
        basins = sgs.get('basins')
        if 'indian' not in basins:
            continue
        if 'atlantic' in basins:
            atl.append(sgs)
        else:
            if 'southern' in basins:
                sou.append(sgs)
            else:
                ind.append(sgs)

    return {
        'indian': ind,
        'southern': sou,
        'atlantic': atl,
    }


def _filter_for_southern(collections):
    filtered = []
    for collection in collections:
        cruises = collection.cruises(limit=1)
        cruise = None
        if len(cruises) > 0:
            cruise = cruises[0]
        if cruise:
            ok = False
            for c in cruise.collections:
                if 'Southern' in c.name:
                    ok = True
                    break
            if not ok:
                continue
        filtered.append(collection)
    return filtered


def _southern():
    sou = Collection.get_all_by_attrs({
        'type': 'WOCE line',
        'names': re.compile('S.*', re.IGNORECASE)
        })
    atl = Collection.get_all_by_attrs({
        'type': 'WOCE line',
        'names': re.compile('A(R|J|__).*', re.IGNORECASE)
        })
    ind = Collection.get_all_by_attrs({
        'type': 'WOCE line',
        'names': re.compile('(I|AIS).*', re.IGNORECASE)
        })
    pac = Collection.get_all_by_attrs({
        'type': 'WOCE line',
        'names': re.compile('(P|AAI).*', re.IGNORECASE)
        })

    sou = _filter_for_southern(sou)
    atl = _filter_for_southern(atl)
    ind = _filter_for_southern(ind)
    pac = _filter_for_southern(pac)

    sou = _sorted_by_name(sou)
    atl = _sorted_by_name(atl)
    ind = _sorted_by_name(ind)
    pac = _sorted_by_name(pac)

    return {
        'southern': sou,
        'atlantic': atl,
        'indian': ind,
        'pacific': pac,
    }


def basin_show(request):
    basin = request.matchdict.get('basin', '').lower()
    if basin not in allowed_basins:
        if basin in static_basins:
            request.matchdict = {'subpath': [u'basin/%s.html' % basin]}
            return catchall_static(request)
        raise HTTPNotFound()

    collections = None
    areas = []
    if basin == 'arctic':
        collections = _arctic()
    elif basin == 'indian':
        areas = ['Indian', 'Southern', 'Atlantic', ]
        collections = _indian()
    elif basin == 'southern':
        areas = ['Southern', 'Atlantic', 'Indian', 'Pacific', ]
        collections = _southern()

    if not collections:
        raise HTTPNotFound()

    return {
        'basin': basin.capitalize(),
        'areas': areas,
        'collections': collections,
    }
