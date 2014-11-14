from cgi import FieldStorage
import tarfile
import os
import tempfile
import time
import shutil
from json import loads as json_loads
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from collections import OrderedDict, defaultdict
from zipfile import BadZipfile

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, subqueryload

from pyramid.response import FileResponse
from pyramid.httpexceptions import (
    HTTPUnauthorized, HTTPBadRequest, HTTPSeeOther, HTTPMethodNotAllowed,
    )

import transaction

from libcchdo.datadir.processing import mkdir_working
from libcchdo.datadir.util import DirName
from libcchdo.datadir.filenames import README_FILENAME

from pycchdo.helpers import (
    link_cruise, pdate, link_person, whtext, has_edit, has_staff, has_mod,
    link_submission, link_asr, path_asr, 
    )
from pycchdo.models.serial import (
    store_context, DBSession, Submission, OldSubmission, Change, Cruise, Person,
    Note, FSFile, UOW,
    )
from pycchdo.models.searchsort import SubmissionSorter

from pycchdo.views import *
from pycchdo.views.session import signin_required, require_signin
from pycchdo.mail import (
    send_asr_attach_confirmation, asr_history_body, send_processing_email,
    )
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
        asr = cruise.sugg(signer, data_type, fsfile)
        if parameters is not None:
            asr._notes.append(Note(
                signer, parameters, data_type='parameters',
                discussion=True))
        if has_mod(request):
            asr.acknowledge(signer)
            if not batched:
                create_asrs_history(request, signer, cruise, [asr])
        return asr
    except ValueError, err:
        log.error(err)
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
        if has_mod(request):
            create_asrs_history(request, signer, cruise, asrs)
        all_asrs += asrs
    return all_asrs


def _query_submission_by_id(request):
    sid = request.params['query']
    if not sid:
        return Submission.query().filter(False)
    return Submission.filtered(sid=sid)


list_queries = OrderedDict([
    ['Not attached not Argo', lambda _: Submission.filtered(attached=False, argo_type=False)],
    ['Not attached all', lambda _: Submission.filtered(attached=False)],
    ['Argo', lambda _: Submission.filtered(argo_type=True)],
    ['Attached', lambda _: Submission.filtered(attached=True)],
    ['All', lambda _: Submission.query()],
    ['Old Submissions', lambda _: OldSubmission.query()],
    ['id', _query_submission_by_id],
])


