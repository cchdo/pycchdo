from StringIO import StringIO
from collections import OrderedDict, defaultdict

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message, Attachment

from libcchdo.fns import uniquify
from libcchdo.datadir.util import q_from_uow_cfg
from libcchdo.datadir.filenames import README_FILENAME
from libcchdo.datadir.processing import ProcessingEmail, parse_readme

from pycchdo import helpers as h
from pycchdo.log import getLogger


log = getLogger(__name__)


def send(request, message):
    mailer = get_mailer(request)
    mailer.send_sendmail(message)


def get_email_addresses(request, key, start=[]):
    """Email addresses for given emails plus given configuration setting."""
    recipient = request.registry.settings.get(key, None)
    return filter(None, start + [recipient])


def _submission_public_status_to_description(status):
    if status == 'public':
        return 'will be public'
    elif status == 'non_public':
        return 'will *not* be public'
    elif status == 'non_public_argo':
        return 'will be available for use exclusively by the Argo program'


def send_submission_confirmation(request, d, submissions):
    recipients = get_email_addresses(request, 'recipient_submission_confirm',
                                       [request.user.email])

    d['user_name'] = request.user.name
    d['file_noun'] = h.whtext.plural(
        len(d['file_names']), 'file', 'files', False)

    d['public_description'] = _submission_public_status_to_description(
        d['public_status'])
    d['file_list'] = '\n'.join(d['file_names'])
    d['actions'] = '\n'.join(d['action_list'])

    body_parts = []
    body = """\
Dear {user_name}:

Thank you for your submission to the CCHDO.

This is an automated confirmation. However, replying to the sender will reach 
all senior CCHDO staff.

Your submitted {file_noun}:
{file_list}

{public_description}.

The following actions were specified:
{actions}

Additional information collected:
""".format(**d)
    if d['institution']:
        body_parts.append('Institution: ' + d['institution'])
    if d['country']:
        body_parts.append('Country: ' + d['country'])
    if d['identifier'] or d['woce_line']:
        parts = []
        if d['identifier']:
            parts.append('ExpoCode: ' + d['identifier'])
        if d['woce_line']:
            parts.append('Line: ' + d['woce_line'])
        body_parts.append(' '.join(parts))
    if d['ship']:
        body_parts.append('Ship: ' + d['ship'])
    if d['cruise_dates']:
        body_parts.append(
            'Dates: ' + datetime.strftime(d['cruise_dates'], '%Y-%m-%d'))
    if d['notes']:
        body_parts.append('Notes: ' + d['notes'] + '\n')
    body_parts.append('Thank you again for your submission.\n')
    body_parts.append('---\n')
    for sub in submissions:
        body_parts.append(request.route_url('staff_submissions',
            _query={'ltype': 'id', 'query': sub.id}) + '\n')

    body += '\n'.join(body_parts)

    message = Message(
        subject="[CCHDO] Submission by {name}: {id}".format(
            name=d['user_name'],
            id=' '.join([d['woce_line'], d['identifier']])),
        sender=get_email_addresses(request, 'from_address')[0],
        recipients=recipients,
        body=body,
    )
    send(request, message)


def asr_history_body(request, asrs):
    """Create a history note body for ASRs."""
    cruises_asrs = defaultdict(list)
    for asr in asrs:
        cruises_asrs[asr.obj].append(asr)
    cruise_data = []
    for cruise, asrs in cruises_asrs.items():
        cruise_data.append(
            request.route_url('cruise_show', cruise_id=cruise.uid))
        for asr in asrs:
            note = asr.note_for_data_type('parameters')
            if note:
                note = note.body
            else:
                note = ''
            cruise_data.append('\t{0}\t{1}'.format(asr.value.name, note))
    cruise_data = "\n".join(cruise_data)
    body = """\
The following data are now available As Received, unprocessed by the CCHDO.

{0}
""".format(cruise_data)
    return body


def send_asr_attach_confirmation(request, asrs):
    dates = []
    dtypes = []
    expocodes = []
    for asr in asrs:
        dates.append(asr.ts_c)
        note = asr.note_for_data_type('parameters')
        if note is not None:
            dtypes.append(note.body)
        expocodes.append(str(asr.obj.uid))
    dtypes = '/'.join(uniquify(dtypes))

    expocode = ', '.join(expocodes)
    date = min(dates)

    body = """\
Dear CCHDO community,

This is an automated message on {date}.

{body}
""".format(date=date.strftime('%F'), body=asr_history_body(request, asrs))

    subject_items = ["Data available As Received for {0}".format(expocode)]
    if dtypes:
        subject_items.append(dtypes)
    subject = ' - '.join(subject_items)

    recipients = get_email_addresses(request, 'recipient_asr_confirm')
    message = Message(
        subject=subject,
        sender=get_email_addresses(request, 'from_address')[0],
        recipients=recipients,
        body=body,
    )
    send(request, message)


def send_processing_email(request, readme_str, uow_cfg, note_id, dryrun=True):
    uid = uow_cfg['expocode']
    asrs, asr_ids = q_from_uow_cfg(uow_cfg)
    title, merger, subject = parse_readme(readme_str)
    recipients = get_email_addresses(request, 'recipient_processing')
    if dryrun:
        subject = 'DRYRUN {0}'.format(subject)
        recipients = [request.user.email]
    body = ProcessingEmail(dryrun).generate_body(
        merger, uid, asrs, note_id, asr_ids)
    message = Message(
        subject=subject,
        sender=get_email_addresses(request, 'from_address')[0],
        recipients=recipients,
        body=body,
    )
    readme_fobj = StringIO(readme_str)
    attachment = Attachment(README_FILENAME, "text/plain", readme_fobj)
    message.attach(attachment)
    send(request, message)
