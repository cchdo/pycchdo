import os.path
import re

from pyramid.request import Request
from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound
from . import catchall_static
import pycchdo.models as models


static_basins = ['atlantic', 'pacific', ]
allowed_basins = ['arctic', 'indian', 'southern', ]
basins = allowed_basins + static_basins


def _arctic():
    default = []
    collections = models.Collection.get_by_attrs(
        names=re.compile('.*arctic.*', re.IGNORECASE))
    woce_collections = set()
    for coll in collections:
        for c in coll.cruises():
            woce_collections |= set(c.collections_woce_line)

    collections = list(woce_collections)
    collections = filter(lambda c: not re.match('P\d.*', c.name), collections)
    collections = sorted(collections, key=lambda c: c.name)
    return {'default': collections}


def _indian():
    ind = []
    sou = []
    atl = []
    for sgs in models.Collection.get_by_attrs(type='spatial_group'):
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


def _southern():
    sou = models.Collection.get_by_attrs(
        type='WOCE line',
        names=re.compile('S.*', re.IGNORECASE))
    atl = models.Collection.get_by_attrs(
        type='WOCE line',
        names=re.compile('A(R|J|__).*', re.IGNORECASE))
    ind = models.Collection.get_by_attrs(
        type='WOCE line',
        names=re.compile('(I|AIS).*', re.IGNORECASE))
    pac = models.Collection.get_by_attrs(
        type='WOCE line',
        names=re.compile('(P|AAI).*', re.IGNORECASE))

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
            response = catchall_static(request)
            return render_to_response('templates/base.jinja2',
                                      response, request=request)
        return HTTPNotFound()

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
        return HTTPNotFound()

    return {
        'basin': basin.capitalize(),
        'areas': areas,
        'collections': collections,
    }
