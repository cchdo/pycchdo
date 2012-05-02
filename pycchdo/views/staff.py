import inspect
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

from pyramid.httpexceptions import HTTPUnauthorized

from pycchdo.helpers import link_cruise, date, link_person, whtext
import pycchdo.models as models

from pycchdo.views import *
from pycchdo.helpers import has_staff
from pycchdo.views.session import require_signin


def staff_signin_required(view_callable):
    """ Decorates a view_callable so that the signed in user must be a staff
        member in order to view.
    """
    def check_signin(request):
        user = request.user
        if user is None:
            request.session.flash('Please sign in to use staff tools.', 'help')
            return require_signin(request)
        if not has_staff(request):
            raise HTTPUnauthorized()
        return None

    numargs = len(inspect.getargspec(view_callable)[0])
    if numargs == 1:
        def decorator(request):
            response = check_signin(request)
            if response is None:
                response = view_callable(request)
            return response
        return decorator
    elif numargs == 2:
        def decorator(context, request):
            response = check_signin(request)
            if response is None:
                response = view_callable(context, request)
            return response
        return decorator
    else:
        def decorator(*args, **kwargs):
            request = args[1]
            response = check_signin(request)
            if response is None:
                response = view_callable(*args, **kwargs)
            return response
        return decorator


@staff_signin_required
def index(request):
    return {}


def _submission_short_text(submission):
    return 'submission by %s on %s called %s' % (
                link_person(submission.creation_stamp.person),
                date(submission.creation_stamp.timestamp),
                submission.identifier)


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
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_submission(request)
    submissions = models.Submission.map_mongo(
                      models.sort_by_stamp(models.Submission.find()))
    submissions = paged(request, submissions)

    return {
        'submissions': submissions,
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


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
    method = http_method(request)
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

    parameters = paged(request, sorted(files_by_parameters.keys()))

    return {
        'parameters': parameters,
        'files_by_parameters': files_by_parameters,
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
                try:
                    f.write(file.read())
                except models.CorruptGridFile:
                    pass

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
