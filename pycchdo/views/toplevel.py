import os

import transaction

from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.httpexceptions import \
    HTTPNotFound, HTTPBadRequest, HTTPSeeOther, HTTPUnauthorized

from jinja2.exceptions import TemplateNotFound

from pycchdo.models.serial import (
    Change, Cruise, Parameter, Unit, ParameterGroup, Collection, 
    Submission,
    )
from pycchdo.models.searchsort import sort_list
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
    collection = Collection.query().filter(Collection._names.any('CARINA')).first()
    if collection:
        cruises = collection.cruises()
        cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    else:
        cruises = []
    return {'cruises': cruises}


def _get_params_for_order(order):
    try:
        param_order = ParameterGroup.query().filter(
            ParameterGroup.name == order).first()
        return list(param_order.order)
    except (AttributeError, IndexError):
        return []


def _parameters():
    primary = _get_params_for_order('CCHDO Primary Parameters')
    secondary = _get_params_for_order('CCHDO Secondary Parameters')
    tertiary = _get_params_for_order('CCHDO Tertiary Parameters')
    return primary, secondary, tertiary


def parameters(request):
    primary, secondary, tertiary = _parameters()
    return {'parameters': {1: primary, 2: secondary, 3: tertiary}}


def parameters_show_json(request):
    primary = _get_params_for_order('CCHDO Primary Parameters')
    secondary = _get_params_for_order('CCHDO Secondary Parameters')
    tertiary = _get_params_for_order('CCHDO Tertiary Parameters')
    return {
        'Primary': primary,
        'Secondary': secondary,
        'Tertiary': tertiary,
    }


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
    return parameter


def contributions(request):
    contributions = _contribution_kmzs(request) + _contributions(request)
    commands = ','.join(['kmllink:%s' % url for url in contributions] + 
                        ['map_type:earth'])
    return map_index(request, commands)


def data(request):
    """Returns data."""
    id = request.matchdict['data_id']
    original = request.params.get('orig', False)

    try:
        data = Change.query().get(id)
    except TypeError:
        raise HTTPNotFound()

    if not data:
        try:
            data = Submission.query().get(id).value
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

    # If data is not accepted, only show it to signed in users.
    if not data.is_accepted() and not request.user:
        raise HTTPUnauthorized()

    if original:
        return file_response(request, data.value_original)
    else:
        return file_response(request, data.value)


def catchall_static(request):
    """Wraps any static templates with the layout."""
    try:
        subpath = os.path.join(*request.matchdict['subpath'])
    except TypeError:
        raise HTTPNotFound()

    static_path = 'static'
    relpath = os.path.join('pycchdo:templates', static_path, subpath)

    try:
        return render_to_response(relpath, {}, request)
    except TemplateNotFound, err:
        log.error(u'template not found: {0}\n{1!r}\n{1}'.format(relpath, err))
        raise
        #raise HTTPNotFound()
    except (ValueError, TypeError), e:
        log.error(u'Failed rendering catchall static: {0!r}'.format(e))
        raise HTTPNotFound()
    raise HTTPNotFound()
