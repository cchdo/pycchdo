#!/usr/bin/env python

import argparse
import sys
import os
import pwd
from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError, \
                         Error as ConfigError

from pycchdo import models
from pycchdo.importers import implog, cchdo, seahunt
from pycchdo.models.search import SearchIndex


wwwusername = '_www'
try:
    wwwuser = pwd.getpwnam(wwwusername)
    import_uid = wwwuser.pw_uid
    import_gid = wwwuser.pw_gid
except Exception:
    implog.error('No such user %s' % wwwusername)
    sys.exit(1)


def check_root_and_drop_permissions():
    if os.geteuid() != 0:
        implog.error('pycchdo importer must be run as root in order to '
                     'import correct file ownerships')
        sys.exit(1)

    # Drop effective privileges, need to re-escalate later when
    # importing files
    os.setegid(import_gid)
    os.seteuid(import_uid)


def parse_args():
    argparser = argparse.ArgumentParser(description='Import CCHDO/seahunt data')
    argparser.add_argument(
        'paste_config', help='A Paste config .ini file that contains application, database, and search index settings')
    argparser.add_argument(
        '-c', '--clear_db_first', type=bool, default=False,
        help='Whether to clear the pycchdo database before rebuilding. Useful for full rebuilds.')
    argparser.add_argument(
        '-C', '--skip_cchdo', type=bool, default=False, help='Skip importing CCHDO data')
    argparser.add_argument(
        '-S', '--skip_seahunt', type=bool, default=False, help='Skip importing Seahunt data')
    argparser.add_argument(
        '-I', '--skip_search_index', type=bool, default=False, help='Skip building the search index')
    argparser.add_argument(
        '-i', '--search_index_only', type=bool, default=False, help='Only build the serach index')
    argparser.add_argument(
        '-D', '--skip_downloads', type=bool, default=False, help='Skip downloading files')
    argparser.add_argument(
        '-X', '--clear_seahunt', type=bool, default=False, help='Clear seahunt imports and exit.')
    argparser.add_argument(
        '-F', '--files_only', type=bool, default=False, help='Only import items that have files')
    return argparser.parse_args()


def read_config(args):
    config = SafeConfigParser()
    config.read(args.paste_config)
    app_entry = 'app:pycchdo'
    try:
        args.db_uri = config.get(app_entry, 'db_uri')
        args.db_search_index_path = config.get(
            app_entry, 'db_search_index_path')
    except ConfigError:
        implog.error('importer requires an .ini file with db_uri and '
                     'db_search_index_path defined for %s' % app_entry)
        sys.exit(1)


def clear_pycchdo():
    implog.info('Clearing pycchdo database')
    cchdo_conn = models.cchdo()
    for coll in cchdo_conn.collection_names():
        if not coll.startswith('system'):
            cchdo_conn.drop_collection(coll)


def main():
    check_root_and_drop_permissions()

    args = parse_args()

    read_config(args)

    implog.info('Importing with options %s' % args)
    implog.info("Connect to pycchdo (%s)" % args.db_uri)
    models.init_conn(args.db_uri)

    if not args.search_index_only:
        if args.clear_db_first:
            clear_pycchdo()

        models.ensure_indices()

        if args.clear_seahunt:
            seahunt.clear()
            return 0

        if not args.skip_cchdo:
            cchdo.import_(import_gid, dl_files=not args.skip_downloads,
                          files_only=args.files_only)

        if not args.skip_seahunt:
            seahunt.import_(dl_files=not args.skip_downloads,
                            files_only=args.files_only)

    if not args.skip_search_index:
        SearchIndex(args.db_search_index_path).rebuild_index(
            clear=args.clear_db_first)

    implog.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main())
