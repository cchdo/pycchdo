import subprocess
from subprocess import Popen, PIPE
from argparse import ArgumentParser
from StringIO import StringIO

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pycchdo.models import reset_database


argparser = ArgumentParser(description='Reset database')
argparser.add_argument(
    '--full-reset', action='store_true', default=False,
    help='Whether to drop the database first')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: development.ini)')


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)
    settings = get_appsettings(args.config_uri + '#pycchdo')

    if args.full_reset:
        dbname = settings['sqlalchemy.url'].split('/')[-1]
        owner = 'pycchdo'

        psql_script = """\
DROP DATABASE IF EXISTS {dbname};
CREATE DATABASE {dbname} TEMPLATE template_postgis;
ALTER DATABASE {dbname} OWNER TO {owner};
\connect {dbname};
"""

        tables = [
            'geography_columns', 'geometry_columns', 'spatial_ref_sys',
            'raster_columns', 'raster_overviews'] 
        for table in tables:
            psql_script += (
                'GRANT select, insert, update, delete ON TABLE public.{table} '
                'TO {{owner}};\n').format(table=table)

        psql_stdin = psql_script.format(dbname=dbname, owner=owner)

        print 'resetting database...'
        reset = Popen(
            ['psql', '-h', 'ghdc.ucsd.edu', '-U', 'postgres', 'postgres'],
            stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = reset.communicate(input=psql_stdin)
        if 'ERROR' in stderr:
            raise ValueError(stderr)

    engine = engine_from_config(settings)
    reset_database(engine)
