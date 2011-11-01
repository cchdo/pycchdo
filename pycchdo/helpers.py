import logging

import webhelpers.html as whh
import webhelpers.html.tags

import models


def has_mod(request):
    # TODO check against actual list
    if not request.user:
        return False
    return str(request.user.id) == '4e1492db1f121d1782000000'


def title(**kwargs):
    try:
        content = kwargs['caller']()
    except KeyError:
        content = None
    if content:
        return ' | ' + content
    return ''


def form_entered(request, key):
    entered_key = 'form_entered_' + key
    if request.session.peek_flash(entered_key):
        return request.session.pop_flash(entered_key)[0]
    return ''


def form_errors_for(request, key):
    error_key = 'form_error_' + key
    if request.session.peek_flash(error_key):
        errors = [whh.HTML.span(x, class_='form-error') for x in \
                  request.session.pop_flash(error_key)]
        return whh.literal(''.join(errors))
    return ''


def email_link(email, microformat_type=None, microformat_classes=[], content=None):
    """ Gives back a mailto link that is slightly obfuscated. """
    obfuscator = '+anti spam'
    parts = email.split('@')
    type = ''
    if microformat_type:
        type = whh.HTML.span(microformat_type, class_='type hidden')
    if not content:
        content = type + parts[0] + \
                  whh.HTML.span(obfuscator, class_='copythis') + '@' + parts[1]
    href = 'mailto:' + parts[0] + obfuscator + '@' + parts[1]
    classes = [('email', True)] + [(x, True) for x in microformat_classes]
    return whh.tags.link_to(content, href, class_=whh.tags.css_classes(classes))


def boxed(title='', bottom='', **attrs):
    classes = [('boxed', True)]
    box_content_classes = [('box_content', True)]
    box_bottom_classes = [('box_bottom', True)]
    try:
        classes.extend([(x, True) for x in attrs['class'].split()])
        del attrs['class']
    except KeyError:
        pass
    try:
        box_content_classes.extend(
            [(x, True) for x in attrs['box_content_class'].split()])
        del attrs['box_content_class']
    except KeyError:
        pass
    try:
        box_bottom_classes.extend(
            [(x, True) for x in attrs['box_bottom_class'].split()])
        del attrs['box_bottom_class']
    except KeyError:
        pass
    caller = lambda: ''
    try:
        caller = attrs['caller']
        del attrs['caller']
    except KeyError:
        pass
    return whh.HTML.div(whh.HTML(
                whh.HTML.h1(whh.HTML.literal(title)),
                whh.HTML.div(caller(),
                             class_=whh.tags.css_classes(box_content_classes)),
                whh.HTML.div(bottom,
                             class_=whh.tags.css_classes(box_bottom_classes))
            ), class_=whh.tags.css_classes(classes), _nl=True, **attrs)


def cruise_map_thumb(thumb=None, full=None, show_full_link=True):
    thumb_link = ''
    thumb_img = whh.tags.image(data_uri(thumb), 'Cruise Map thumbnail')
    if full:
        full_uri = data_uri(full)
        if thumb:
            thumb_link = whh.HTML.p(
                whh.tags.link_to(thumb_img, full_uri))
        thumb_link += whh.HTML.p(whh.tags.link_to('Full Map', full_uri),
                                 class_='caption')
    else:
        if thumb:
            thumb_link = whh.HTML.p(thumb_img)
    return whh.HTML.div(thumb_link, class_='thumb')


def cruise_history_rows(change, i, hl):
    """ Give the HTML table rows for a cruise history entry.
        
        i - The entry number
        hl - even or odd class name
    """

    baseclass = "mb-link{i} {hl}".format(i=i, hl=hl)

    if type(change) == models.Note:
        time = change.creation_stamp.timestamp.strftime('%Y-%m-%d')
        # TODO link to person?
        person = change.creation_stamp.person.full_name()
        data_type = change['data_type']
        action = change['action']
        summary = change['subject']
        body = change['body']
        if change.discussion:
            baseclass += ' discussion'
    else:
        time = change.creation_stamp.timestamp.strftime('%Y-%m-%d')
        # TODO link to person?
        person = change.creation_stamp.person.full_name()
        data_type = change['key']
        if change['deleted']:
            action = 'Deleted'
            summary = 'Deleted'
        else:
            action = 'Updated'
            summary = change['value']
        body = ''

    return whh.HTML.tr(
            whh.HTML.td(time, class_='date'),
            whh.HTML.td(data_type, class_='data_type'),
            whh.HTML.td(action, class_='action'),
            whh.HTML.td(summary, class_='summary'),
            class_=baseclass + " meta"
        ) + whh.HTML.tr(
            whh.HTML.td(person, class_='person'),
            whh.HTML.td(whh.HTML.pre(body), colspan=3, class_='body'),
            class_=baseclass + " body"
        )


