from pyramid.httpexceptions import HTTPMovedPermanently, HTTPNotFound

import pycchdo.models as models

from . import _file_response


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
