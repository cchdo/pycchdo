from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid

import webhelpers
import webhelpers.html
import webhelpers.html.tags

import helpers
from models import init_conn


class RequestWithUserAttribute(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            import models
            p = models.Person.get_id(userid)
            return p


def add_renderer_globals(event):
    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['h'] = helpers


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    authentication_policy = AuthTktAuthenticationPolicy('seekrit')
    authorization_policy = ACLAuthorizationPolicy()

    config = Configurator(
        settings=settings,
        authentication_policy=authentication_policy,
        authorization_policy=authorization_policy,
        request_factory=RequestWithUserAttribute,
    )

    init_conn(settings)

    config.include('pyramid_jinja2')
    config.add_subscriber(add_renderer_globals, BeforeRender)

    config.add_static_view('static', 'pycchdo:static')

    config.add_route('home', '/')
    config.add_view('pycchdo.views.home', route_name='home', renderer='templates/base.jinja2')

    config.add_route('clear', '/clear')
    config.add_view('pycchdo.views.clear_db', route_name='clear')

    config.add_route('session', '/session')
    config.add_view('pycchdo.views.session_show', route_name='session', renderer='templates/sessions/show.jinja2')
    config.add_route('session_new', '/session/new')
    config.add_view('pycchdo.views.session_new', route_name='session_new')
    config.add_route('session_delete', '/session/delete')
    config.add_view('pycchdo.views.session_delete', route_name='session_delete')

    config.add_route('objs', '/objs')
    config.add_view('pycchdo.views.objs', route_name='objs', renderer='templates/objs/index.jinja2')
    config.add_route('obj_new', '/objs/new')
    config.add_view(
        view='pycchdo.views.obj_new', route_name='obj_new',
        context='pycchdo.models.Obj', permission='create',
        renderer='templates/objs/new.jinja2')
    config.add_route('obj_show', '/obj/{obj_id}')
    config.add_view('pycchdo.views.obj_show', route_name='obj_show', renderer='templates/objs/show.jinja2')
    config.add_route('obj_attrs', '/obj/{obj_id}/a')
    config.add_view('pycchdo.views.obj_attrs', route_name='obj_attrs', renderer='templates/objs/attrs.jinja2')

    config.add_route('obj_attr', '/obj/{obj_id}/a/{key}')
    config.add_view('pycchdo.views.obj_attr', route_name='obj_attr', renderer='templates/objs/attr.jinja2')

    return config.make_wsgi_app()
