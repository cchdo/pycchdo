#!/usr/bin/env python

import getopt
import sys
import os
import pwd
from ConfigParser import SafeConfigParser

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


_USAGE = """\
Usage: importer.py <ini-file>
\t-c|--clear\tClear database before importing
\t-C|--skip-cchdo\tSkip importing CCHDO data
\t-S|--skip-seahunt\tSkip importing Seahunt data
\t-I|--skip-index\tSkip building the search index
\t-i|--index-only\tOnly build search index
\t-D|--skip-downloads\tSkip downloading files
\t-X|--clear-seahunt\tClears seahunt imports and exits
\t-F|--files-only\tOnly import items that have files
\t-h|--help\tPrint this help message
"""


def main(argv):
    if os.geteuid() != 0:
        implog.error('pycchdo importer must be run as root in order to '
                     'import correct file ownerships')
        print _USAGE
        return 1

    # Drop effective privileges to _www, need to re-escalate later when
    # importing files
    os.setegid(import_gid)
    os.seteuid(import_uid)

    options = {
        'clear_db_first': False,
        'db_uri': 'mongodb://dimes.ucsd.edu:28019',
        'db_search_index_path': '/var/cache/pycchdo_search_index_dev',
        'cchdo_import': True,
        'seahunt_import': True,
        'build_index': True,
        'index_only': False,
        'dl_files': True,
        'clear_seahunt': False,
        'files_only': False,
    }

    if len(argv) < 2:
        implog.error('pycchdo importer needs a paste config .ini file to read '
                     'database and search index settings')
        return 1

    opts, args = getopt.getopt(
        argv[1:], 'hcCSIiDXF',
        ('help', 'clear', 'skip-cchdo', 'skip-seahunt', 'skip-index',
         'index-only', 'skip-downloads', 'clear-seahunt', 'files-only'))
    for option, value in opts:
        if option in ('-h', '--help'):
            print _USAGE
            return 0
        if option in ('-c', '--clear'):
            options['clear_db_first'] = True
        if option in ('-C', '--skip-cchdo'):
            options['cchdo_import'] = False
        if option in ('-S', '--skip-seahunt'):
            options['seahunt_import'] = False
        if option in ('-I', '--skip-index'):
            options['build_index'] = False
        if option in ('-i', '--index-only'):
            options['index_only'] = True
        if option in ('-D', '--skip-downloads'):
            options['dl_files'] = False
        if option in ('-X', '--clear-seahunt'):
            options['clear_seahunt'] = True
        if option in ('-F', '--files-only'):
            options['files_only'] = True

    config = SafeConfigParser()
    if len(args) != 1:
        implog.error('importer requires an .ini file with db_uri and '
                     'db_search_index_path defined for app:pycchdo')
        print _USAGE
        return 1
    config.read(args[0])
    options['db_uri'] = config.get('app:pycchdo', 'db_uri')
    options['db_search_index_path'] = config.get('app:pycchdo', 'db_search_index_path')
    del config

    implog.info('Importing with options %s' % options)

    implog.info("Connect to pycchdo (%s)" % options['db_uri'])
    models.init_conn(options['db_uri'])

    if not options['index_only']:
        if options['clear_db_first']:
            implog.info('Clearing database')
            cchdo_conn = models.cchdo()
            for coll in cchdo_conn.collection_names():
                if not coll.startswith('system'):
                    cchdo_conn.drop_collection(coll)

        models.ensure_indices()

        if options['clear_seahunt']:
            seahunt.clear()
            return 0

        if options['cchdo_import']:
            cchdo.import_(import_gid, dl_files=options['dl_files'],
                          files_only=options['files_only'])

        if options['seahunt_import']:
            seahunt.import_(dl_files=options['dl_files'],
                            files_only=options['files_only'])

    if options['build_index']:
        SearchIndex(options['db_search_index_path']).rebuild_index(
            clear=options['clear_db_first'])

    implog.info("Finished import")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
