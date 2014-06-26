from cgi import FieldStorage
import tarfile
import os
import tempfile
import time
import shutil
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from collections import OrderedDict, defaultdict
from zipfile import BadZipfile

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, subqueryload

from pyramid.httpexceptions import (
    HTTPUnauthorized, HTTPBadRequest, HTTPSeeOther,
    )

import transaction

from pycchdo.helpers import (
    link_cruise, pdate, link_person, whtext, has_edit, has_staff,
    link_submission, link_asr, path_asr, 
    )
from pycchdo.models.serial import (
    store_context, DBSession, Submission, OldSubmission, Change, Cruise, Person,
    Note, FSFile,
    )

from pycchdo.views import *
from pycchdo.views.session import signin_required, require_signin
from pycchdo.mail import send_asr_attach_confirmation, asr_history_body
from pycchdo.log import getLogger


log = getLogger(__name__)


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
    return 'S {0}'.format(link_submission(submission))


def _moderate_submission(request):
    try:
        submission_id = request.params['submission_id']
        submission = Submission.query().get(submission_id)
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

    allowed_actions = ['Accept', 'Acknowledge', 'release', 'Reject', ]
    if action not in allowed_actions:
        request.session.flash(
            'The action must be one of %s' % ', '.join(allowed_actions), 'help')
        return

    if action == 'Acknowledge':
        submission.change.acknowledge(request.user)
        request.session.flash(
            'Claimed {0}'.format(_submission_short_text(submission)),
            'action_taken')
        return
    elif action == 'release':
        submission.change.ts_ack = None
        submission.change.p_ack = None
        request.session.flash(
            'Released {0}'.format(_submission_short_text(submission)),
            'action_taken')
        return
    elif action == 'Reject':
        submission.change.reject(request.user)
        request.session.flash(
            'Discarded {0}'.format(_submission_short_text(submission)),
            'action_taken')
        return

    # Attaching
    try:
        cruise_id = request.params['cruise_id']
        data_type = request.params['data_type']
        parameters = request.params['parameters']
    except KeyError:
        request.response.status = 400
        request.session.flash('Invalid arguments to attach', 'help')
        return
    fname = request.params.get('fname', None)
    if not parameters:
        parameters = None

    try:
        cruise = Cruise.get_by_id(cruise_id)
    except ValueError:
        request.session.flash(
            'Could not find a cruise using %s' % cruise_id, 'help')
        return

    asr_specs = []
    if submission.is_multiple():
        try:
            with    store_context(request.registry.settings['fsstore']), \
                    submission.multiple_files() as zfile:
                if fname is None:
                    # Attach all of the multiple files as separate ASRs to the
                    # same cruise.
                    for zinfo in zfile.infolist():
                        data = FieldStorage()
                        data.filename = zinfo.filename
                        data.file = zfile.open(zinfo)
                        data = FSFile.from_fieldstorage(data)
                        asr_specs.append((cruise, data_type, data, parameters))
                else:
                    zinfo = zfile.getinfo(fname)
                    if not zinfo:
                        request.session.flash(
                            'Could not find file to attach', 'help')
                        return
                    data = FieldStorage()
                    data.filename = fname
                    data.file = zfile.open(zinfo)
                    data = FSFile.from_fieldstorage(data)
                    asr_specs.append((cruise, data_type, data, parameters))
        except BadZipfile:
            log.error(u'Unable to attach due to bad zip file.')
            request.response.status = 500
            request.session.flash('Could not attach bad zip file', 'error')
            return
    else:
        asr_specs.append((cruise, data_type, submission.file, parameters))
    asrs = create_asrs(request, request.user, asr_specs)
    submission.attached.extend(asrs)

    asr_text = ', '.join([link_asr(request, asr) for asr in asrs])
    request.session.flash(
        'Attached {0} as {1}'.format(_submission_short_text(submission), 
            asr_text), 'action_taken')


def create_asrs_history(request, signer, cruise, asrs):
    body = asr_history_body(request, asrs)
    action = 'Data available'
    summary = 'As Received'
    cruise.change._notes.append(Note(signer, body, action, subject=summary))
    send_asr_attach_confirmation(request, asrs)


def create_asr(request, signer, cruise, data_type, fsfile, parameters=None,
               batched=False):
    """Add data as a suggestion and send As Received confirmation email."""
    try:
        with store_context(request.registry.settings['fsstore']):
            asr = cruise.sugg(signer, data_type, fsfile)
            if parameters is not None:
                asr._notes.append(Note(
                    signer, parameters, data_type='parameters',
                    discussion=True))
            if not batched:
                create_asrs_history(request, signer, cruise, [asr])
            return asr
    except ValueError, err:
        request.response.status = 400
        request.session.flash('help', 'error')
        return


