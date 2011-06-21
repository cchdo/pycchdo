from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid


class RequestWithUserAttribute(Request):
    @reify
    def user(self):
        # <your database connection, however you get it, the below line
        # is just an example>
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            # in the database
            import models
            p = models.Person.get_id(userid)
            return p


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

    config.include('pyramid_jinja2')

    config.add_static_view('static', 'pycchdo:static')

    config.add_route('home', '/', view='pycchdo.views.home', view_renderer='templates/base.jinja2')

    config.add_route('clear', '/clear', view='pycchdo.views.clear_db')

    config.add_route('session', '/session', view='pycchdo.views.session_show', view_renderer='templates/sessions/show.jinja2')
    config.add_route('session_new', '/session/new', view='pycchdo.views.session_new')
    config.add_route('session_delete', '/session/delete', view='pycchdo.views.session_delete')

    config.add_route('objs', '/objs', view='pycchdo.views.objs',
                     view_renderer='templates/objs/index.jinja2')
    config.add_route('obj_new', '/objs/new', view='pycchdo.views.obj_new',
                     view_renderer='templates/objs/new.jinja2')
    config.add_view(
        view='pycchdo.views.obj_new', route_name='obj_new',
        context='pycchdo.models.Obj', permission='create',
        renderer='templates/objs/new.jinja2')
    config.add_route('obj_show', '/obj/{obj_id}', view='pycchdo.views.obj_show',
                     view_renderer='templates/objs/show.jinja2')
    config.add_route('obj_attrs', '/obj/{obj_id}/a', view='pycchdo.views.obj_attrs',
                     view_renderer='templates/objs/attrs.jinja2')
    config.add_route('obj_attr', '/obj/{obj_id}/a/{key}', view='pycchdo.views.obj_attr',
                     view_renderer='templates/objs/attr.jinja2')

    return config.make_wsgi_app()
