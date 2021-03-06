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

from webassets import Bundle

import webhelpers
import webhelpers.html
import webhelpers.html.tags

import geojson

from sqlalchemy import engine_from_config

from pycchdo import helpers
from pycchdo.util import (
    reenable_logs, patch_pyramid_exclog, patch_get_all_pending)
from pycchdo.routes import configure_routes
from pycchdo.models.serial import DBSession, Person
from pycchdo.models.search import SearchIndex
from pycchdo.models.filestorage import FSStore
from pycchdo.views.datacart import get_datacart


class RequestFactory(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            return Person.query().get(userid)

    @reify
    def search_index(self):
        return self.registry.settings['db.search_index']

    @reify
    def models(self):
        return models

    @reify
    def fsstore(self):
        return self.registry.settings['fsstore']

    @reify
    def datacart(self):
        return get_datacart(self)

    @reify
    def db(self):
        return DBSession


def _configure_bindings(config):
    # get_jinja2_environment may return None if config is not committed
    config.commit()
    config.add_jinja2_extension('webassets.ext.jinja2.AssetsExtension')
    config.add_jinja2_extension('webassets.ext.jinja2.AssetsExtension', '.html')
    assets_env = config.get_webassets_env()
    config.get_jinja2_environment().assets_environment = assets_env
    config.get_jinja2_environment('.html').assets_environment = assets_env
    config.add_jinja2_search_path('pycchdo:templates')
    config.add_jinja2_search_path('pycchdo:templates', '.html')


def _add_renderer_globals(event):
    # from urllib import quote
    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['txt'] = webhelpers.text
    event['tags'] = webhelpers.html.tags
    event['h'] = helpers
    event['geojson'] = geojson


def _configure_renderers(config):
    config.add_subscriber(_add_renderer_globals, BeforeRender)
    config.add_jinja2_renderer('.html')
    config.add_renderer('json', 'pycchdo.renderer_factory.json')


def _add_error_view(
        config, view_callable, context, renderer='errors/xxx.jinja2'):
    config.add_view(view_callable, context=context, renderer=renderer)


def _configure_error_views(config):
    _add_error_view(config, 'pycchdo.views.notfound_view', NotFound)
    _add_error_view(config, 'pycchdo.views.unauthorized_view', HTTPUnauthorized)
    _add_error_view(config, 'pycchdo.views.server_error_view', HTTPInternalServerError)


def _configure(config):
    _configure_renderers(config)
    _configure_bindings(config)
    _configure_error_views(config)
    configure_routes(config)
    config.add_tween('pycchdo.tweens.fsstore_tween_factory')


def initialize_from_settings(settings):
    settings['db.engine'] = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=settings['db.engine'])
    settings['fsstore'] = FSStore(
        path=settings['file_system_path'],
        base_url='/',
    )


def create_config(settings):
    authentication_policy = AuthTktAuthenticationPolicy(
        settings['key_auth_policy'])
    authorization_policy = ACLAuthorizationPolicy()
    session_factory = UnencryptedCookieSessionFactoryConfig(
        settings['key_session_factory'])

    settings['db.search_index'] = SearchIndex(settings['search_index_path'])

    return Configurator(
        settings=settings,
        request_factory=RequestFactory,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        session_factory=session_factory,
    )
    

def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    initialize_from_settings(settings)

    reenable_logs()
    patch_pyramid_exclog()
    patch_get_all_pending()

    config = create_config(settings)
    _configure(config)
    return config.make_wsgi_app()
