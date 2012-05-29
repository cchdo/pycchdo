import os

from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.httpexceptions import \
    HTTPNotFound, HTTPBadRequest, HTTPSeeOther, HTTPUnauthorized

import pycchdo.models as models
from pycchdo.views import *
from pycchdo.views.staff import staff_signin_required
from pycchdo.views.cruise import _contributions, _contribution_kmzs
from pycchdo.views.search_map import index as map_index


__all__ = [
    'favicon', 'robots', 'home', 'find_menu', 'search_menu', 'submit_menu',
    'information_menu', 'tools_menu', 'project_carina', 'parameters',
    'contributions', 'parameter_show', 'data', 'catchall_static',
]


_static_root = os.path.join(os.path.dirname(__file__), '..', 'static')


try:
    with open(os.path.join(_static_root, 'favicon.ico')) as _f:
        _favicon = _f.read()
    _favicon_response = Response(content_type='image/x-icon', body=_favicon)
except IOError:
    _favicon_response = HTTPNotFound()

try:
    with open(os.path.join(_static_root, 'robots.txt')) as _f:
        _robots = _f.read()
    _robots_response = Response(content_type='text/plain', body=_robots)
except IOError:
    _robots_response = HTTPNotFound()


def favicon(context, request):
    return _favicon_response


def robots(context, request):
    return _robots_response


def empty_view(context, request):
    return {}


find_menu = empty_view
search_menu = empty_view
submit_menu = empty_view
information_menu = empty_view
tools_menu = staff_signin_required(empty_view)


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
    contributions = _contribution_kmzs(request) + _contributions(request)
    commands = ','.join(['kmllink:%s' % url for url in contributions] + 
                        ['map_type:earth'])
    return map_index(request, commands)


def parameter_show(request):
    try:
        parameter_id = request.matchdict['parameter_id']
    except KeyError:
        raise HTTPBadRequest()

    parameter = models.Parameter.get_id(parameter_id)
    if not parameter:
        parameters = models.Parameter.get_by_attrs(name=parameter_id)
        if len(parameters) > 0:
            parameter = parameters[0]
        else:
            raise HTTPNotFound()

    response = {'parameter': {
        'name': parameter.get('name', ''),
        'aliases': filter(None,
            [parameter.get('name_netcdf'), parameter.get('full_name')] + \
             parameter.aliases),
        'format': parameter.get('format', ''),
        'bounds': parameter.bounds,
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


def data(request):
    """ Returns data """
    id = request.matchdict['data_id']
    try:
        data = models._Attr.get_id(id)
    except ValueError:
        raise HTTPNotFound()

    if not data:
        try:
            data = models.Submission.get_id(id)
        except ValueError:
            raise HTTPNotFound()

    if not data:
        try:
            data = models.ArgoFile.get_id(id)
        except ValueError:
            raise HTTPNotFound()

    if not data:
        raise HTTPNotFound()

    # Ensure the session is authorized to read the data
    perms = None
    try:
        perms = data.permissions['read']
    except (KeyError, AttributeError):
        pass
    if perms:
        try:
            if not request.user.is_authorized(perms):
                raise HTTPUnauthorized()
        except AttributeError:
            raise HTTPUnauthorized()
    if not data.judgment_stamp and not request.user:
        raise HTTPUnauthorized()

    return file_response(request, data.file)


def catchall_static(request):
    """ Wraps any static templates with the layout """
    subpath = os.path.join(*request.matchdict['subpath'])

    project_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    static_path = os.path.join('templates', 'static')

    path = os.path.join(project_path, static_path, subpath)
    relpath = os.path.join(static_path, subpath)

    if os.path.isfile(path):
        return render_to_response(relpath, {}, request)
    raise HTTPNotFound()
