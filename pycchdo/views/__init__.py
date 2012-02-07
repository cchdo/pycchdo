import os
from datetime import datetime
import cgi
import geojson

from pyramid.renderers import render_to_response, get_renderer
from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPSeeOther, \
    HTTPNoContent
from pyramid.url import current_route_url

from webhelpers import paginate

from webob.multidict import MultiDict

import pycchdo.models as models
from pycchdo.models.models import data_file_human_names
import pycchdo.helpers as h
from pycchdo.views.session import require_signin


_views = ['favicon', 'robots', 'home', 'get_menu', 'search_menu', 'give_menu',
          'information_menu', 'tools_menu', 'project_carina', 'parameters',
          'contributions', 'parameter_show', 'data', 'catchall_static', ]


__all__ = [
    '_collapsed_dict', '_http_method', '_paged', '_unescape', 'text_to_obj',
    'str_to_track', '_file_response', 'FILE_GROUPS', 'FILE_GROUPS_SELECT',
    'PLEASE_SIGNIN_MESSAGE', ] + _views


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
            # TODO test for list condition
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


_possible_data_formats = [
    '%Y-%m-%dT%H:%M:%S.%f%z', 
    '%Y-%m-%dT%H:%M:%S', 
    '%Y-%m-%dT%H:%M', 
    '%Y-%m-%d', 
]


def _ensure_object_id(x):
    try:
        return models.ensure_objectid(x)
    except ValueError:
        return None


def text_to_obj(value, text_type='text'):
    if type(value) is cgi.FieldStorage:
        return value
    if text_type == 'text':
        return value.strip()
    if text_type == 'datetime':
        for df in _possible_data_formats:
            try:
                return datetime.strptime(value, df)
            except ValueError:
                pass
        return None
    if text_type == 'text_list':
        return [_unescape(x.strip()) for x in value.split(',')]
    if text_type == 'id':
        return _ensure_object_id(value)
    if text_type == 'id_list':
        return [_ensure_object_id(x.strip()) for x in value.split(',')]


def str_to_track(s):
    coords = [[float(y) for y in x.split(',')] for x in s.split()]
    return geojson.LineString(coords)


_static_root = os.path.join(os.path.dirname(__file__), '..', 'static')


try:
    _favicon = open(os.path.join(_static_root, 'favicon.ico')).read()
    _favicon_response = Response(content_type='image/x-icon', body=_favicon)
except IOError:
    _favicon_response = HTTPNotFound()

try:
    _robots = open(os.path.join(_static_root, 'robots.txt')).read()
    _robots_response = Response(content_type='text/plain', body=_robots)
except IOError:
    _robots_response = HTTPNotFound()


def favicon(context, request):
    return _favicon_response


def robots(context, request):
    return _robots_response


def _empty_view(context, request):
    return {}


get_menu = _empty_view
search_menu = _empty_view
give_menu = _empty_view
information_menu = _empty_view
tools_menu = _empty_view


def _humanize(obj):
    if type(obj) == list:
        if len(obj) == 1:
            return _humanize(obj[0])
        leader = ', '.join([_humanize(o) for o in obj[:-1]])
        if len(obj) > 2:
            leader += ','
        return leader + ' and ' + _humanize(obj[-1])
    return str(obj)


def home(request):
    num_updates = 2
    updated = models.Cruise.updated(num_updates)
    upcoming = models.Cruise.upcoming(num_updates)

    return {
        'updated': updated,
        'upcoming': upcoming,
    }


def project_carina(request):
    collections = models.Collection.get_by_attrs(names='CARINA')
    if len(collections) > 0:
        return {'cruises': collections[0].cruises()}
    else:
        return {'cruises': []}


def parameters(request):
    def get_params_for_order(order):
        try:
            return models.ParameterOrder.get_by_attrs({'name': order})[0].order
        except IndexError:
            return []
    primary = get_params_for_order('CCHDO Primary Parameters')
    secondary = get_params_for_order('CCHDO Secondary Parameters')
    tertiary = get_params_for_order('CCHDO Tertiary Parameters')
    return {'parameters': {1: primary, 2: secondary, 3: tertiary}}


def contributions(request):
    from pycchdo.views.cruise import _contributions, _contribution_kmzs
    from pycchdo.views.search_map import index as map_index
    contributions = _contribution_kmzs(request) + _contributions(request)
    commands = ','.join(['kmllink:%s' % url for url in contributions] + 
                        ['map_type:earth'])
    return map_index(request, commands)


def parameter_show(request):
    try:
        parameter_id = request.matchdict['parameter_id']
    except KeyError:
        return HTTPBadRequest()

    parameter = models.Parameter.get_id(parameter_id)
    if not parameter:
        parameters = models.Parameter.get_by_attrs(name=parameter_id)
        if len(parameters) > 0:
            parameter = parameters[0]
        else:
            return HTTPNotFound()

    response = {'parameter': {
        'name': parameter.get('name', ''),
        'aliases': filter(None,
            [parameter.get('name_netcdf'), parameter.get('full_name')] + \
            parameter.get('aliases')),
        'format': parameter.get('format', ''),
        'bounds': parameter.get('bounds', []),
        },
        'description': parameter.get('description', None),
    }
    units = parameter.units
    if units:
        response['parameter']['units'] = {
            'unit': {
                'def': units.get('name'),
                'aliases': [
                    {'name': {'singular': units.get('mnemonic')}}
                ]
            }
        }
    return response


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
        # TODO test that this must be string.
        resp.content_type = str(file.content_type)
    except AttributeError:
        pass
    try:
        resp.content_disposition = '{disposition}; filename="{name}"'.format(
            disposition=disposition, name=file.name)
    except AttributeError:
        resp.content_disposition = disposition
    return resp


def data(request):
    """ Returns data """
    id = request.matchdict['data_id']
    try:
        data = models._Attr.get_id(id)
    except ValueError:
        return HTTPNotFound()

    if not data:
        try:
            data = models.Submission.get_id(id)
        except ValueError:
            return HTTPNotFound()

    if not data:
        try:
            data = models.ArgoFile.get_id(id)
        except ValueError:
            return HTTPNotFound()

    if not data:
        return HTTPNotFound()

    return _file_response(data.file)


def catchall_static(request):
    """ Wraps any static templates with the layout """
    subpath = os.path.join(*request.matchdict['subpath'])

    project_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    static_path = os.path.join('templates', 'static')

    path = os.path.join(project_path, static_path, subpath)
    relpath = os.path.join(static_path, subpath)

    if os.path.isfile(path):
        return render_to_response(relpath, {}, request)
    return HTTPNotFound()
