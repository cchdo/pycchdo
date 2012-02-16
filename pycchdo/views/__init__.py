from datetime import datetime
import cgi
import geojson

from pyramid.response import Response
from pyramid.httpexceptions import HTTPNoContent
from pyramid.url import current_route_url

from webhelpers import paginate

from webob.multidict import MultiDict

import pycchdo.models as models
from pycchdo.models.models import data_file_human_names


__all__ = [
    '_collapsed_dict', '_http_method', '_paged', '_unescape', 'text_to_obj',
    'str_to_track', '_file_response', 'FILE_GROUPS', 'FILE_GROUPS_SELECT',
    'PLEASE_SIGNIN_MESSAGE', ]


PLEASE_SIGNIN_MESSAGE = """\
    Please help us better process your data by leaving a way to contact you."""


FILE_GROUPS = MultiDict([
    ['Exchange', ['bottle_exchange', 'bottlezip_exchange', 'ctdzip_exchange']],
    ['NetCDF', ['bottlezip_netcdf', 'ctdzip_netcdf']],
    ['WOCE', ['bottle_woce', 'ctdzip_woce', 'sum_woce']],
    ['Map', ['map_thumb', 'map_full']],
    ['Documentation', ['doc_txt', 'doc_pdf']],
])


FILE_GROUPS_SELECT = []
for k, v in FILE_GROUPS.items():
    FILE_GROUPS_SELECT.append(
        ([(x, data_file_human_names[x]) for x in v], k))
FILE_GROUPS_SELECT.append('Other')


def _collapsed_dict(d, n=None):
    """ Collapses a dict recursively into the value n if it has no values that
    are not n """
    e = {}
    for k, v in d.items():
        if type(v) is dict:
            # recurse into sub-dicts
            v = _collapsed_dict(v, n)
        if type(v) is list:
            # TODO TEST for list condition
            # do not recurse into lists if n is None
            if n is None and not v:
                v = n
        if v != n:
            e[k] = v
    if len(e) < 1:
        return n
    return e


def _http_method(request):
    try:
        return request.params['_method']
    except KeyError:
        return request.method


def _paged(request, l):
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 50))
    def page_url(page):
        query = request.params.copy()
        query['page'] = page
        query['items_per_page'] = items_per_page
        return current_route_url(request, _query=query)
    return paginate.Page(
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


def _ensure_id(x):
    """ Attempts to convert the argument into an ObjectId
        If that fails consider the argument as an id

        Checks if the id exists as an Obj.

        If the check fails, raise ValueError

    """
    try:
        id = models.guess_objectid(x)
    except models.InvalidId:
        id = x
    if models.Obj.find_one(id, limit=1):
        return id
    else:
        raise ValueError('%s is not a valid object' % id)


def text_to_obj(value, text_type='text'):
    if type(value) is cgi.FieldStorage:
        return value
    if text_type == 'text':
        return value.strip()
    if text_type == 'datetime':
        for df in _possible_date_formats:
            try:
                return datetime.strptime(value, df)
            except ValueError:
                pass
        return None
    if text_type == 'text_list':
        return [_unescape(x.strip()) for x in value.split(',')]
    if text_type == 'id':
        if not value:
            return None
        return _ensure_id(value)
    if text_type == 'id_list':
        return [_ensure_id(x.strip()) for x in value.split(',')]


def str_to_track(s):
    coords = [[float(y) for y in x.split(',')] for x in s.split()]
    return geojson.LineString(coords)


def _humanize(obj):
    if type(obj) == list:
        if len(obj) == 1:
            return _humanize(obj[0])
        leader = ', '.join([_humanize(o) for o in obj[:-1]])
        if len(obj) > 2:
            leader += ','
        return leader + ' and ' + _humanize(obj[-1])
    return str(obj)


def _file_response(file, disposition='inline'):
    if disposition not in ['inline', 'attachment']:
        raise ValueError()

    if file is None:
        return HTTPNoContent()

    resp = Response()
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
        resp.content_type = str(file.content_type)
    except AttributeError:
        pass
    try:
        resp.content_disposition = '{disposition}; filename="{name}"'.format(
            disposition=disposition, name=file.name)
    except AttributeError:
        resp.content_disposition = disposition
    return resp
