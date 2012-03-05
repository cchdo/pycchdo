from pyramid.httpexceptions import HTTPMovedPermanently, HTTPNotFound

import pycchdo.models as models


def map_search(request):
    return HTTPMovedPermanently(
        location=request.route_path('search_map'))


def basin(request):
    return HTTPMovedPermanently(
        location=request.route_path('basin_show',
                                    basin=request.matchdict.get('basin')))


def add_extension(request, ext='html'):
    return HTTPMovedPermanently(location=u'%s.%s' % (request.url, ext))


def data_access(request):
    return HTTPMovedPermanently(location='/search/advanced')


def data_access_show_cruise(request):
    expocode = request.params['ExpoCode']
    return HTTPMovedPermanently(location='/cruise/%s' % expocode)


def data_df(request):
    """ Serve legacy data files that used to be served from /data prefix
    """
    url = '/' + '/'.join(['data'] + list(request.matchdict['rest']))

    attr = models._Attr.get_one({'import_filepath': url})

    if not attr:
        return HTTPNotFound()
    return HTTPMovedPermanently(location='/data/b/%s' % attr.id)


def parameter_descriptions(request):
    return HTTPMovedPermanently(location=request.route_path('parameters'))


static_policies_parameters = parameter_descriptions


def static_metermap(request):
    return HTTPMovedPermanently(location='/maps/metermap.html')


def static_policies_name(request):
    return HTTPMovedPermanently(location='/policies/woce_name.html')
