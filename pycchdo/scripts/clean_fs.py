import os
from argparse import ArgumentParser

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pycchdo.models.serial import DBSession, FSFile


argparser = ArgumentParser(description='Clean the filesystem of unlinked files')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: development.ini)')


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)
    settings = get_appsettings(args.config_uri + '#pycchdo')
    engine = engine_from_config(settings)
    DBSession.configure(bind=engine)

    fsids = set([x[0] for x in DBSession.query(FSFile.fsid).all()])

    fs_root = settings['fs_root']
    files = [os.path.join(dp, f) for dp, dn, fn in os.walk(fs_root) for f in fn]
    fsfsids = set()
    # Identify orphaned FS files
    for fname in files:
        bname = os.path.basename(fname)
        fsfsids.add(bname)
        if bname not in fsids:
            with open(fname, 'r') as fff:
                print bname, os.stat(fname).st_size, repr(fff.readline()[:10])
            os.unlink(fname)

    # Also identify files that are not in the FS store but in the database
    not_in_fs = fsids - fsfsids
    if not_in_fs:
        print 'Not found in FS:', not_in_fs
    else:
        print 'FS has all required files'
