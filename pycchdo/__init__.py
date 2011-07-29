from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid

import models


class RequestWithUserAttribute(Request):
    @reify
    def user(self):
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            p = models.Person.get_id(userid)
            return p


def add_renderer_globals(event):
    import webhelpers
    import webhelpers.html
    import webhelpers.html.tags

    import helpers

    event['wh'] = webhelpers
    event['whh'] = webhelpers.html
    event['h'] = helpers


def obj_routes(config, obj, plural_obj=None):
    if not plural_obj:
        plural_obj = obj + 's'
    config.add_route(plural_obj, '/' + plural_obj)
    config.add_view('pycchdo.views.{obj}.{plural_obj}_index'.format(
        obj=obj, plural_obj=plural_obj), route_name=plural_obj,
        renderer='templates/{obj}/index.jinja2'.format(obj=obj))
    config.add_route('{obj}_show'.format(obj=obj), '/{obj}/{{{obj}_id}}'.format(obj=obj))
    config.add_view('pycchdo.views.{obj}.{obj}_show'.format(obj=obj),
                    route_name='{obj}_show'.format(obj=obj),
                    renderer='templates/{obj}/show.jinja2'.format(obj=obj))


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

    obj_routes(config, 'cruise')
    obj_routes(config, 'collection')
    obj_routes(config, 'country', 'countries')
    obj_routes(config, 'institution')
    obj_routes(config, 'ship')

	# Search routes
    config.add_route('search','/search')
    config.add_view('pycchdo.views.search.search', route_name='search')

    config.add_route('search_results', '/search/results')
    config.add_view('pycchdo.views.search.search_results', route_name='search_results')

    config.add_route('advanced_search','/search/advanced')

    # maintain legacy URLs
    config.add_route('data_access','/data_access')
    config.add_view('pycchdo.views.search.advanced_search', route_name='advanced_search', renderer='templates/search/advanced.jinja2')
    config.add_view('pycchdo.views.search.advanced_search', route_name='data_access', renderer='templates/search/advanced.jinja2') #maintain legacy URLs

    # Serve data blobs
    config.add_route('data', '/data/{data_id}')
    config.add_view('pycchdo.views.data', route_name='data')

	# catchall_static must be last route
    config.add_route('catchall_static', '/*subpath')
    config.add_view('pycchdo.views.catchall_static', route_name='catchall_static', renderer='templates/base.jinja2')

    return config.make_wsgi_app()
