from pyramid.httpexceptions import HTTPUnauthorized

from pycchdo.helpers import is_staff, link_cruise, date, link_person
import pycchdo.models as models

from . import *
from session import require_signin


def staff_signin_required(view_callable):
    """ Decorates a view_callable so that the signed in user must be a staff
        member in order to view.
    """
    def decorator(*args, **kwargs):
        request = args[-1]
        user = request.user
        if user is None:
            request.session.flash('Please sign in to use staff tools.', 'help')
            return require_signin(request)
        if not is_staff(user):
            return HTTPUnauthorized()
        return view_callable(request)
    return decorator


@staff_signin_required
def index(request):
    return {}


def _submission_short_text(submission):
    return 'submission by %s on %s called %s' % (
                link_person(submission.creation_stamp.person),
                date(submission.creation_stamp.timestamp),
                submission.identifier)


@staff_signin_required
def _moderate_submission(request):
    try:
        submission_id = request.params['submission_id']
        submission = models.Submission.get_id(submission_id)
    except KeyError:
        request.session.flash(
            'A submission must be specified', 'help')
        return
    if not submission:
        request.session.flash(
            'No submission %s' % submission_id, 'help')
        return

    try:
        action = request.params['action']
    except KeyError:
        request.session.flash(
            'Please specify an action to take on the submission', 'help')
        return

    allowed_actions = ['Accept', 'Acknowledge', 'Reject', ]
    if action not in allowed_actions:
        request.session.flash(
            'The action must be one of %s' % ', '.join(allowed_actions), 'help')
        return

    if action == 'Acknowledge':
        submission.acknowledge(request.user)
        request.session.flash(
            'Acknowleged %s' % _submission_short_text(submission),
            'action_taken')
        return

    if action == 'Reject':
        submission.reject(request.user)
        request.session.flash(
            'Rejected %s' % _submission_short_text(submission),
            'action_taken')
        return

    cruise_id = request.params['cruise_id']
    data_type = request.params['data_type']

    cruise = models.Cruise.get_id(cruise_id)
    if not cruise:
        cruises = models.Cruise.get_by_attrs(expocode=cruise_id)
        if len(cruises) > 0:
            cruise = cruises[0]
        else:
            request.session.flash(
                'Could not find a cruise using %s' % cruise_id, 'help')
            return

    attr = cruise.set(data_type, submission.file, request.user)
    submission.attach(attr, request.user)

    request.session.flash(
        'Attached %s to %s as %s' % (_submission_short_text(submission), 
                                     link_cruise(cruise),
                                     data_type), 'action_taken')


@staff_signin_required
def submissions(request):
    method = _http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_submission(request)
    submissions = models.Submission.map_mongo(
                      models.sort_by_stamp(models.Submission.find()))
    submissions = _paged(request, submissions)

    return {
        'submissions': submissions,
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


@staff_signin_required
def _moderate_attribute(request):
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


@staff_signin_required
def moderation(request):
    method = _http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_attribute(request)

    pending = models._Attr.pending()

    files_by_parameters = {}
    for p in pending:
        for note in p.notes:
            if note.data_type == 'Parameters':
                try:
                    l = files_by_parameters[note.body]
                except KeyError:
                    l = files_by_parameters[note.body] = {}
                try:
                    m = l[p.obj]
                except KeyError:
                    m = l[p.obj] = set()
                m.add(p)

    parameters = _paged(request, sorted(files_by_parameters.keys()))

    return {
        'parameters': parameters,
        'files_by_parameters': files_by_parameters,
    }
