import sys
import os
from contextlib import closing
from getpass import getpass
from urllib import quote
from urlparse import urlsplit, urlunsplit, SplitResult
from subprocess import Popen, PIPE
from argparse import ArgumentParser

from sqlalchemy import create_engine
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
    host, port, dbname, owner, password, o = credentials(engine_url)

    try:
        password = os.environ['PGPASSWORD']
    except KeyError:
        password = getpass('Password for {0}: '.format(args.superuser))
    new_split = o._replace(
        netloc='{0}:{1}@{2}:{3}'.format(
            args.superuser, quote(password), o.hostname, o.port),
        path=args.template_db)
    superuser_url = urlunsplit(new_split)
    engine = create_engine(superuser_url)
    with closing(engine.connect()) as conn:
        # ensure owner exists
        print 'checking for user {0}...'.format(owner)
        with closing(conn.execute(sql_check_user(owner))) as result:
            if not result.first():
                print 'creating user {0}...'.format(owner)
                with closing(conn.execute(
                        sql_create_user(owner, password))) as result:
                    pass

        print 're-creating database...'
        # These operations cannot be done inside a transaction. Commit the open
        # transaction first.
        conn.execute("commit")
        conn.execute(sql_drop(dbname, owner))
        conn.execute("commit")
        conn.execute(sql_create(dbname, owner))
    print 'granting...'
    new_split = new_split._replace(path=dbname)
    superuser_url = urlunsplit(new_split)
    engine = create_engine(superuser_url)
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
    db_missing = False
    engine = create_engine(engine_url)
    try:
        engine.connect().close()
    except OperationalError as err:
        db_missing = True

    if args.full_reset or db_missing:
        drop_and_create_db(args, engine_url)

    if args.full_reset or db_missing or args.reset_db:
        print 'resetting database...'
        reset_database(engine)
    else:
        print 'creating additional...'
        Meta.create_all(engine)
