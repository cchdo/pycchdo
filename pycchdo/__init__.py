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

from sqlalchemy import engine_from_config

from pycchdo import models, helpers
from pycchdo.views.basin import basins
from pycchdo.models import DBSession, FSFile
from pycchdo.models.search import SearchIndex


def create_config(settings):
    authentication_policy = AuthTktAuthenticationPolicy(
        settings['key_auth_policy'])
    authorization_policy = ACLAuthorizationPolicy()
    session_factory = UnencryptedCookieSessionFactoryConfig(
        settings['key_session_factory'])

    settings['db.search_index'] = SearchIndex(settings['db_search_index_path'])

    return Configurator(
        settings=settings,
        request_factory=RequestFactory,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        session_factory=session_factory,
    )


def _configure_bindings(config):
    config.add_jinja2_search_path('pycchdo:templates')


class RequestFactory(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            p = models.Person.query().get(userid)
            return p

    @reify
    def search_index(self):
        return self.registry.settings['db.search_index']

    @reify
    def models(self):
        return models

    @reify
    def db(self):
        return DBSession


def _add_renderer_globals(event):
    # from urllib import quote
    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['h'] = helpers
    event['geojson'] = geojson


def _configure_renderers(config):
    config.add_subscriber(_add_renderer_globals, BeforeRender)
    config.add_renderer('.html', 'pyramid_jinja2.renderer_factory')
    config.add_renderer('json', 'pycchdo.renderer_factory.json')


def _add_error_view(config, view_callable, context,
                   renderer='errors/xxx.jinja2'):
    config.add_view(view_callable, context=context, renderer=renderer)


def _configure_error_views(config):
    _add_error_view(config, 'pycchdo.views.notfound_view', NotFound)
    _add_error_view(config, 'pycchdo.views.unauthorized_view', HTTPUnauthorized)
    _add_error_view(config, 'pycchdo.views.server_error_view', HTTPInternalServerError)


def route_path(config, route_name, path, view_callable, renderer=None):
    config.add_route(route_name, path)
    config.add_view(view_callable, route_name=route_name, renderer=renderer)


def obj_routes(config, obj, plural_obj=None,
               new=False, mergeable=False, editable=False, json_index=False,
               json_show=False, archiveable=False):
    if not plural_obj:
        plural_obj = obj + 's'

    route_path(config, plural_obj,
               '/{0}.html'.format(plural_obj),
               'pycchdo.views.{0}.{1}_index'.format(obj, plural_obj),
               '{0}/index.jinja2'.format(obj))

    if json_index:
        route_path(config, plural_obj + '_json',
                   '/{0}.json'.format(plural_obj), 
                   'pycchdo.views.{0}.{1}_index_json'.format(obj, plural_obj),
                   'json')

    if json_show:
        route_path(config, '{0}_show_json'.format(obj),
                   '/{0}/{{{0}_id}}.json'.format(obj),
                   'pycchdo.views.{0}.{0}_show_json'.format(obj),
                   'json')

    route_path(config, '{0}_show'.format(obj),
               '/{0}/{{{0}_id}}'.format(obj),
               'pycchdo.views.{0}.{0}_show'.format(obj),
               '{0}/show.jinja2'.format(obj))

    if archiveable:
        route_path(config, '{0}_archive'.format(obj),
                   '/{0}/{{{0}_id}}/archive.zip'.format(obj),
                   'pycchdo.views.{0}.{0}_archive'.format(obj))

    if new:
        route_path(config, '{0}_new'.format(obj),
                   '/{0}/{{{0}_id}}/new'.format(obj),
                   'pycchdo.views.{0}.{0}_new'.format(obj),
                   '{0}/new.jinja2'.format(obj))

        route_path(config, '{0}_new'.format(plural_obj),
                   '/{0}/new.html'.format(plural_obj),
                   'pycchdo.views.{0}.{0}_new'.format(obj),
                   '{0}/new.jinja2'.format(obj))

    if mergeable:
        route_path(config, '{0}_merge'.format(obj),
                   '/{0}/{{{0}_id}}/merge'.format(obj),
                   'pycchdo.views.{0}.{0}_merge'.format(obj),
                   '{0}/show.jinja2'.format(obj))

    if editable:
        route_path(config, '{0}_edit'.format(obj),
                   '/{0}/{{{0}_id}}/edit'.format(obj),
                   'pycchdo.views.{0}.{0}_edit'.format(obj),
                   '{0}/show.jinja2'.format(obj))


def _configure_routes(config):
    # Serve static files from root
    route_path(config, 'favicon', '/favicon.ico',
               'pycchdo.views.toplevel.favicon')
    route_path(config, 'robots', '/robots.txt',
               'pycchdo.views.toplevel.robots')

    config.add_static_view(
        'static', 'pycchdo:static', cache_max_age=60 * 60 * 24 * 30)

    route_path(config, 'home', '/',
               'pycchdo.views.toplevel.home', 'home.jinja2')
    route_path(config, 'find_menu', '/find.html',
               'pycchdo.views.toplevel.find_menu', 'find.jinja2')
    route_path(config, 'submit_menu', '/submit_menu.html',
               'pycchdo.views.toplevel.submit_menu', 'submit_menu.jinja2')
    route_path(config, 'information_menu', '/information.html',
               'pycchdo.views.toplevel.information_menu', 'information.jinja2')

    route_path(config, 'submit', '/submit.html',
               'pycchdo.views.submit.submit', 'submit.jinja2')
    route_path(config, 'parameters', '/parameters.html',
               'pycchdo.views.toplevel.parameters', 'parameters.jinja2')
    route_path(config, 'contributions', '/contributions.html',
               'pycchdo.views.toplevel.contributions', 'search/map.jinja2')

    route_path(config, 'parameter_show', '/parameter/{parameter_id}.json',
               'pycchdo.views.toplevel.parameter_show', 'json')

    route_path(config, 'session', '/session',
               'pycchdo.views.session.session_show', 'sessions/show.jinja2')
    route_path(config, 'session_identify', '/session/identify',
               'pycchdo.views.session.session_identify', 'sessions/identify.jinja2')
    route_path(config, 'session_new', '/session/new',
               'pycchdo.views.session.session_new')
    route_path(config, 'session_delete', '/session/delete',
               'pycchdo.views.session.session_delete')

    # TODO REMOVE
    route_path(config, 'objs', '/objs',
               'pycchdo.views.obj.objs', 'objs/index.jinja2')
    route_path(config, 'obj_new', '/objs/new',
               'pycchdo.views.obj.obj_new', 'objs/new.jinja2')
    route_path(config, 'obj_show', '/obj/{obj_id}',
               'pycchdo.views.obj.obj_show', 'objs/show.jinja2')
    route_path(config, 'obj_attrs', '/obj/{obj_id}/a',
               'pycchdo.views.obj.obj_attrs', 'objs/attrs.jinja2')

    route_path(config, 'obj_attr', '/obj/{obj_id}/a/{key}',
               'pycchdo.views.obj.obj_attr', 'objs/attr.jinja2')

    # Need precedence for extension to catch before ending up a cruise identifier
    route_path(config, 'cruise_kml', '/cruise/{cruise_id}.kml',
               'pycchdo.views.cruise.kml')
    obj_routes(config, 'cruise', new=True, json_index=True, json_show=True)
    # TODO map_full.png?
    route_path(config, 'cruise_map_full', '/cruise/{cruise_id}/map_full',
               'pycchdo.views.cruise.map_full')
    route_path(config, 'cruise_map_thumb', '/cruise/{cruise_id}/map_thumb',
               'pycchdo.views.cruise.map_thumb')
    route_path(config, 'cruises_archive', '/cruises/archive.zip',
               'pycchdo.views.cruise.cruises_archive')

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
    route_path(config, 'argo_index', '/argo.html',
               'pycchdo.views.argo.index', 'argo/index.jinja2')
    route_path(config, 'argo_index_no_ext', '/argo',
               'pycchdo.views.legacy.add_extension')
    route_path(config, 'argo_new', '/argo/new',
               'pycchdo.views.argo.new', 'argo/new.jinja2')
    route_path(config, 'argo_entity', '/argo/{id}',
               'pycchdo.views.argo.entity', 'argo/show.jinja2')

    # Basin lists
    basins_re = '|'.join(basins)
    route_path(config, 'basin_show', '/basin/{basin:%s}.html' % basins_re,
               'pycchdo.views.basin.basin_show', 'basin.jinja2')
    route_path(config, 'legacy_basin', '/{basin:%s}{ext:|\.html}' % basins_re,
               'pycchdo.views.legacy.basin')

	# Search routes
    route_path(config, 'search', '/search.html',
               'pycchdo.views.search.search')
    route_path(config, 'search_no_ext', '/search',
               'pycchdo.views.legacy.add_extension')

    route_path(config, 'search_results', '/search/results.html',
               'pycchdo.views.search.search_results', 'search/results.jinja2')
    route_path(config, 'search_results_no_ext', '/search/results',
               'pycchdo.views.legacy.add_extension')

    route_path(config, 'search_results_json', '/search/results.json',
               'pycchdo.views.search.search_results_json', 'json')

    route_path(config, 'advanced_search', '/search/advanced.html',
               'pycchdo.views.search.advanced_search', 'search/advanced.jinja2')
    route_path(config, 'advance_search_no_ext', '/search/advanced',
               'pycchdo.views.legacy.add_extension')

    # Search map routes
    route_path(config, 'search_map', '/search/map.html',
               'pycchdo.views.search_map.index', 'search/map.jinja2')
    route_path(config, 'search_map_no_ext', '/search/map',
               'pycchdo.views.legacy.add_extension')
    route_path(config, 'search_map_ids', '/search/map/ids',
               'pycchdo.views.search_map.ids')
    route_path(config, 'search_map_layer', '/search/map/layer',
               'pycchdo.views.search_map.layer')

    route_path(config, 'legacy_map_search', '/map_search', 
               'pycchdo.views.legacy.map_search')

    # maintain legacy data_access
    route_path(config, 'parameter_descriptions', '/parameter_descriptions',
               'pycchdo.views.legacy.parameter_descriptions')
    route_path(config, 'data_access', '/data_access',
               'pycchdo.views.legacy.data_access')
    route_path(config, 'data_access_show_cruise', '/data_access/show_cruise',
               'pycchdo.views.legacy.data_access_show_cruise')
    route_path(config, 'submit_no_ext', '/submit',
               'pycchdo.views.legacy.add_extension')
    route_path(config, 'groups', '/groups',
               'pycchdo.views.legacy.groups')

    # legacy static files
    route_path(config, 'static_metermap', '/metermap.html',
               'pycchdo.views.legacy.static_metermap')
    route_path(config, 'static_policies_parameters', '/policies/parameters.html',
               'pycchdo.views.legacy.static_policies_parameters')
    route_path(config, 'static_policies_name', '/policies/name.html',
               'pycchdo.views.legacy.static_policies_name')

    # Tools
    route_path(config, 'tools_menu', '/tools.html',
               'pycchdo.views.toplevel.tools_menu', 'tools.jinja2')
    route_path(config, 'tool_data_cmp', '/tool/data_cmp.html',
               'pycchdo.views.tools.data_cmp', 'tool/data_cmp.jinja2')
    route_path(config, 'tool_visual', '/tool/visual.html',
               'pycchdo.views.tools.visual', 'tool/visual.jinja2')
    route_path(config, 'tool_convert', '/tool/convert.html',
               'pycchdo.views.tools.convert', 'tool/convert.jinja2')
    route_path(config, 'tool_convert_from_to', '/tool/convert',
               'pycchdo.views.tools.convert_from_to', 'json')
    route_path(config, 'tool_convert_any_to_google_wire', '/tool/convert/any_to_google_wire',
               'pycchdo.views.tools.convert_any_to_google_wire', 'json')
    route_path(config, 'tool_archives', '/tool/archives.html',
               'pycchdo.views.tools.archives', 'tool/archives.jinja2')
    route_path(config, 'tool_dumps', '/tool/dumps.html',
               'pycchdo.views.tools.dumps', 'tool/dumps.jinja2')
    route_path(config, 'tool_dumps_sqlite', '/tool/dumps.sqlite',
               'pycchdo.views.tools.dumps_sqlite')

    # Staff
    route_path(config, 'staff_index', '/staff.html',
               'pycchdo.views.staff.index', 'staff/index.jinja2')
    route_path(config, 'staff_submissions', '/staff/submissions.html',
               'pycchdo.views.staff.submissions', 'staff/submissions.jinja2')
    route_path(config, 'staff_moderation', '/staff/moderation.html',
               'pycchdo.views.staff.moderation', 'staff/moderation.jinja2')

    # dynamic static pages
    route_path(config, 'project_carina', '/project_carina.html',
               'pycchdo.views.toplevel.project_carina', 'project_carina.jinja2')

    # Serve data blobs
    route_path(config, 'data', '/data/b/{data_id}*ignore',
               'pycchdo.views.toplevel.data')

    # Serve legacy /data prefix data files
    route_path(config, 'data_df', '/data/*rest',
               'pycchdo.views.legacy.data_df')

	# catchall_static must be last route
    route_path(config, 'catchall_static', '/*subpath',
               'pycchdo.views.toplevel.catchall_static')


def _configure(config):
    _configure_bindings(config)
    _configure_renderers(config)
    _configure_error_views(config)
    _configure_routes(config)
    

def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    FSFile.reconfig_fs_storage(settings['fs_root'])

    config = create_config(settings)
    _configure(config)
    return config.make_wsgi_app()