def create_asrs(request, signer, asr_specs):
    all_asrs = []
    grouped_short_specs = defaultdict(list)
    for asr_spec in asr_specs:
        cruise = asr_spec[0]
        short_spec = asr_spec[1:]
        grouped_short_specs[cruise].append(short_spec)
    for cruise, short_specs in grouped_short_specs.items():
        asrs = []
        for data_type, fsf, parameters in short_specs:
            asrs.append(
                create_asr(request, signer, cruise, data_type, fsf, parameters,
                           batched=True))
        create_asrs_history(request, signer, cruise, asrs)
        all_asrs += asrs
    return all_asrs


list_queries = OrderedDict([
    ['Not attached not Argo', lambda _: Submission.filtered(attached=False, argo_type=False)],
    ['Not attached all', lambda _: Submission.filtered(attached=False)],
    ['Argo', lambda _: Submission.filtered(argo_type=True)],
    ['Attached', lambda _: Submission.filtered(attached=True)],
    ['All', lambda _: Submission.query()],
    ['Old Submissions', lambda _: OldSubmission.query()],
    ['id', lambda request: Submission.filtered(sid=request.params['query'])],
])


def submission_attach(request):
    method = http_method(request)
    if method == 'PUT':
        if not has_edit(request):
            raise HTTPUnauthorized()
        cruise_id = request.params.get('cruise_id')
        cruise = Cruise.get_by_id(cruise_id)
        if not cruise:
            request.response.status = 400
            request.session.flash(
                'Invalid cruise identifier', 'form_error_cruise_id')
        data_type = request.params.get('data_type', 'data_suggestion')
        parameters = request.params.get('parameters', '')
        data = request.POST.get('data', None)
        if data is None:
            request.response.status = 400
            request.session.flash('Invalid data', 'form_error_data')

        if request.response.status == 400:
            pass
        else:
            asr = create_asr(request, request.user, cruise, data_type, data,
                             parameters)
            request.session.flash(
                'Attached data As Received {0}'.format(link_asr(request, asr)),
                'action_taken')
            return HTTPSeeOther(location=path_asr(request, asr))
    else:
        if not has_edit(request):
            request.session.flash(PLEASE_SIGNIN_MESSAGE, 'help')
            request.referrer = request.url
            return require_signin(request)
    return {'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT}


def _get_default_list_query():
    return list_queries.keys()[0]


@staff_signin_required
def submissions(request):
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_submission(request)

    query = request.params.get('query', '')
    ltype = request.params.get('ltype', _get_default_list_query())
    try:
        squery = list_queries[ltype](request)
    except KeyError:
        query = request.params
        query['ltype'] = _get_default_list_query()
        return HTTPSeeOther(location=request.current_route_path(_query=query))
    squery = squery.with_transformation(Submission.change.join)
    squery = squery.with_transformation(Change.p_c.join)
    if query and ltype != 'id':
        likestr = '%{0}%'.format(query)
        or_list = [
            Submission.expocode.ilike(likestr),
            Submission.ship_name.ilike(likestr),
            Submission.line.ilike(likestr),
            Change.p_c._aliased.name.ilike(likestr),
        ]
        try:
            int(query)
            or_list.append(Submission.id == query)
        except ValueError:
            pass
        squery = squery.filter(or_(*or_list))
    squery = squery.order_by(Submission.change._aliased.ts_c.desc())
    submissions = squery.all()
    submissions = paged(request, submissions)

    return {
        'ltype': ltype,
        'lqueries': list_queries,
        'query': query,
        'submissions': submissions,
        'FILE_GROUPS_SELECT': FILE_GROUPS_SELECT,
        }


def _moderate_attribute(request):
    """Edit a Change.

    Actions:
      * Acknowledge
      * Accept
      * Reject
      * create - create an ASR given a cruise, data_type, and FieldStorage
        params: cruise_id 
        params: data - POSTed file

    """
    action = request.params['action']
    if action not in ('Acknowledge', 'Accept', 'Reject', 'create'):
        request.response_status = ('400 Bad action')
        return

    if action == 'create':
        cruise = Cruise.get_by_id(request.params['cruise_id'])
        data_type = request.params['data_type']
        parameters = request.params.get('parameters', None)
        asr = create_asr(
            request, request.user, cruise, data_type, request.POST['data'],
            parameters)
        return

    try:
        attr = Change.query().get(request.params['attr'])
    except KeyError:
        request.response_status = '400 No attribute to modify'
        return
    except ValueError:
        request.response_status = '404 Attribute to modify not found'
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
    """List of Changes to be reviewed.

    """
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_attribute(request)

    pending = Change.filtered_data('unjudged',
        query_modifier=lambda q: q.options(joinedload('submission')))

    dtc_to_q = {}
    for change in pending:
        key = (change.ts_c, change.obj)
        try:
            dtc_to_q[key].append(change)
        except KeyError:
            dtc_to_q[key] = [change]

    dtc = paged(request, sorted(dtc_to_q.keys(), reverse=True))

    return {
        'dtc': dtc,
        'dtc_to_q': dtc_to_q,
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

    field = FieldStorage()
    field.name = filename
    field.file = temp
    field.content_type = 'application/x-tar-bz2'
    temp.seek(0, os.SEEK_END)
    field.length = temp.tell()
    temp.seek(0)
    return file_response(request, field, 'attachment')
