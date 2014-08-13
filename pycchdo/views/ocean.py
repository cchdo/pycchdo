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


static_oceans = ['atlantic', 'pacific', ]
allowed_oceans = ['arctic', 'indian', 'southern', ]
oceans = allowed_oceans + static_oceans


def _sorted_by_name(collections):
    return sorted(collections, key=lambda c: c.name)


def _coll_cruises(colls):
    """Return dict mapping collection to its cruises."""
    cc = {}
    for coll in colls:
        cc[coll] = cruises_sort_by_date_start(coll.cruises)
    return cc


def _sort_results(results):
    return _sorted_by_name(results)


def _arctic():
    """Provide a list of collections with cruises in the Arctic circle.

    """
    colls = Collection.query().filter(Collection.oceans.contains(u'arctic')).all()
    colls = _sort_results(colls)
    return colls, _coll_cruises(colls)


def _indian():
    colls = Collection.query().filter(Collection.oceans.contains(u'indian')).all()
    colls = _sort_results(colls)
    return colls, _coll_cruises(colls)


def _southern():
    colls = Collection.query().filter(Collection.oceans.contains(u'southern')).all()
    colls = _sort_results(colls)
    return colls, _coll_cruises(colls)


def ocean_show(request):
    ocean = request.matchdict.get('ocean', '').lower()
    if ocean not in allowed_oceans:
        if ocean in static_oceans:
            request.matchdict = {'subpath': [u'ocean/%s.html' % ocean]}
            return catchall_static(request)
        raise HTTPNotFound()

    collections = None
    if ocean == 'arctic':
        collections, coll_cruises = _arctic()
    elif ocean == 'indian':
        collections, coll_cruises = _indian()
    elif ocean == 'southern':
        collections, coll_cruises = _southern()

    if not collections:
        raise HTTPNotFound()

    return {
        'ocean': ocean.capitalize(),
        'collections': collections,
        'coll_cruises': coll_cruises,
    }