def link_person_institutions(pis):
    strings = []
    for pi in pis:
        try:
            p = pi['person']
        except KeyError:
            continue
        try:
            i = pi['institution']
        except KeyError:
            i = None
        name = whh.tags.link_to(p.full_name(), '/person/%s' % p.id)
        inst = None
        if i:
            inst = whh.tags.link_to(i.get('name'), '/institution/%s' % i.id)
            inst = '(%s)' % inst
        strings.append(' '.join(filter(None, (name, inst))))
    return whh.HTML.literal(', '.join(strings))


def link_collections(cs):
    links = [whh.tags.link_to(c.name, '/collection/%s' % c.id) for c in cs]
    return whh.HTML.literal(', '.join(links))


def link_ship(s):
    return whh.HTML.literal(whh.tags.link_to(s.name, '/ship/%s' % s.id))


def link_country(c):
    return whh.HTML.literal(whh.tags.link_to(c.name, '/country/%s' %
                                             c.name))


def change_pretty(change):
    person = change.creation_stamp.person
    if change['deleted']:
        status = 'deleted'
    else:
        status = 'changed'
    if not change.is_accepted():
        if change.is_acknowledged():
            if change['deleted']:
                status = 'wants to delete'
            else:
                status = 'wants to change'
        elif change.is_rejected():
            if change['deleted']:
                status = 'could not delete'
            else:
                status = 'could not change'
        else:
            if change['deleted']:
                status = 'suggested deleting'
            else:
                status = 'suggested changing'
    status = ' %s ' % status
    span = whh.HTML.span
    return whh.HTML.p(
        span(person.full_name(), class_='person'), status,
        span(change['key'], class_='key'), ' to ',
        span(change['value'], class_='value'), ' at ',
        span(change['creation_stamp']['timestamp'], class_='date'),
        class_='change')


def data_uri(data):
    """ Given an _Attr with a file, provides a link to a file. """
    if not data or not data.file_:
        if not data:
            raise ValueError('Cannot link to nothing')
        else:
            logging.error('Cannot link to a non file _Attr #%s' % data.id)
        return '/404.html'

    return '/data/b/{id}'.format(id=data['_id'])


def short_data_type(type):
    if type.startswith('ctd'):
        return 'CTD'
    if type.startswith('bot'):
        return 'BOT'
    if type.startswith('sum'):
        return 'SUM'
    if type.startswith('large_volume_samples'):
        return 'Large Volume'
    if type.startswith('trace_metals'):
        return 'Trace Metal'
    if type.startswith('doc'):
        if 'pdf' in type:
            return 'PDF'
        elif 'txt' in type or 'text' in type:
            return 'TXT'
    return ''


def sort_data_files(d):
    """ Sort a list of tuples of (data file type, file) by the order CCHDO
        would like them to be in

        Order of preference: CTD, BOT, SUM, Large Volume, Trace Metal, TXT, PDF
    
    """
    preferred = [None] * 7

    for type, df in d.items():
        short_type = short_data_type(type)
        i = -1
        if short_type == 'CTD':
            i = 0
        elif short_type == 'BOT':
            i = 1
        elif short_type == 'SUM':
            i = 2
        elif short_type == 'Large Volume':
            i = 3
        elif short_type == 'Trace Metal':
            i = 4
        elif short_type == 'TXT':
            i = 5
        elif short_type == 'PDF':
            i = 6
        preferred[i] = (type, df)
    return filter(None, preferred)


def data_file_link(type, data):
    """ Given an _Attr with a file, provides a link to a file next to its
        description as a table row

        type - a short form of the file format e.g. ctdzip_exchange,
               bottlezip_netcdf
        data - the _Attr with file
    """
    try:
        link = data_uri(data)
    except KeyError:
        return ''

    data_type = short_data_type(type)

    description = models.data_file_descriptions.get(type, '')


    preliminary = False
    if data.obj:
        status = data.obj.get(type + '_status', [])
        if status:
            preliminary = 'preliminary' in status
    else:
        logging.error('%r has no obj' % data)

    classes = [type.replace('_', ' ')]
    if preliminary:
        classes.append('preliminary')
    classname = ' '.join(classes)

    return whh.HTML.tr(
        whh.HTML.th(whh.tags.link_to(data_type, link)) + \
                    whh.HTML.td(description), class_=classname)
