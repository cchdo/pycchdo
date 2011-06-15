from pyramid.config import Configurator

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)

    config.include('pyramid_jinja2')

    config.add_static_view('static', 'pycchdo:static')

    config.add_route('home', '/', view='pycchdo.views.home',
                     view_renderer='templates/base.jinja2')
    config.add_route('objs', '/objs', view='pycchdo.views.objs',
                     view_renderer='templates/objs/index.jinja2')
    config.add_route('obj_new', '/objs/new', view='pycchdo.views.obj_new',
                     view_renderer='templates/objs/new.jinja2')
    config.add_route('obj_show', '/obj/{obj_id}', view='pycchdo.views.obj_show',
                     view_renderer='templates/objs/show.jinja2')
    config.add_route('obj_attrs', '/obj/{obj_id}/a', view='pycchdo.views.obj_attrs',
                     view_renderer='templates/objs/attrs.jinja2')
    config.add_route('obj_attr', '/obj/{obj_id}/a/{key}', view='pycchdo.views.obj_attr',
                     view_renderer='templates/objs/attr.jinja2')

    return config.make_wsgi_app()
