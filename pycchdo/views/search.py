import urllib

from pyramid.response import Response
from pyramid.httpexceptions import HTTPSeeOther, HTTPMovedPermanently, HTTPBadRequest

from ..models import search as searcher


def advanced_search(request):
    """ The advanced search form """
    return {}


def search_results(request):
    query = request.params.get('query', None)

    request.session['query'] = query

    if not query:
        return HTTPSeeOther(location='/search/advanced')
    return {'query': query,
            'results': searcher.search(unicode(query))}


def search(request):
    params = request.str_params

    if not params: 
        return HTTPMovedPermanently(location='/search/advanced') 

    query = ''
    if 'query' in params:
        return HTTPSeeOther(location='/search/results?query=%s'%(params['query']))
    if params.get('line'): 
        query = query + "line:" + urllib.quote_plus(params['line']) + '+'
    if params.get('expocode'): 
        query = query + "expocode:" + urllib.quote_plus(params['expocode']) + '+'
    if params.get('ship'):
        query = query + "ship:" + urllib.quote_plus(params['ship']) + '+'
    if params.get('people'):
        query = query + "people:" + urllib.quote_plus(params['people']) + '+'
    if params.get('country'):
        query = query + "country:" + urllib.quote_plus(params['country']) + '+'
    if params.get('search_date_min'):
        query = query + "from:" + urllib.quote_plus(params['search_date_min']) + '+'
    if params.get('search_date_max'):
        query = query + "to:" + urllib.quote_plus(params['search_date_min']) + '+'
    return HTTPSeeOther(location='/search/results?query=%s'%(query))

