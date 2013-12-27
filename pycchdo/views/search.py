from datetime import datetime
from urllib import quote_plus
from re import search as re_search

from pyramid.response import Response
from pyramid.httpexceptions import HTTPSeeOther, HTTPBadRequest

from pycchdo.util import collapse_dict
from pycchdo.models.searchsort import sort_results
from pycchdo.views.cruise import _cruise_to_json
from pycchdo.log import ColoredLogger, DEBUG


log = ColoredLogger(__name__)
log.setLevel(DEBUG)


def advanced_search(request):
    """ The advanced search form """
    return {}


def search_results(request):
    query = request.params.get('query', None)
    orderby = request.params.get('orderby', '')

    request.session['query'] = query
    request.session['query_orderby'] = orderby

    if not query:
        raise HTTPSeeOther(location=request.route_path('advanced_search'))
    try:
        results = sort_results(
            collapse_dict(request.search_index.search(unicode(query))),
            orderby=orderby)
    except Exception, e:
        log.error('Search failed: %s' % e)
        results = {'cruise': []}
    return {
        'query': query,
        'results': results
    }


def search_results_json(request):
    query = request.params.get('query', None)
    orderby = request.params.get('orderby', '')
    if not query:
        raise HTTPBadRequest()
    try:
        results = sort_results(
            collapse_dict(request.search_index.search(unicode(query))),
            orderby=orderby)
    except Exception, e:
        log.error('Search failed: %s' % e)
        results = {'cruise': []}

    cruise_jsons = map(_cruise_to_json, results.get('cruise', {}))
    for person, cruises in results.get('person', {}).items():
        cruise_jsons.extend(map(_cruise_to_json, cruises))
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

