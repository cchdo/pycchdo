import logging
import urllib
import re

from pyramid.response import Response
from pyramid.httpexceptions import HTTPSeeOther, HTTPMovedPermanently, HTTPBadRequest

from pycchdo.views import _collapsed_dict
from pycchdo.views.cruise import _cruise_to_json


def advanced_search(request):
    """ The advanced search form """
    return {}


def search_results(request):
    query = request.params.get('query', None)

    request.session['query'] = query

    if not query:
        raise HTTPSeeOther(location=request.route_path('advanced_search'))
    try:
        results = _collapsed_dict(request.search_index.search(unicode(query)))
    except Exception, e:
        logging.error('Search failed: %s' % e)
        results = {'cruise': []}
    return {
        'query': query,
        'results': results
    }


def search_results_json(request):
    query = request.params.get('query', None)
    if not query:
        raise HTTPBadRequest()
    try:
        results = request.search_index.search(unicode(query))
    except Exception, e:
        logging.error('Search failed: %s' % e)
        results = {'cruise': []}

    cruise_jsons = map(_cruise_to_json, results['cruise'])
    for person, cruises in results['person'].items():
        cruise_jsons.extend(map(_cruise_to_json, cruises))
    return {
        'query': query,
        'results': cruise_jsons,
    }


def _quote(str):
    """ URL quoted keyword argument for query """
    if re.search('\s', str):
        str = '"%s"' % str
    return urllib.quote_plus(str)


def search(request):
    params = request.params

    if not params: 
        raise HTTPMovedPermanently(location='/search/advanced') 

    queries = []
    if 'query' in params:
        raise HTTPSeeOther(location='/search/results?query=%s'%(params['query']))
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
    raise HTTPSeeOther(location='/search/results?query=%s'%(query))

