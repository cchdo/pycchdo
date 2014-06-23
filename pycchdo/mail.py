from collections import OrderedDict, defaultdict

from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message

from libcchdo.fns import uniquify

from pycchdo.log import getLogger


log = getLogger(__name__)


def send(request, message):
    mailer = get_mailer(request)
    mailer.send_sendmail(message)


from_addr = 'cchdo@ucsd.edu'


def _get_email_recipients(request, key, start=[]):
    recipient = request.registry.settings.get(key, None)
    return filter(None, start + [recipient])


def send_submission_confirmation(request, d, submissions):
    recipients = _get_email_recipients(request, 'recipient_submission_confirm',
                                       [request.user.email])

    d['user_name'] = request.user.name
    d['file_noun'] = h.whtext.plural(
        len(d['file_names']), 'file', 'files', False)

    if d['public_status'] == 'public':
        d['public_description'] = 'will be public'
    elif d['public_status'] == 'non_public':
        d['public_description'] = 'will *not* be public'
    elif d['public_status'] == 'non_public_argo':
        d['public_description'] = \
            'will be available for use exclusively by the Argo program'
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
        sender=from_addr,
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

    recipients = _get_email_recipients(request, 'recipient_asr_confirm')
    message = Message(
        subject=subject,
        sender=from_addr,
        recipients=recipients,
        body=body,
    )
    send(request, message)
