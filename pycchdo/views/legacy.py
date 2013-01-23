from pyramid.httpexceptions import HTTPMovedPermanently, HTTPNotFound, HTTPSeeOther

import pycchdo.models as models


def map_search(request):
    raise HTTPMovedPermanently(
        location=request.route_path('search_map'))


def basin(request):
    raise HTTPMovedPermanently(
        location=request.route_path('basin_show',
                                    basin=request.matchdict.get('basin')))


def add_extension(request, ext='html'):
    raise HTTPMovedPermanently(
        location=u'%s.%s?%s' % (request.path, ext, request.query_string))


def data_access(request):
    raise HTTPMovedPermanently(location=request.route_path('advanced_search'))


def data_access_show_cruise(request):
    expocode = request.params['ExpoCode']
    raise HTTPMovedPermanently(location='/cruise/%s' % expocode)


def data_df(request):
    """ Serve legacy data files that used to be served from /data prefix
    """
    url = '/' + '/'.join(['data'] + list(request.matchdict['rest']))

    attr = models._Attr.get_one({'import_filepath': url})

    if not attr:
        raise HTTPNotFound()
    raise HTTPMovedPermanently(location='/data/b/%s' % attr.id)


def parameter_descriptions(request):
    raise HTTPMovedPermanently(location=request.route_path('parameters'))


static_policies_parameters = parameter_descriptions


def static_metermap(request):
    raise HTTPMovedPermanently(location='/maps/metermap.html')


def static_policies_name(request):
    raise HTTPMovedPermanently(location='/policies/woce_name.html')


def submissions(request):
    raise HTTPMovedPermanently(location=request.route_path('staff_submissions'))


def queue(request):
    raise HTTPMovedPermanently(location=request.route_path('staff_moderation'))


def groups(request):
    group = request.params['id']

    # TODO Attempt to find collection page.
    raise HTTPSeeOther(
        location=request.route_path('collection_show', collection_id=1))
