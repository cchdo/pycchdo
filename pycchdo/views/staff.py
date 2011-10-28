import pycchdo.models as models

from . import *
from session import require_signin


def index(request):
    return {}


def submissions(request):
    submissions = models.Submission.get_all()
    return {'submissions': submissions}


def _moderate_attribute(request):
    # TODO permissions check moderator

    try:
        attr = models._Attr.get_id(request.params['attr'])
    except KeyError:
        request.response_status = '400 No attribute to modify'
        return
    except ValueError:
        request.response_status = '404 Attribute to modify not found'
        return

    action = request.params['action']
    if action not in ('Acknowledge', 'Accept', 'Reject'):
        request.response_status = ('400 Bad action')
        return

    if action == 'Acknowledge':
        if attr.is_acknowledged():
            request.response_status = ('400 Attempt to acknowledge already '
                                       'acknowledged attribute')
            return

        attr.acknowledge(request.user)
    else:
        if attr.is_judged():
            request.response_status = '400 Attempt to modify judged attribute'
            return
        if action == 'Accept':
            attr.accept(request.user)
        else:
            attr.reject(request.user)


def moderation(request):
    method = _http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_attribute(request)

    pending = models._Attr.pending()
    return {'pending': pending}
