import os
from argparse import ArgumentParser

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pycchdo.models.serial import DBSession, Person


def add_permission(pid, perm):
    ppp = Person.query().get(pid)
    if perm not in ppp.permissions:
        ppp.permissions.append(perm)
        transaction.commit()


def remove_permission(pid, perm):
    ppp = Person.query().get(pid)
    ppp.permissions.remove(perm)
    transaction.commit()


argparser = ArgumentParser(description="Edit person's permissions")
argparser.add_argument(
    'person_id', type=int, help="The person's id")
argparser.add_argument(
    'permission', type=unicode, default=u'staff',
    help="The permission (default: staff)")
argparser.add_argument(
    'action', type=unicode, default=u'add', choices=[u'add', 'remove'],
    help="The action (default: add)")
argparser.add_argument(
    'config_uri', type=str, nargs='?', default='development.ini',
    help='(default: development.ini)')


ACTIONS = {
    'add': add_permission,
    'remove': remove_permission,
}


def main():
    args = argparser.parse_args()

    setup_logging(args.config_uri)
    settings = get_appsettings(args.config_uri + '#pycchdo')
    engine = engine_from_config(settings)
    DBSession.configure(bind=engine)

    try:
        ACTIONS[args.action](args.person_id, args.permission)
    except KeyError:
        raise NotImplementedError(u'No such action')
    return 0
