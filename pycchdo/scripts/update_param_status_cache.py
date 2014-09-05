import sys
import os
from contextlib import closing
from argparse import ArgumentParser
import logging
from multiprocessing import Pool, get_logger, log_to_stderr
import warnings


log = log_to_stderr()
log.setLevel(logging.INFO)


import transaction

from sqlalchemy.orm import noload, joinedload
from sqlalchemy import exc as sa_exc

from pyramid.paster import get_appsettings, setup_logging

from pycchdo.models.serial import DBSession, Cruise, Parameter, CruiseParameter
from pycchdo import initialize_from_settings
from pycchdo.tweens import fsstore_context

from libcchdo.fns import uniquify
from libcchdo.model.datafile import DataFile
from libcchdo.formats.bottle import exchange as btlex 


argparser = ArgumentParser(description='Update the bottle parameter status cache')
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: development.ini)')


def is_minimal(col):
    return len(filter(None, col.values)) <= 10


BANNED_PARAMETERS = ['EXPOCODE', 'SECT_ID', 'STNNBR', 'CASTNO', 'SAMPNO',
                     'BTLNBR', 'LATITUDE', 'LONGITUDE', 'DEPTH', '_DATETIME']


def read_btlex_for_param_status(args):
    fsstore, cruise_id, bfile = args
    with fsstore_context(fsstore):
        try:
            fobj = bfile.open_file()
        except (OSError, IOError):
            log.error(u'Missing file for {0}'.format(cruise_id))
            return (cruise_id, None)
        dfile = DataFile()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=sa_exc.SAWarning)
                btlex.read(dfile, fobj)
        except BaseException as err:
            log.error(u'Unable to read bottle exchange for {0}'.format(cruise_id))
            log.error(err)
        return (cruise_id, dfile)


def _handle_result_dfile(cruise, dfile):
    try:
        cruise.num_stations = len(uniquify(dfile['STNNBR']))
    except KeyError:
        pass
    cparams = []
    for param, col in dfile.columns.items():
        if param in BANNED_PARAMETERS:
            continue
        minimal = is_minimal(col)
        parameter = Parameter.query().\
            filter(Parameter.name == param).first()
        if not parameter:
            log.error(u'pycchdo does not know about parameter {0}'.format(
                param))
        cparams.append(CruiseParameter(parameter, minimal))
    cruise.parameters = cparams
    log.info(cruise.uid)


def main():
    args = argparser.parse_args()

    settings = get_appsettings(args.config_uri + '#pycchdo')
    initialize_from_settings(settings)
    fsstore = settings['fsstore']

    log.info(u'loading cruises...')
    cruise_query = Cruise.query().options(noload('*'), joinedload('files'),
                                          joinedload('files.file'))

    cruises = {}
    files = []
    for cruise in cruise_query.all():
        btl = cruise.files.get('bottle_exchange', None)
        if btl is None:
            continue
        if btl.file is None:
            log.error(u'Missing bottle exchange for {0}'.format(cruise))
            continue
        cruises[cruise.id] = cruise
        files.append((fsstore, cruise.id, btl.file))

    log.info(u'reading data...')

    pool = Pool()
    itr = pool.imap_unordered(read_btlex_for_param_status, files)
    for cruise_id, dfile in itr:
        if dfile is None:
            continue
        cruise = cruises[cruise_id]
        _handle_result_dfile(cruise, dfile)

    transaction.commit()
    log.info(u'done')
