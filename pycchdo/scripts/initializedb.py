import sys
import os
from contextlib import closing
from getpass import getpass
from urllib import quote
from urlparse import urlsplit, urlunsplit, SplitResult
from subprocess import Popen, PIPE
from argparse import ArgumentParser

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError

from pyramid.paster import get_appsettings, setup_logging

from pycchdo.models.serial import reset_database, Meta


argparser = ArgumentParser(description='Reset database')
argparser.add_argument(
    '--create-additional', action='store_true', default=False,
    help='Skips resetting and just creates new schema')
argparser.add_argument(
    '--full-reset', action='store_true', default=False,
    help='Drop the database and recreate')
argparser.add_argument(
    '--reset-db', action='store_true', default=False,
    help='Drop all tables and recreate. Does not drop the database.')
argparser.add_argument(
    '--superuser', type=str, default='postgres',
    help='The adminstrative user with the power to create databases for others.'
         '(default: postgres)')
argparser.add_argument(
    '--template-db', type=str, default='template1',
    help='A template database to log into temporarily while making changes.')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: development.ini)')


def sql_check_user(owner):
    return "SELECT 1 FROM pg_roles WHERE rolname={0!r}".format(owner)


def sql_check_database(dbname):
    return 'SELECT 1 FROM pg_database WHERE datname={0!r}'.format(dbname)


def sql_create_user(user, password):
    return "CREATE USER {0} CREATEDB ENCRYPTED PASSWORD {1!r}".format(user, password)


def sql_drop(dbname, owner):
    return "DROP DATABASE IF EXISTS {dbname};".format(dbname=dbname)


def sql_create(dbname, owner):
    return "\
CREATE DATABASE {dbname} OWNER {owner} TEMPLATE template_postgis;""".format(
        dbname=dbname, owner=owner)


def sql_grant(owner):
    tables = [
        'geography_columns', 'geometry_columns', 'spatial_ref_sys',
        #'raster_columns', 'raster_overviews',
    ] 
    sql = ""
    for table in tables:
        sql += (
            'GRANT select, insert, update, delete ON TABLE public.{table} '
            'TO {{owner}};\n').format(table=table)
    return sql.format(owner=owner)


def credentials(engine_url):
    o = urlsplit(engine_url)

    host = o.hostname
    port = str(o.port or 5432)
    dbname = o.path[1:]
    owner = o.username or 'pycchdo'
    password = o.password
    assert password is not None

    return host, port, dbname, owner, password, o


def drop_and_create_db(args, engine_url):
    host, port, dbname, owner, pycchdo_password, o = credentials(engine_url)

    try:
        password = os.environ['PGPASSWORD']
    except KeyError:
        password = getpass('Password for {0}: '.format(args.superuser))
    new_split = o._replace(
        netloc='{0}:{1}@{2}:{3}'.format(
            args.superuser, quote(password), o.hostname, o.port),
        path=args.template_db)
    superuser_url = urlunsplit(new_split)
    engine = create_engine(superuser_url, poolclass=NullPool)
    with closing(engine.connect()) as conn:
        # ensure owner exists
        sys.stderr.write('checking for user {0}...\n'.format(owner))
        with closing(conn.execute(sql_check_user(owner))) as result:
            if not result.first():
                sys.stderr.write('creating user {0}...\n'.format(owner))
                with closing(conn.execute(
                        sql_create_user(owner, pycchdo_password))) as result:
                    pass

    sys.stderr.write('tearing down database...\n')
    with closing(engine.connect()) as conn:
        conn.execute("rollback")
        # These operations cannot be done inside a transaction.
        conn.execution_options(autocommit=False).execute(sql_drop(dbname, owner))
        conn.execution_options(autocommit=False).execute(sql_create(dbname, owner))
        # There's still a rollback here...
        conn.begin()
    sys.stderr.write('granting...\n')
    new_split = new_split._replace(path=dbname)
    superuser_url = urlunsplit(new_split)

    sys.stderr.write('creating...\n')
    engine = create_engine(superuser_url, poolclass=NullPool)
    with closing(engine.connect()) as conn:
        sql = sql_grant(owner)
        with closing(conn.execute(sql)) as result:
            pass


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)
    settings = get_appsettings(args.config_uri + '#pycchdo')
    engine_url = settings['sqlalchemy.url']

    # Check if database exists
    sys.stderr.write('checking database...\n')
    db_missing = False
    engine = create_engine(engine_url, poolclass=NullPool)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError as err:
        sys.stderr.write('database missing: {0!r}\n'.format(err))
        db_missing = True

    if args.full_reset or db_missing:
        sys.stderr.write('re-creating database...\n')
        drop_and_create_db(args, engine_url)

    if args.full_reset or db_missing or args.reset_db:
        sys.stderr.write('resetting database...\n')
        reset_database(engine)
    else:
        sys.stderr.write('creating additional...\n')
        Meta.create_all(engine)
