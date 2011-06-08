from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from pycchdo.models import initialize_sql

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)
    config = Configurator(settings=settings)

    config.include('pyramid_jinja2')

    config.add_static_view('static', 'pycchdo:static')

    config.add_route('home', '/', view='pycchdo.views.home',
                     view_renderer='templates/base.jinja2')
    return config.make_wsgi_app()
