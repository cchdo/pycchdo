import os

import transaction

from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.httpexceptions import \
    HTTPNotFound, HTTPBadRequest, HTTPSeeOther, HTTPUnauthorized

import pycchdo.models as models
from pycchdo.models import (
    Cruise, Parameter, Unit, disjoint_load_obj, disjoint_load_list,
    )
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

try:
    with open(os.path.join(_static_root, 'transparent.gif')) as _f:
        _transparent = _f.read()
    _transparent_response = Response(
        content_type='image/gif', body=_transparent)
except IOError:
    _transparent_response = HTTPNotFound()


def favicon(context, request):
    return _favicon_response


def robots(context, request):
    return _robots_response


def transparent(context, request):
    return _transparent_response


def empty_view(context, request):
    return {}


find_menu = empty_view
search_menu = empty_view
submit_menu = empty_view
information_menu = empty_view
tools_menu = staff_signin_required(empty_view)


def home(request):
    num_updates = 8
    num_upcoming = 2
    updated = Cruise.updated(num_updates)
    upcoming = Cruise.upcoming(num_upcoming)

    return {
        'updated': updated,
        'upcoming': upcoming,
    }


def project_carina(request):
    collection = models.Collection.get_one_by_attrs({'names': 'CARINA'})
    if collection:
        return {'cruises': collection.cruises()}
    else:
        return {'cruises': []}


def _get_params_for_order(order):
    try:
        param_order = models.ParameterOrder.get_one_by_attrs({'name': order})
        disjoint_load_obj([param_order], 'order', Parameter, single=False)
        order = param_order.order
        disjoint_load_list(order, 'aliases')
        disjoint_load_list(order, 'bounds')
        disjoint_load_obj(order, 'unit', Unit, single=True)
        return order
    except (AttributeError, IndexError):
        return []


def parameters(request):
    primary = _get_params_for_order('CCHDO Primary Parameters')
    secondary = _get_params_for_order('CCHDO Secondary Parameters')
    tertiary = _get_params_for_order('CCHDO Tertiary Parameters')
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

    try:
        parameter = Parameter.query().get(parameter_id)
    except Exception, e:
        transaction.begin()
        parameter = Parameter.get_one_by_attrs({'name': parameter_id})
    if not parameter:
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
    """Returns data."""
    id = request.matchdict['data_id']

    try:
        data = models._Attr.query().get(id)
    except TypeError:
        raise HTTPNotFound()

    if not data:
        try:
            data = models.Submission.query().get(id)
        except ValueError:
            raise HTTPNotFound()

    if not data:
        raise HTTPNotFound()

    # Ensure the HTTP session is authorized to read the data
    perms = None
    try:
        perms = data.permissions_read
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

    return file_response(request, data.value)


def catchall_static(request):
    """ Wraps any static templates with the layout """
    try:
        subpath = os.path.join(*request.matchdict['subpath'])
    except TypeError:
        raise HTTPNotFound()

    project_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    static_path = os.path.join('templates', 'static')

    path = os.path.join(project_path, static_path, subpath)
    relpath = os.path.join(static_path, subpath)

    try:
        if os.path.isfile(path):
            return render_to_response(relpath, {}, request)
    except TypeError:
        raise HTTPNotFound()
    raise HTTPNotFound()
