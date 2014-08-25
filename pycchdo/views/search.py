from datetime import datetime
from urllib import quote_plus
from re import search as re_search
from traceback import format_exc

from pyramid.response import Response
from pyramid.httpexceptions import HTTPSeeOther, HTTPBadRequest

from pycchdo.models.searchsort import sort_results
from pycchdo.views.cruise import _cruise_to_json
from pycchdo.log import getLogger, DEBUG


log = getLogger(__name__)
log.setLevel(DEBUG)


def advanced_search(request):
    """ The advanced search form """
    return {}


def search_results(request):
    query = request.params.get('query', None)
    orderby = request.params.get('orderby', 'date_start')
    expanded = request.params.get('expanded', '')

    request.session['query'] = query
    request.session['query_orderby'] = orderby

    if not query:
        raise HTTPSeeOther(location=request.route_path('advanced_search'))
    try:
        results = sort_results(
            request.search_index.search(unicode(query)),
            orderby=orderby)
    except Exception:
        log.error('Search failed: {0}'.format(format_exc()))
        results = {}
    return {
        'expanded': expanded,
        'query': query,
        'results': results,
    }


def search_results_json(request):
    query = request.params.get('query', None)
    orderby = request.params.get('orderby', 'date_start')
    if not query:
        raise HTTPBadRequest()
    try:
        results = sort_results(
            request.search_index.search(unicode(query)),
            orderby=orderby)
    except Exception, err:
        log.error('Search failed: {0}'.format(format_exc()))
        results = {}

    cruises = results.get('cruise', [])
    for key, value in results.items():
        if key in ('cruise', 'note'):
            continue
        for obj, obj_cruises in value.items():
            cruises.extend(obj_cruises)
    cruise_jsons = map(_cruise_to_json, cruises)
    return {
        'query': query,
        'results': cruise_jsons,
    }


def _quote(s):
    """ URL quoted keyword argument for query """
    if re_search('\s', s):
        str = '"{0}"'.format(s)
    return quote_plus(s)


def search(request):
    params = request.params

    if not params: 
        raise HTTPSeeOther(
            location=request.route_path('advanced_search')) 

    queries = []
    if 'query' in params:
        raise HTTPSeeOther(
            location='/search/results?query={0}'.format(params['query']))
    if params.get('line'): 
        queries.append("line:" + _quote(params['line']))
    if params.get('expocode'): 
        queries.append("expocode:" + _quote(params['expocode']))
    if params.get('ship'):
        queries.append("ship:" + _quote(params['ship']))
    if params.get('people'):
        queries.append("people:" + _quote(params['people']))
    if params.get('country'):
        queries.append("country:" + _quote(params['country']))
    if params.get('search_date_min'):
        queries.append("from:" + _quote(params['search_date_min']))
    if params.get('search_date_max'):
        queries.append("to:" + _quote(params['search_date_max']))
    query = '+'.join(queries)
    raise HTTPSeeOther(location='/search/results?query={0}'.format(query))

