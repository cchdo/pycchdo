import cgi
import tarfile
import os
import tempfile
import time
import shutil
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from collections import OrderedDict

from pyramid.httpexceptions import HTTPUnauthorized

from pycchdo.helpers import (
    link_cruise, pdate, link_person, whtext, has_staff, link_submission, link_q
    )
from pycchdo.models.serial import Submission, OldSubmission, Change

from pycchdo.views import *
from pycchdo.views.common import get_cruise
from pycchdo.views.session import signin_required, require_signin


def _check_signin_staff(request):
    user = request.user
    if user is None:
        request.session.flash('Please sign in to use staff tools.', 'help')
        return require_signin(request)
    if not has_staff(request):
        raise HTTPUnauthorized()
    return None


def staff_signin_required(view_callable):
    return signin_required(_check_signin_staff)(view_callable)


@staff_signin_required
def index(request):
    return {}


def _submission_short_text(submission):
    return 'submission {0}'.format(link_submission(submission))


def _moderate_submission(request):
    try:
        submission_id = request.params['submission_id']
        submission = Submission.get_id(submission_id)
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
            'Acknowleged {0}'.format(_submission_short_text(submission)),
            'action_taken')
        return

    if action == 'Reject':
        submission.reject(request.user)
        request.session.flash(
            'Rejected {0}'.format(_submission_short_text(submission)),
            'action_taken')
        return

    cruise_id = request.params['cruise_id']
    data_type = request.params['data_type']

    try:
        cruise = get_cruise(cruise_id)
    except ValueError:
        request.session.flash(
            'Could not find a cruise using %s' % cruise_id, 'help')
        return

    attr = cruise.set(data_type, submission.file, request.user)
    attr.accept(request.user)
    submission.attach(attr, request.user)

    request.session.flash(
        'Attached {0} as Q {1}'.format(
            _submission_short_text(submission), 
            link_q(request, attr)), 'action_taken')


list_queries = OrderedDict([
    ['Not queued not Argo', lambda: Submission.query().filter(
            Submission.attached == None, Submission.type != 'argo')],
    ['Not queued all', lambda: Submission.query().filter(Submission.attached == None)],
    ['Argo', lambda: Submission.query().filter(Submission.type == 'argo')],
    ['Queued', lambda: Submission.query().filter(Submission.attached != None)],
    ['All', lambda: Submission.query()],
    ['Old Submissions', lambda: OldSubmission.query()],
    ['unassigned', lambda: Submission.query()],
])


@staff_signin_required
def submissions(request):
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_submission(request)

    ltype = request.params.get('ltype', 'Not Queued not argo')

    try:
        squery = list_queries[ltype]()
    except KeyError:
        if ltype == 'id':
            squery = Submission.query().filter(Submission.id == request.params['query'])
        else:
            squery = list_queries['Not queued not Argo']()
        
    submissions = squery.join(Submission._changes).\
        order_by(Change.ts_c.desc()).\
        all()

    submissions = paged(request, submissions)

    return {
        'ltype': ltype,
        'lqueries': list_queries,
        'submissions': submissions,
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


def _moderate_attribute(request):
    try:
        attr = Change.get_id(request.params['attr'])
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
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_attribute(request)

    #pending = Change.pending()

    #files_by_parameters = {}
    #for attr in pending:
    #    for note in attr.notes:
    #        if note.data_type == 'Parameters':
    #            try:
    #                l = files_by_parameters[note.body]
    #            except KeyError:
    #                l = files_by_parameters[note.body] = {}
    #            try:
    #                m = l[attr.obj]
    #            except KeyError:
    #                m = l[attr.obj] = set()
    #            m.add(attr)

    #parameters = paged(request, sorted(files_by_parameters.keys()))

    parameters = []
    files_by_parameters = []

    dtc_to_q = {}
    pending = Change.pending_data()
    attr_sub = {}
    for attr in pending:
        key = (attr.ts_c, attr.obj)
        try:
            dtc_to_q[key].append(attr)
        except KeyError:
            dtc_to_q[key] = [attr]
        attr_sub[attr.id] = attr.submission

    dtc = paged(request, sorted(dtc_to_q.keys(), reverse=True))

    return {
        'parameters': parameters,
        'files_by_parameters': files_by_parameters,
        'dtc': dtc,
        'dtc_to_q': dtc_to_q,
        'attr_sub': attr_sub,
    }


def _archive_path(cruise, tree=[]):
    """ Gives the archive path for the cruise
    
    Arguments:
        tree - describes the path components. e.g. a cruise '33RR2009____' with
        a ship named 'Revelle' and date_start year 2009 along with tree=['ship',
        'date_start'] will produce a path /revelle/2009/33RR2009____

    """
    urlify = whtext.urlify
    cruise_id = urlify(str(cruise.uid))
    try:
        ship = urlify(cruise.ship.name)
    except AttributeError:
        ship = 'unk_ship'
    try:
        date_start = urlify(str(cruise.date_start.year))
    except AttributeError:
        date_start = 'unk_year'
    parts = []
    for branch in tree:
        if branch == 'ship':
            parts.append(ship)
        elif branch == 'date_start':
            parts.append(date_start)
    parts.append(cruise_id)
    return os.path.join(*parts)


@staff_signin_required
def archive(request, cruises, filename='archive.tbz', formats=['exchange'],
            tree=['ship', 'date_start']):
    """ Produce an archive of data files for the specified cruises

    Arguments:
        formats - limits the file formats returned
        tree - see _archive_path
    """
    tempdir = tempfile.mkdtemp()

    for cruise in cruises:
        path = os.path.join(tempdir, _archive_path(cruise, tree))
        for type, file in cruise.files.items():
            if not any(type.endswith(format) for format in formats):
                continue

            try:
                os.makedirs(path)
            except OSError:
                pass
            filepath = os.path.join(path, file.name)

            with open(filepath, 'w') as f:
                f.write(file.read())

            now = time.time()
            d = file.upload_date
            created = time.mktime(d.timetuple())
            os.utime(filepath, (now, created))

    temp = tempfile.SpooledTemporaryFile()
    archive = tarfile.open(mode='w:bz2', fileobj=temp)
    savedir = os.getcwd()
    os.chdir(tempdir)
    archive.add('.')
    os.chdir(savedir)
    archive.close()
    shutil.rmtree(tempdir)

    field = cgi.FieldStorage()
    field.name = filename
    field.file = temp
    field.content_type = 'application/x-tar-bz2'
    temp.seek(0, os.SEEK_END)
    field.length = temp.tell()
    temp.seek(0)
    return file_response(request, field, 'attachment')