def submission_attach(request):
    """Attach data directly to a cruise.

    This can be used by both editors and moderators. Moderator edits result in
    automatic acknowledgement.

    """
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
            if not asr:
                return
            msg = 'Attached data As Received {0}'.format(link_asr(request, asr))
            if not has_mod(request):
                msg += ' to be reviewed by staff before made public'
            request.session.flash(msg, 'action_taken')
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
    sorter = SubmissionSorter(request.params.get('orderby', ''))
    try:
        squery = list_queries[ltype](request)
    except KeyError:
        # Redirect to default ltype
        query = request.params.dict_of_lists()
        query['ltype'] = _get_default_list_query()
        return HTTPSeeOther(location=request.current_route_path(_query=query))
    squery = squery.with_transformation(Submission.change.join)
    squery = squery.with_transformation(Change.p_c.join)
    squery = squery.with_transformation(Change.notes.join)
    if query and ltype != 'id':
        likestr = '%{0}%'.format(query)
        or_list = [
            Submission.expocode.ilike(likestr),
            Submission.ship_name.ilike(likestr),
            Submission.line.ilike(likestr),
            Change.p_c._aliased.name.ilike(likestr),
            Submission.line.ilike(likestr),
            Change.notes._aliased.body.ilike(likestr),
        ]
        try:
            int(query)
            or_list.append(Submission.id == query)
        except ValueError:
            raise HTTPBadRequest()
        squery = squery.filter(or_(*or_list))
    squery = squery.order_by(Submission.change._aliased.ts_c.desc())
    submissions = sorter.sort(squery.all())
    submissions = paged(request, submissions)

    return {
        'ltype': ltype,
        'lqueries': list_queries,
        'sorter': sorter,
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
        create_asrs_history(request, request.user, attr.obj, [attr])
    else:
        if attr.is_judged():
            request.response_status = '400 Attempt to modify judged attribute'
            return
        if action == 'Accept':
            attr.accept(request.user)
        else:
            attr.reject(request.user)


def _int_ids(ids):
    """Convert list of string ids to int ids."""
    int_ids = []
    for iid in ids:
        try:
            int_ids.append(int(iid))
        except ValueError:
            pass
    return int_ids


def _pending_changes(request):
    """A list of pending data Changes.

    May be filtered by id. In this case, ids will be returned regardless of
    pending status.

    :returns: A list of pending data Changes.

    """
    text_ids = request.params.get('ids', '')
    ids = _int_ids(filter(None, text_ids.split(',')))
    qmod = lambda q: q.options(joinedload('submission'))
    if text_ids:
        p_qmod = qmod
        qmod = lambda q: p_qmod(q.filter(Change.id.in_(ids)))
        return Change.filtered(query_modifier=qmod)
    return Change.filtered_data('unjudged', query_modifier=qmod)


@staff_signin_required
def as_received(request):
    """Return the data changes.

    If ids is not specified, return all Changes not judged.

    GET /staff/moderation.json
    data:
        ids - (optional) comma separated integers
    returns:
        list of Changes in JSON

    """
    return _pending_changes(request)


def _tar_response(request, fname, callback):
    """Return a FileResponse with a tarball of the tempdir.

    Arguments:
        request - the original request being responded to
        fname - the file name for the tarball
        callback(archive) - a function

    """
    with tempfile.NamedTemporaryFile(delete=True) as temp:
        archive = tarfile.open(mode='w:bz2', fileobj=temp)
        try:
            callback(archive)
        finally:
            archive.close()

        temp.seek(0)
        return FileResponse(temp.name, request,
                            content_type='application/x-tar-bz2')


def _tar_add_dir(archive, tempdir):
    savedir = os.getcwd()
    os.chdir(tempdir)
    try:
        archive.add('.')
    finally:
        os.chdir(savedir)


def copy_fsfile_to(fsstore, fsfile, path):
    with store_context(fsstore):
        fpath = fsstore_path(fsstore, fsfile)
        tarpath = os.path.join(path, fsfile.name)
        try:
            shutil.copyfile(fpath, tarpath)
        except (IOError, OSError):
            log.error(u'Missing file {0}'.format(fsfile))


def _sanitize_for_fname(string):
    return "".join([
        c for c in string if c.isalpha() or c.isdigit()]).rstrip()


class CruiseHistoryRepr(object):
    """Construct a directory representing the cruise's data change history."""

    def __init__(self, fsstore, dirpath, cruise):
        self.fsstore = fsstore
        self.dirpath = dirpath
        self.cruise = cruise

        self._uows = set()

        self.asr_dir = os.path.join(dirpath, 'asr')
        self.merged_dir = os.path.join(dirpath, 'merged')

        self.archive()
        self.changes()
        self.uows()

    def archive(self):
        archive = self.cruise.files.get('archive', None)
        if archive:
            copy_fsfile_to(self.fsstore, archive.file, self.dirpath)

    def change(self, change):
        # There are three cases of how to display a change in history
        # Case 1: accepted with new value
        # Case 2: accepted value
        # Case 3: pending value
        # In all other cases, the data should not be shown in history.

# Modes in which data can be added to a cruise
# 1. assimilating from submissions
# 2. direct addition to cruise

# Cruise
# Case 3 - in ASR
#  1. data_suggestion btlex_bob (assimilated, pending)
#  3. bottle_exchange btlex (assimilated,     pending)
#  4. bottle_exchange btlex (directly added,  pending)
# Case 1 - original value in originals, accepted value in tgo
#  2. data_suggestion ctdex_bob ctdex (assimilated, accepted with value)
#  6. bottle_exchange btlex btlex2 (directly added, accepted with value)
# Case 2 - accepted value in tgo
#  5. bottle_exchange btlex (directly added, accepted)
#  7. bottle_exchange btlex (directly set,   accepted)

# If the change is not part of a UOW, it is from the import.
# Case 4 - in merged

        # If the change is part of a UOW, use that information to generate the
        # work directory in history. Otherwise, the work directory is simpler
        # and only based on the change itself.

        # work directories follow the format:
        #  date_summary_who
        #   * submissions - data causing the change
        #   * originals   - data being changed
        #   * processing  - supporting documentation (00_README.txt, processing)
        #   * tgo         - new data

        if change.is_accepted():
            # Case 1
            if not change.sugg_uows and not change.result_uows:
                # Case 1a - original (if any) in asr, accepted in merged
                work_dir = self.work_dir(self.dirpath, change.p_c.uid,
                                         str(change.id), change.ts_c)
                if change._value_accepted:
                    change_dir = os.path.join(work_dir, DirName.original)
                    copy_fsfile_to(
                        self.fsstore, change.value_original, change_dir)
                change_dir = os.path.join(work_dir, DirName.tgo)
                copy_fsfile_to(
                    self.fsstore, change.value, change_dir)
            else:
                # Case 1b
                self._uows |= set(change.sugg_uows)
                self._uows |= set(change.result_uows)
        elif change.is_acknowledged():
            # Case 2 - value in ASR
            change_dir = os.path.join(self.asr_dir, str(change.id))
            os.makedirs(change_dir)
            copy_fsfile_to(self.fsstore, change.value, change_dir)

    def changes(self):
        # reconstruct the history of a cruise by replaying the changes
        changes = self.cruise._changes.order_by(Change.ts_c.asc()).all()

        for change in changes:
            if not change.is_data():
                continue
            if change.attr == 'archive':
                continue
            self.change(change)

    def work_dir(self, basepath, person, title, dtime, has_processing=False):
        person = _sanitize_for_fname(person)
        title = _sanitize_for_fname(title)
        return mkdir_working(self.dirpath, person, title, dtime,
                             processing_subdirs=has_processing)

    def uow(self, uow):
        work_dir = self.work_dir(self.dirpath, uow.note.p_c.uid,
                                 uow.note.subject, uow.results[0].ts_j)
        orig_dir = os.path.join(work_dir, DirName.original)
        sub_dir = os.path.join(work_dir, DirName.submission)
        tgo_dir = os.path.join(work_dir, DirName.tgo)

        with open(os.path.join(work_dir, README_FILENAME), 'w') as fff:
            fff.write(uow.note.body)

        for change in uow.suggestions:
            if change in uow.results:
                continue
            # if a change is a suggestion of a uow, its original value should
            # appear in submissions. accepted value should go in originals
            if change._value_accepted:
                copy_fsfile_to(self.fsstore, change.value_original, sub_dir)
            copy_fsfile_to(self.fsstore, change.value, orig_dir)

        for change in uow.results:
            # If a change is a result of a uow, its original value should appear
            # in submissions and its accepted value should appear in tgo
            if change._value_accepted:
                copy_fsfile_to(self.fsstore, change.value_original, sub_dir)
            copy_fsfile_to(self.fsstore, change.value, tgo_dir)

    def uows(self):
        for uow in self._uows:
            self.uow(uow)


def _uow_fetch(request):
    """Fetch a cruise's history.

    GET /staff/uow

    Fetch a UOW's history because creating the actual directory is better
    handled by the client.

    data:
        cruise_id - the cruise to fetch history for

    raises:
        HTTPBadRequest - if no cruise_id
        HTTPNotFound - if the cruise is not found

    response:
        a tarball containing a reconstructed original directory

    """
    try:
        cid = request.params['cruise_id']
    except KeyError:
        raise HTTPBadRequest()
    cruise = Cruise.get_by_id(cid)
    if not cruise:
        raise HTTPNotFound()

    tempdir = tempfile.mkdtemp()
    try:
        fsstore = request.registry.settings['fsstore']
        CruiseHistoryRepr(fsstore, tempdir, cruise)
        fname = 'uow.{0}.original.tar.bz2'.format(cid)
        return _tar_response(
            request, fname, lambda arc: _tar_add_dir(arc, tempdir))
    finally:
        shutil.rmtree(tempdir)


def _json_response(request, msg, status=400):
    """Return a dict representation of an error for JSON purposes."""
    request.response.status = status
    return {"status": "error", "error": msg}


def _uow_commit(request):
    """Commit a UOW.

    POST /staff/uow
    data:
        fly - if not blank, confirms that the operation is not a dry run
        result[n] - a final result file to put in dataset
        result_types - a JSON array that maps the result files to the dataset
            data types
        support - a file that is stored as supporting documentation with the 
            UOW. Commonly a tar.
        uow_cfg - a JSON object representing the UOW configuration
        readme - the readme file, used for the history note

    """

    dryrun = not bool(request.params.get('fly', False))
    if dryrun:
        log.info(u'Dry run UOW commit')
        transaction.doom()
    else:
        log.info(u'UOW commit')

    results = {}
    for k, v in request.POST.items():
        if k.startswith('result['):
            key = int(k.split('[', 1)[1][:-1])
            results[key] = v
    if not results:
        log.error(u'UOW missing results')
        return _json_response(request, "No data changes")
    try:
        result_types = json_loads(request.params['result_types'])
        uow_cfg = json_loads(request.params['uow_cfg'])
        support = request.POST['support']
        readme_file = request.POST['readme']
    except KeyError as err:
        return _json_response(request, "Missing {0}".format(err))

    if len(results) != len(result_types):
        return _json_response(request, "Need result type for each result")

    expocode = uow_cfg['expocode']
    cruise = Cruise.get_by_id(expocode)
    person = request.user

    uow = UOW()
    DBSession.add(uow)

    uow.results = []
    for iii, rtype in enumerate(result_types):
        uow.results.append(cruise.set(person, rtype, results[iii]))

    uow.support = FSFile.from_fieldstorage(support)

    uow.suggestions = []
    for qinfo in uow_cfg['q_infos']:
        change = Change.query().get(qinfo['q_id'])
        change.accept(person)
        uow.suggestions.append(change)

    title = uow_cfg['title']
    summary = uow_cfg['summary']
    action = 'Website Update'

    readme_str = readme_file.file.read()
    note = Note(person, readme_str, action, title, summary)
    cruise.change._notes.append(note)
    uow.note = note

    DBSession.flush()

    send_processing_email(request, readme_str, uow_cfg, note.id, dryrun)

    if dryrun:
        log.info(u'Dryrun committed UOW')
    else:
        log.info(u'Committed UOW')
    return {'status': 'ok'}


@staff_signin_required
def uow(request):
    """UOW operations

    GET and POST allowed.

    """
    method = http_method(request)
    if method == 'GET':
        return _uow_fetch(request)
    elif method == 'POST':
        return _uow_commit(request)
    else:
        return HTTPMethodNotAllowed()


@staff_signin_required
def moderation(request):
    """List of Changes to be reviewed.

    """
    method = http_method(request)
    if method == 'PUT':
        if not request.user:
            return require_signin(request)
        _moderate_attribute(request)

    pending = _pending_changes(request)

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
    try:
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

        return _tar_response(
            request, fname, lambda arc: _tar_add_dir(arc, tempdir))
    finally:
        shutil.rmtree(tempdir)
