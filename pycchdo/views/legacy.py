from pyramid.httpexceptions import HTTPMovedPermanently, HTTPNotFound, HTTPSeeOther

from pycchdo.models.serial import FSFile


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


def list_files(request):
    log.error(u'List files accessed')
    # TODO implement a file manifest system
    raise HTTPNotFound()


def data_df(request):
    """Serve legacy data files that used to be served from /data prefix."""
    url = '/' + '/'.join(['data'] + list(request.matchdict['rest']))

    fsf = FSFile.query().filter(FSFile.import_path == url).first()

    if not fsf:
        raise HTTPNotFound()
    raise HTTPMovedPermanently(location='/data/b/{0}'.format(fsf.id))


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


def data_history(request):
    try:
        expocode = request.params['ExpoCode']
        raise HTTPSeeOther(
            location=request.route_url(
                'cruise_show', cruise_id=expocode, _anchor='history'))
    except KeyError, err:
        raise HTTPSeeOther(
            location=request.route_path('advanced_search'))


def groups(request):
    group = request.params['id']
    raise HTTPMovedPermanently(
        location=request.route_path(
            'search_results', _query=[('query', 'group:{0}'.format(group))]))


table = groups


def carina(request):
    raise HTTPMovedPermanently(location=request.route_path('project_carina'))
