import os.path
import re

from pyramid.request import Request
from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound

from sqlalchemy import distinct

from pycchdo.helpers import cruises_sort_by_date_start
from pycchdo.views.toplevel import catchall_static
from pycchdo.models.serial import Collection
from pycchdo.log import getLogger


log = getLogger(__name__)


static_basins = ['atlantic', 'pacific', ]
allowed_basins = ['arctic', 'indian', 'southern', ]
basins = allowed_basins + static_basins


def _sorted_by_name(collections):
    return sorted(collections, key=lambda c: c.name)


def _coll_cruises(colls):
    """Return dict mapping collection to its cruises."""
    cc = {}
    for coll in colls:
        cc[coll] = cruises_sort_by_date_start(coll.cruises)
    return cc


def _arctic():
    """Provide a list of collections with cruises in the Arctic circle.

    """
    colls = Collection.query().filter(Collection.basins.contains(u'arctic')).all()

    results = {'default': colls}
    _sort_results(results)
    return results, _coll_cruises(colls)


def _indian():
    colls = Collection.query().filter(Collection.basins.contains(u'indian')).all()

    results = {
        u'indian': [],
        u'southern': [],
        u'atlantic': [],
    }

    for coll in colls:
        basins = list(coll.basins)
        if u'atlantic' in basins:
            results[u'atlantic'].append(coll)
        elif u'southern' in basins:
            results[u'southern'].append(coll)
        else:
            results[u'indian'].append(coll)

    _sort_results(results)
    return results, _coll_cruises(colls)


def _sort_results(results):
    for key in results:
        results[key] = _sorted_by_name(results[key])


def _southern():
    colls = Collection.query().filter(Collection.basins.contains(u'southern')).all()

    results = {
        u'southern': [],
        u'atlantic': [],
        u'indian': [],
        u'pacific': [],
    }

    for coll in colls:
        basins = list(coll.basins)
        if u'atlantic' in basins:
            results[u'atlantic'].append(coll)
        elif u'indian' in basins:
            results[u'indian'].append(coll)
        elif u'pacific' in basins:
            results[u'pacific'].append(coll)
        else:
            results[u'southern'].append(coll)

    _sort_results(results)
    return results, _coll_cruises(colls)


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
        collections, coll_cruises = _arctic()
    elif basin == 'indian':
        areas = ['Indian', 'Southern', 'Atlantic', ]
        collections, coll_cruises = _indian()
    elif basin == 'southern':
        areas = ['Southern', 'Atlantic', 'Indian', 'Pacific', ]
        collections, coll_cruises = _southern()

    if not collections:
        raise HTTPNotFound()

    return {
        'basin': basin.capitalize(),
        'areas': areas,
        'collections': collections,
        'coll_cruises': coll_cruises,
    }
