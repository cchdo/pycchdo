import argparse

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pycchdo.models.serial import DBSession
from pycchdo.models.search import SearchIndex


argparser = argparse.ArgumentParser(description='Rebuild search index')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: developement.ini)')


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)
    settings = get_appsettings(args.config_uri + '#pycchdo')
    engine = engine_from_config(settings)
    DBSession.configure(bind=engine)
    SearchIndex(settings['search_index_path']).rebuild_index(clear=True)
