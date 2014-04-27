from datetime import datetime
from cgi import FieldStorage

from geojson import LineString as gj_LineString

from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound, HTTPNoContent, HTTPUnauthorized
from pyramid.url import current_route_url

from webhelpers. paginate import Page

from webob.multidict import MultiDict

from pycchdo.models import Obj
from pycchdo.models.types import *
from pycchdo.models.file_types import DataFileTypes
from pycchdo.util import guess_mime_type, collapse_dict
from pycchdo.log import ColoredLogger, DEBUG


log = ColoredLogger(__name__)
log.setLevel(DEBUG)


__CONSTANTS__ = [
    'FILE_GROUPS', 'FILE_GROUPS_SELECT', 'PLEASE_SIGNIN_MESSAGE', 
]


__all__ = [
    'log',
    'collapse_dict', 'http_method', 'paged', 'text_to_obj', 'str_to_track',
    'file_response', ] + __CONSTANTS__


PLEASE_SIGNIN_MESSAGE = """\
    Please help us better process your data by leaving a way to contact you."""


FILE_GROUPS = MultiDict([
    ['Exchange', ['bottle_exchange', 'bottle_zip_exchange', 'ctd_zip_exchange']],
    ['NetCDF', ['bottle_zip_netcdf', 'ctd_zip_netcdf']],
    ['WOCE', ['bottle_woce', 'ctd_zip_woce', 'sum_woce']],
    ['Map', ['map_thumb', 'map_full']],
    ['Documentation', ['doc_txt', 'doc_pdf']],
])


FILE_GROUPS_SELECT = []
for k, v in FILE_GROUPS.items():
    FILE_GROUPS_SELECT.append(
        ([(x, DataFileTypes.human_names[x]) for x in v], k))
FILE_GROUPS_SELECT.append('Other')


def http_method(request):
    try:
        return request.params['_method']
    except KeyError:
        return request.method


def paged(request, l):
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 30))
    def page_url(page):
        query = request.params.copy()
        query['page'] = page
        query['items_per_page'] = items_per_page
        return current_route_url(request, _query=query)
    return Page(
        l, current_page, items_per_page=items_per_page, url=page_url)


def _unescape(s, escape='\\'):
    n = s.find(escape)
    while n > -1:
        s = s[:n] + s[n + 1:]
        n = s.find(escape, n + 1)
    return s


_possible_date_formats = [
    '%Y-%m-%dT%H:%M:%S.%f%z', 
    '%Y-%m-%dT%H:%M:%S', 
    '%Y-%m-%dT%H:%M', 
    '%Y-%m-%d %H:%M:%S', 
    '%Y-%m-%d %H:%M', 
    '%Y-%m-%d', 
]


def _obj_exists(id):
    """Check that the id refers to a valid Obj.

    """
    if Obj.query().get(id):
        return id
    else:
        raise ValueError('%s is not a valid object' % id)


def text_to_obj(value, text_type=Unicode):
    """Convert some text into the given type of object.

    """
    if type(value) is FieldStorage:
        return value

    if isinstance(text_type, list):
        for t in text_type:
            try:
                return text_to_obj(value, t)
            except ValueError:
                pass

    if text_type == Unicode:
        return value.strip()
    if text_type == DateTime:
        for df in _possible_date_formats:
            try:
                return datetime.strptime(value, df)
            except ValueError:
                pass
        return None
    if text_type == TextList:
        return [_unescape(x.strip()) for x in value.split(',')]
    if text_type == ID:
        if not value:
            return None
        return _obj_exists(value)
    if text_type == IDList:
        return [_obj_exists(x.strip()) for x in value.split(',')]
    if text_type == File:
        return value

    raise ValueError(u'Unknown text type: {0}'.format(text_type))


def str_to_track(s):
    coords = [[float(y) for y in x.split(',')] for x in s.split()]
    return gj_LineString(coords)


def _humanize(obj):
    if type(obj) == list:
        if len(obj) == 1:
            return _humanize(obj[0])
        leader = ', '.join([_humanize(o) for o in obj[:-1]])
        if len(obj) > 2:
            leader += ','
        return leader + ' and ' + _humanize(obj[-1])
    return str(obj)


def file_response(request, file, disposition='inline'):
    if disposition not in ['inline', 'attachment']:
        raise ValueError('Disposition must be in %r' % disposition)

    if file is None:
        raise HTTPNoContent()

    resp = Response(conditional_response=True)

    # Caching
    try:
        resp.etag = file.md5
    except AttributeError:
        pass
    try:
        resp.last_modified = file.upload_date
    except AttributeError:
        pass
    # For data files, there isn't really an expiry date.
    # Let's set one for almost a month so we have the opportunity to change it.
    resp.cache_control.max_age = 60 * 60 * 24 * 30

    try:
        resp.app_iter = file.file
    except AttributeError:
        resp.app_iter = file
    try:
        resp.content_length = file.length
    except AttributeError:
        pass
    try:
        # TODO TEST that this must be string.
        if file.content_type is not None and file.content_type != 'None':
            resp.content_type = str(file.content_type)
        else:
            resp.content_type = guess_mime_type(file.name)
    except AttributeError:
        pass
    try:
        resp.content_disposition = '{disposition}; filename="{name}"'.format(
            disposition=disposition, name=file.name)
    except AttributeError:
        resp.content_disposition = disposition

    # HACK detect corrupted files (data in fs missing) before the framework gets
    # handed the file to send
    try:
        resp.app_iter.read(1)
        resp.app_iter.seek(0)
    except Exception, e:
        log.error('Missing file {0}:\n{1!r}'.format(file.id, e))
        raise HTTPNotFound()

    return resp


def notfound_view(request):
    request.response.status_int = 404
    return {
        'errno': '404',
        'errstr': 'Not Found',
        'errmsg': 'The requested resource could not be found.',
    }


def unauthorized_view(request):
    request.response.status_int = 401
    return {
        'errno': '401',
        'errstr': 'Unauthorized',
        'errmsg': "I'm sorry. I can't let you do that.",
    }


def server_error_view(request):
    request.response.status_int = 500
    return {
        'errno': '500',
        'errstr': 'Internal Server Error',
        'errmsg': ("Oops! Sorry, that's an error. We have been notified and "
                   "will take a look shortly."),
    }
