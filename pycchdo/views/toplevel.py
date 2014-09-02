import os
from collections import OrderedDict

import transaction

from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.httpexceptions import \
    HTTPNotFound, HTTPBadRequest, HTTPSeeOther, HTTPUnauthorized

from sqlalchemy.orm import noload, joinedload

from jinja2.exceptions import TemplateNotFound

from pycchdo.models.serial import (
    Change, Cruise, Parameter, Unit, ParameterGroup, Collection, 
    Submission, FileHolder,
    )
from pycchdo.models.searchsort import sort_list
from pycchdo.helpers import data_uri
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
    updated = Cruise.updated(num_updates)

    update_map = OrderedDict()

    cruise_ids = set()
    for attr in updated:
        cruise_ids.add(attr.obj_id)

    cruise_id_map = {}
    cruise_query = Cruise.query().filter(Cruise.id.in_(cruise_ids))
    cruise_query = cruise_query.options(
        noload(Cruise.participants), noload(Cruise._aliases),
        noload(Cruise.collections), noload(Cruise.ship),
        noload(Cruise._statuses), noload(Cruise.institutions),
        noload(Cruise.country), joinedload(Cruise.files))
    for cruise in cruise_query.all():
        cruise_id_map[cruise.id] = cruise

    for attr in updated:
        update_map[attr] = cruise_id_map[attr.obj_id]
    return {
        'updated': update_map,
    }


def project_carina(request):
    collection = Collection.query().filter(Collection.names.contains('CARINA')).first()
    if collection:
        cruises = collection.cruises
        cruises = sort_list(cruises, orderby=request.params.get('orderby', ''))
    else:
        cruises = []
    return {'cruises': cruises}


def manifest(request):
    """A text list of files available from us."""
    json = {}
    for cruise in Cruise.query().options(noload('*')).all():
        files = {}
        for key, fattr in cruise.file_attrs.items():
            if key == 'archive' or key.startswith('map'):
                continue
            files[key] = {
                "url": data_uri(fattr),
                "ctime": unicode(fattr.ts_c),
            }
        json[cruise.uid] = files
    return json


def _get_params_for_order(order):
    try:
        param_order = ParameterGroup.query().filter(
            ParameterGroup.name == order).\
            options(joinedload('_order')).first()
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
        parameter = Parameter.query().filter(Parameter.name == parameter_id).first()
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
    data_id = str(request.matchdict['data_id'])
    original = request.params.get('orig', False)

    fht = data_id[0]
    did = data_id[1:]

    try:
        fholder = FileHolder.file_holder(fht).query().get(did)
    except (ValueError, TypeError):
        raise HTTPNotFound()
    if not fholder:
        raise HTTPNotFound()

    # Ensure the HTTP session is authorized to read the data
    try:
        perms = fholder.permissions_read
        try:
            if perms and not request.user.is_authorized(perms):
                raise HTTPUnauthorized()
        except AttributeError:
            raise HTTPUnauthorized()
    except (KeyError, AttributeError):
        pass

    # If fholder is not accepted, only show it to signed in users.
    try:
        if not fholder.is_accepted() and not request.user:
            raise HTTPUnauthorized()
    except AttributeError:
        pass

    if original:
        return file_response(request, fholder.value_original)
    else:
        return file_response(request, fholder.value)


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
        raise HTTPNotFound()
    except (ValueError, TypeError), e:
        log.error(u'Failed rendering catchall static: {0!r}'.format(e))
        raise HTTPNotFound()
    raise HTTPNotFound()
