import os

from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid
from pyramid.httpexceptions import HTTPUnauthorized, HTTPInternalServerError
from pyramid.exceptions import NotFound

import webhelpers
import webhelpers.html
import webhelpers.html.tags

import geojson

import models
import helpers
from views.basin import basins
from pycchdo.models.search import SearchIndex


class RequestFactory(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            p = models.Person.get_id(userid)
            return p

    @reify
    def search_index(self):
        return self.registry.settings['db.search_index']

    @reify
    def models(self):
        return models


def add_renderer_globals(event):
    # from json import dumps
    # from urllib import quote
    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['h'] = helpers
    event['geojson'] = geojson


def obj_routes(config, obj, plural_obj=None,
               new=False, mergeable=False, editable=False, json_index=False,
               json_show=False, archiveable=False):
    if not plural_obj:
        plural_obj = obj + 's'

    config.add_route(plural_obj,
                     '/{plural_obj}.html'.format(plural_obj=plural_obj))
    config.add_view('pycchdo.views.{obj}.{plural_obj}_index'.format(
        obj=obj, plural_obj=plural_obj), route_name=plural_obj,
        renderer='templates/{obj}/index.jinja2'.format(obj=obj))

    if json_index:
        config.add_route(plural_obj + '_json',
                         '/{plural_obj}.json'.format(plural_obj=plural_obj))
        config.add_view('pycchdo.views.{obj}.{plural_obj}_index_json'.format(
            obj=obj, plural_obj=plural_obj), route_name=plural_obj + '_json',
            renderer='json')

    if json_show:
        config.add_route(
            '{obj}_show_json'.format(obj=obj),
            '/{obj}/{{{obj}_id}}.json'.format(obj=obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_show_json'.format(obj=obj),
            route_name='{obj}_show_json'.format(obj=obj),
            renderer='json')

    config.add_route(
        '{obj}_show'.format(obj=obj), '/{obj}/{{{obj}_id}}'.format(obj=obj))
    config.add_view(
        'pycchdo.views.{obj}.{obj}_show'.format(obj=obj),
        route_name='{obj}_show'.format(obj=obj),
        renderer='templates/{obj}/show.jinja2'.format(obj=obj))

    if archiveable:
        config.add_route(
            '{obj}_archive'.format(obj=obj),
            '/{obj}/{{{obj}_id}}/archive.zip'.format(obj=obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_archive'.format(obj=obj),
            route_name='{obj}_archive'.format(obj=obj))

    if new:
        config.add_route(
            '{obj}_new'.format(obj=obj),
            '/{obj}/{{{obj}_id}}/new'.format(obj=obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_new'.format(obj=obj),
            route_name='{obj}_new'.format(obj=obj),
            renderer='templates/{obj}/new.jinja2'.format(obj=obj))

        config.add_route(
            '{plural_obj}_new'.format(plural_obj=plural_obj),
            '/{plural_obj}/new.html'.format(plural_obj=plural_obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_new'.format(obj=obj),
            route_name='{plural_obj}_new'.format(plural_obj=plural_obj),
            renderer='templates/{obj}/new.jinja2'.format(obj=obj))

    if mergeable:
        config.add_route(
            '{obj}_merge'.format(obj=obj),
            '/{obj}/{{{obj}_id}}/merge'.format(obj=obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_merge'.format(obj=obj),
            route_name='{obj}_merge'.format(obj=obj),
            renderer='templates/{obj}/show.jinja2'.format(obj=obj))

    if editable:
        config.add_route(
            '{obj}_edit'.format(obj=obj),
            '/{obj}/{{{obj}_id}}/edit'.format(obj=obj))
        config.add_view(
            'pycchdo.views.{obj}.{obj}_edit'.format(obj=obj),
            route_name='{obj}_edit'.format(obj=obj),
            renderer='templates/{obj}/show.jinja2'.format(obj=obj))


def route_for_path(config, route_name, path, view_callable):
    config.add_route(route_name, path)
    config.add_view(view_callable, route_name=route_name)


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.

    """
    authentication_policy = AuthTktAuthenticationPolicy(
        settings['key_auth_policy'])
    authorization_policy = ACLAuthorizationPolicy()
    session_factory = UnencryptedCookieSessionFactoryConfig(
        settings['key_session_factory'])
    settings['db.search_index'] = SearchIndex(settings['db_search_index_path'])

    config = Configurator(
        settings=settings,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        request_factory=RequestFactory,
        session_factory=session_factory,
    )

    models.init_conn(settings)

    config.include('pyramid_jinja2')
    config.include('pyramid_mailer')
    config.add_subscriber(add_renderer_globals, BeforeRender)
    config.add_renderer('.html', 'pyramid_jinja2.renderer_factory')
    config.add_renderer('json', 'pycchdo.renderer_factory.json')

    config.add_view('pycchdo.views.notfound_view', context=NotFound, renderer='templates/errors/xxx.jinja2')
    config.add_view('pycchdo.views.unauthorized_view', context=HTTPUnauthorized, renderer='templates/errors/xxx.jinja2')
    config.add_view('pycchdo.views.server_error_view', context=HTTPInternalServerError, renderer='templates/errors/xxx.jinja2')

    # Serve static files from root
    config.add_route('favicon', '/favicon.ico')
    config.add_view('pycchdo.views.toplevel.favicon', route_name='favicon')
    config.add_route('robots', '/robots.txt')
    config.add_view('pycchdo.views.toplevel.robots', route_name='robots')

    config.add_static_view('static', 'pycchdo:static', cache_max_age=60 * 60 * 24 * 30)

    config.add_route('home', '/')
    config.add_view('pycchdo.views.toplevel.home', route_name='home', renderer='templates/home.jinja2')

    config.add_route('get_menu', '/get.html')
    config.add_view('pycchdo.views.toplevel.get_menu', route_name='get_menu',
                    renderer='templates/get.jinja2')

    config.add_route('search_menu', '/search.html')
    config.add_view('pycchdo.views.toplevel.search_menu', route_name='search_menu',
                    renderer='templates/search.jinja2')

    config.add_route('information_menu', '/information.html')
    config.add_view('pycchdo.views.toplevel.information_menu', route_name='information_menu',
                    renderer='templates/information.jinja2')

    config.add_route('give_menu', '/give.html')
    config.add_view('pycchdo.views.toplevel.give_menu', route_name='give_menu',
                    renderer='templates/give.jinja2')

    config.add_route('submit', '/submit.html')
    config.add_view('pycchdo.views.submit.submit', route_name='submit',
                    renderer='templates/submit.jinja2')

    config.add_route('parameters', '/parameters.html')
    config.add_view('pycchdo.views.toplevel.parameters', route_name='parameters',
                    renderer='templates/parameters.jinja2')

    config.add_route('contributions', '/contributions.html')
    config.add_view('pycchdo.views.toplevel.contributions', route_name='contributions',
                    renderer='templates/search/map.jinja2')

    config.add_route('parameter_show', '/parameter/{parameter_id}.json')
    config.add_view('pycchdo.views.toplevel.parameter_show', route_name='parameter_show',
                    renderer='json')

    config.add_route('session', '/session')
    config.add_view('pycchdo.views.session.session_show', route_name='session', renderer='templates/sessions/show.jinja2')
    config.add_route('session_identify', '/session/identify')
    config.add_view('pycchdo.views.session.session_identify', route_name='session_identify', renderer='templates/sessions/identify.jinja2')
    config.add_route('session_new', '/session/new')
    config.add_view('pycchdo.views.session.session_new', route_name='session_new')
    config.add_route('session_delete', '/session/delete')
    config.add_view('pycchdo.views.session.session_delete', route_name='session_delete')

    config.add_route('objs', '/objs')
    config.add_view('pycchdo.views.obj.objs', route_name='objs', renderer='templates/objs/index.jinja2')
    config.add_route('obj_new', '/objs/new')
    config.add_view('pycchdo.views.obj.obj_new', route_name='obj_new', renderer='templates/objs/new.jinja2')
    config.add_route('obj_show', '/obj/{obj_id}')
    config.add_view('pycchdo.views.obj.obj_show', route_name='obj_show', renderer='templates/objs/show.jinja2')
    config.add_route('obj_attrs', '/obj/{obj_id}/a')
    config.add_view('pycchdo.views.obj.obj_attrs', route_name='obj_attrs', renderer='templates/objs/attrs.jinja2')

    config.add_route('obj_attr', '/obj/{obj_id}/a/{key}')
    config.add_view('pycchdo.views.obj.obj_attr', route_name='obj_attr', renderer='templates/objs/attr.jinja2')

    # Need precedence for extension to catch before ending up a cruise identifier
    config.add_route('cruise_kml', '/cruise/{cruise_id}.kml')
    config.add_view('pycchdo.views.cruise.kml', route_name='cruise_kml')
    obj_routes(config, 'cruise', new=True, json_index=True, json_show=True)
    config.add_route('cruise_map_full', '/cruise/{cruise_id}/map_full')
    config.add_view('pycchdo.views.cruise.map_full',
                    route_name='cruise_map_full')
    config.add_route('cruise_map_thumb', '/cruise/{cruise_id}/map_thumb')
    config.add_view('pycchdo.views.cruise.map_thumb',
                    route_name='cruise_map_thumb')
    config.add_route('cruises_archive', '/cruises/archive.zip')
    config.add_view('pycchdo.views.cruise.cruises_archive',
                    route_name='cruises_archive')

    obj_routes(config, 'collection', mergeable=True, editable=True,
               json_index=True, archiveable=True)
    obj_routes(config, 'country', 'countries', mergeable=True, editable=True,
               json_index=True, archiveable=True)
    obj_routes(config, 'person', 'people', mergeable=True, editable=True,
               json_index=True, archiveable=True)
    obj_routes(config, 'institution', mergeable=True, editable=True,
               json_index=True, archiveable=True)
    obj_routes(config, 'ship', mergeable=True, editable=True,
               json_index=True, archiveable=True)

    # Argo Secure File Repository
    config.add_route('argo_index', '/argo.html')
    config.add_view('pycchdo.views.argo.index', route_name='argo_index', renderer='templates/argo/index.jinja2')
    route_for_path(
        config, 'argo_index_no_ext', '/argo',
        'pycchdo.views.legacy.add_extension')
    config.add_route('argo_new', '/argo/new')
    config.add_view('pycchdo.views.argo.new', route_name='argo_new', renderer='templates/argo/new.jinja2')
    config.add_route('argo_entity', '/argo/{id}')
    config.add_view('pycchdo.views.argo.entity', route_name='argo_entity', renderer='templates/argo/show.jinja2')

    # Basin lists
    basins_re = '|'.join(basins)
    config.add_route('basin_show', '/basin/{basin:%s}.html' % basins_re)
    config.add_view('pycchdo.views.basin.basin_show', route_name='basin_show',
                    renderer='templates/basin.jinja2')

    config.add_route('legacy_basin', '/{basin:%s}{ext:|\.html}' % basins_re)
    config.add_view('pycchdo.views.legacy.basin', route_name='legacy_basin')

	# Search routes
    config.add_route('search', '/search.html')
    config.add_view('pycchdo.views.search.search', route_name='search')
    route_for_path(
        config, 'search_no_ext', '/search',
        'pycchdo.views.legacy.add_extension')

    config.add_route('search_results', '/search/results')
    config.add_view('pycchdo.views.search.search_results', route_name='search_results', renderer='templates/search/results.jinja2')

    config.add_route('search_results_json', '/search/results.json')
    config.add_view('pycchdo.views.search.search_results_json',
                    route_name='search_results_json', renderer='json')

    config.add_route('advanced_search', '/search/advanced.html')
    config.add_view('pycchdo.views.search.advanced_search', route_name='advanced_search', renderer='templates/search/advanced.jinja2')
    route_for_path(
        config, 'advance_search_no_ext', '/search/advanced',
        'pycchdo.views.legacy.add_extension')

    # Search map routes
    config.add_route('search_map', '/search/map.html')
    config.add_view('pycchdo.views.search_map.index', route_name='search_map',
                    renderer='templates/search/map.jinja2')
    route_for_path(
        config, 'search_map_no_ext', '/search/map',
        'pycchdo.views.legacy.add_extension')
    config.add_route('search_map_ids', '/search/map/ids')
    config.add_view('pycchdo.views.search_map.ids', route_name='search_map_ids')
    config.add_route('search_map_layer', '/search/map/layer')
    config.add_view('pycchdo.views.search_map.layer',
                    route_name='search_map_layer')

    config.add_route('legacy_map_search', '/map_search')
    config.add_view('pycchdo.views.legacy.map_search', route_name='legacy_map_search')

    # maintain legacy data_access
    route_for_path(config, 'parameter_descriptions',
                   '/parameter_descriptions',
                   'pycchdo.views.legacy.parameter_descriptions')
    route_for_path(config, 'data_access', '/data_access',
                   'pycchdo.views.legacy.data_access')
    route_for_path(config, 'data_access_show_cruise',
                   '/data_access/show_cruise',
                   'pycchdo.views.legacy.data_access_show_cruise')
    route_for_path(config, 'submit_no_ext', '/submit',
                   'pycchdo.views.legacy.add_extension')

    # legacy static files
    route_for_path(config, 'static_metermap', '/metermap.html',
                   'pycchdo.views.legacy.static_metermap')
    route_for_path(config, 'static_policies_parameters', '/policies/parameters.html',
                   'pycchdo.views.legacy.static_policies_parameters')
    route_for_path(config, 'static_policies_name', '/policies/name.html',
                   'pycchdo.views.legacy.static_policies_name')

    # Tools
    config.add_route('tools_menu', '/tools.html')
    config.add_view('pycchdo.views.toplevel.tools_menu', route_name='tools_menu',
                    renderer='templates/tools.jinja2')
    config.add_route('tool_data_cmp', '/tool/data_cmp.html')
    config.add_view('pycchdo.views.tools.data_cmp', route_name='tool_data_cmp',
                    renderer='templates/tool/data_cmp.jinja2')
    config.add_route('tool_visual', '/tool/visual.html')
    config.add_view('pycchdo.views.tools.visual',
                    route_name='tool_visual',
                    renderer='templates/tool/visual.jinja2')
    config.add_route('tool_convert', '/tool/convert.html')
    config.add_view('pycchdo.views.tools.convert',
                    route_name='tool_convert',
                    renderer='templates/tool/convert.jinja2')
    config.add_route('tool_convert_from_to', '/tool/convert')
    config.add_view('pycchdo.views.tools.convert_from_to',
                    route_name='tool_convert_from_to', renderer='json')
    config.add_route('tool_convert_any_to_google_wire', '/tool/convert/any_to_google_wire')
    config.add_view('pycchdo.views.tools.convert_any_to_google_wire',
                    route_name='tool_convert_any_to_google_wire', renderer='json')
    config.add_route('tool_archives', '/tool/archives.html')
    config.add_view('pycchdo.views.tools.archives', route_name='tool_archives',
                    renderer='templates/tool/archives.jinja2')
    config.add_route('tool_dumps', '/tool/dumps.html')
    config.add_view('pycchdo.views.tools.dumps', route_name='tool_dumps',
                    renderer='templates/tool/dumps.jinja2')
    config.add_route('tool_dumps_sqlite', '/tool/dumps.sqlite')
    config.add_view('pycchdo.views.tools.dumps_sqlite',
                    route_name='tool_dumps_sqlite')

    # Staff
    config.add_route('staff_index', '/staff.html')
    config.add_view('pycchdo.views.staff.index', route_name='staff_index', renderer='templates/staff/index.jinja2')
    config.add_route('staff_submissions', '/staff/submissions.html')
    config.add_view('pycchdo.views.staff.submissions', route_name='staff_submissions', renderer='templates/staff/submissions.jinja2')
    config.add_route('staff_moderation', '/staff/moderation.html')
    config.add_view('pycchdo.views.staff.moderation', route_name='staff_moderation', renderer='templates/staff/moderation.jinja2')

    # dynamic static pages
    config.add_route('project_carina', '/project_carina.html')
    config.add_view('pycchdo.views.toplevel.project_carina', route_name='project_carina',
                    renderer='templates/project_carina.jinja2')

    # Serve data blobs
    config.add_route('data', '/data/b/{data_id}*ignore')
    config.add_view('pycchdo.views.toplevel.data', route_name='data')

    # Serve legacy /data prefix data files
    route_for_path(config, 'data_df', '/data/*rest',
                   'pycchdo.views.legacy.data_df')

	# catchall_static must be last route
    config.add_route('catchall_static', '/*subpath')
    config.add_view('pycchdo.views.toplevel.catchall_static', route_name='catchall_static')

    return config.make_wsgi_app()
