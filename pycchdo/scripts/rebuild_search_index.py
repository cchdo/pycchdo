import argparse
from logging import getLogger, ERROR, WARN, INFO, DEBUG, NOTSET

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pycchdo.models.serial import DBSession
from pycchdo.models.search import SearchIndex, DETAIL


argparser = argparse.ArgumentParser(description='Rebuild search index')
argparser.add_argument(
    '-v', '--verbose', action='count', default=0,
    help='Verbosity by logging level.')
argparser.add_argument(
    '--clear', action='store_true', default=False,
    help='Whether to clear the indexes first')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: developement.ini)')
argparser.add_argument(
    'indices', type=str, nargs='*', 
    help='the indices to rebuild')


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)

    logger = getLogger('pycchdo.models.search')
    logger.setLevel(WARN)
    if args.verbose >= 0:
        logger.setLevel(INFO)
    if args.verbose >= 1:
        logger.setLevel(DEBUG)
    if args.verbose >= 2:
        logger.setLevel(DETAIL)

    settings = get_appsettings(args.config_uri + '#pycchdo')
    engine = engine_from_config(settings)
    DBSession.configure(bind=engine)
    si = SearchIndex(settings['search_index_path'])
    if args.indices:
        for index in args.indices:
            si._rebuild_index(index, clear=args.clear)
    else:
        si.rebuild_index(clear=args.clear)
