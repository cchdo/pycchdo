from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid

import webhelpers
import webhelpers.html
import webhelpers.html.tags

import helpers
import models
from models import init_conn


class RequestWithUserAttribute(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            p = models.Person.get_id(userid)
            return p


def add_renderer_globals(event):
    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['h'] = helpers


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    # TODO change the secret
    authentication_policy = AuthTktAuthenticationPolicy('seekrit')
    authorization_policy = ACLAuthorizationPolicy()

    # TODO change the secret
    session_factory = UnencryptedCookieSessionFactoryConfig('itsaseekreet')

    config = Configurator(
        settings=settings,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        request_factory=RequestWithUserAttribute,
        session_factory=session_factory,
    )

    models.init_conn(settings)

    config.include('pyramid_jinja2')
    config.add_subscriber(add_renderer_globals, BeforeRender)

    config.add_static_view('static', 'pycchdo:static')

    config.add_route('home', '/')
    config.add_view('pycchdo.views.home', route_name='home', renderer='templates/base.jinja2')

    config.add_route('submit', '/submit')
    config.add_view('pycchdo.views.submit', route_name='submit', renderer='templates/submit.jinja2')

    config.add_route('clear', '/clear')
    config.add_view('pycchdo.views.clear_db', route_name='clear')

    config.add_route('session', '/session')
    config.add_view('pycchdo.views.session_show', route_name='session', renderer='templates/sessions/show.jinja2')
    config.add_route('session_identify', '/session/identify')
    config.add_view('pycchdo.views.session_identify', route_name='session_identify', renderer='templates/sessions/identify.jinja2')
    config.add_route('session_new', '/session/new')
    config.add_view('pycchdo.views.session_new', route_name='session_new')
    config.add_route('session_delete', '/session/delete')
    config.add_view('pycchdo.views.session_delete', route_name='session_delete')

    config.add_route('objs', '/objs')
    config.add_view('pycchdo.views.objs', route_name='objs', renderer='templates/objs/index.jinja2')
    config.add_route('obj_new', '/objs/new')
    config.add_view('pycchdo.views.obj_new', route_name='obj_new', renderer='templates/objs/new.jinja2')
    config.add_route('obj_show', '/obj/{obj_id}')
    config.add_view('pycchdo.views.obj_show', route_name='obj_show', renderer='templates/objs/show.jinja2')
    config.add_route('obj_attrs', '/obj/{obj_id}/a')
    config.add_view('pycchdo.views.obj_attrs', route_name='obj_attrs', renderer='templates/objs/attrs.jinja2')

    config.add_route('obj_attr', '/obj/{obj_id}/a/{key}')
    config.add_view('pycchdo.views.obj_attr', route_name='obj_attr', renderer='templates/objs/attr.jinja2')

    config.add_route('cruises', '/cruises')
    config.add_view('pycchdo.views.cruises_index', route_name='cruises', renderer='templates/cruise/index.jinja2')

    config.add_route('cruise_show', '/cruise/{cruise_id}')
    config.add_view('pycchdo.views.cruise_show', route_name='cruise_show', renderer='templates/cruise/show.jinja2')

    config.add_route('data', '/data/{data_id}')
    config.add_view('pycchdo.views.data', route_name='data')

    config.add_route('catchall_static', '/*subpath')
    config.add_view('pycchdo.views.catchall_static', route_name='catchall_static', renderer='templates/base.jinja2')

    return config.make_wsgi_app()
