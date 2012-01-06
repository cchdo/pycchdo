import logging
import os.path

import webhelpers.html as whh
import webhelpers.html.tags

from gridfs.grid_file import GridOut

import models


def has_edit(request):
    return request.user is not None


def is_staff(user):
    if not user:
        return False
    # TODO check against actual list
    if user.name_last == 'Shen' and \
       user.name_first in ['Matthew', 'Andrew']:
        return True
    if user.name_last == 'Berys' and \
       user.name_first == 'Carolina':
        return True
    if user.name_last == 'Fields' and \
       user.naem_first == 'Justin':
        return True
    if user.name_last == 'Diggs' and \
       user.naem_first == 'Steve':
        return True


def has_mod(request):
    if not request.user:
        return False
    if is_staff(request.user):
        return True
    # TODO other possibilities of being mod?
    return False


def get_visible_notes(request, attr):
    if not request.user:
        return attr.notes_public
    return attr.notes


def title(**kwargs):
    try:
        content = kwargs['caller']()
    except KeyError:
        content = None
    if content:
        return ' | ' + content
    return ''


def form_entered(request, key, value=None):
    entered_key = 'form_entered_' + key

    if value is not None:
        request.session.flash(value, entered_key)
        return

    if request.session.peek_flash(entered_key):
        return request.session.pop_flash(entered_key)[0]
    return ''


def form_errors_for(request, key, value=None):
    error_key = 'form_error_' + key

    if value is not None:
        request.session.flash(value, error_key)
        return

    if request.session.peek_flash(error_key):
        errors = [whh.HTML.span(x, class_='form-error') for x in \
                  request.session.pop_flash(error_key)]
        return whh.literal(''.join(errors))
    return ''


form_errors = form_errors_for


PAGER_FORMAT = '$link_first $link_previous ~5~ $link_next $link_last'


def pager_for(page, format=PAGER_FORMAT):
    next_url = whh.HTML.literal(page._url_generator(page.next_page))
    return whh.HTML.div(
        page.pager(format),
        whh.HTML.a(rel='next', href=next_url, style='display: none;'),
        class_='pager autopagerize_insert_before')


def email_link(email, microformat_type=None, microformat_classes=[],
               content=None):
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


# Pretty printers


def date(d, format='%F'):
    if not d:
        return ''
    try:
        return d.strftime(format)
    except AttributeError:
        return str(d)


def datetime(dt, format='%F %T'):
    if not dt:
        return ''
    try:
        return dt.strftime(format)
    except AttributeError:
        return str(dt)


def attr_value(a):
    v = a.value
    if type(v) is GridOut:
        return 'file(%s)' % v.name
    return a.value


def cruise_dates(cruise):
    try:
        start = date(cruise.date_start)
    except AttributeError:
        start = None
    try:
        end = date(cruise.date_end)
    except AttributeError:
        end = None
    combined = '/'.join(map(str, filter(None, (start, end))))
    return (start, end, combined)


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


def cruise_suggested_attr(attr):
    person = link_person(attr.creation_stamp.person)
    if attr.deleted:
        verb = 'deleting'
        obj_phrase = [whh.HTML.span(attr.key, class_='key')]
    else:
        verb = 'changing'
        obj_phrase = [whh.HTML.span(attr.key, class_='key'), ' to ',
                      whh.HTML.span(attr.value, class_='value')]
    when = attr.creation_stamp.timestamp
    if attr.pending_stamp:
        followup = \
           '(Under review as of %s)' % (attr.pending_stamp.timestamp)
    else:
        followup = ''

    return whh.HTML.div(
        person, ' suggested ', 
        whh.HTML.span(verb, class_='verb'), ' the ', 
        whh.HTML.span(*obj_phrase, class_='change'), ' at ',
        whh.HTML.span(when, class_='when'), '. ',
        whh.HTML.span(followup, class_='pending'), class_='suggestion')


def cruise_history_rows(change, i, hl):
    """ Give the HTML table rows for a cruise history entry.
        
        i - The entry number
        hl - even or odd class name
    """

    baseclass = "mb-link{i} {hl}".format(i=i, hl=hl)

    if type(change) == models.Note:
        time = date(change.creation_stamp.timestamp, '%Y-%m-%d')
        person = link_person(change.creation_stamp.person)
        data_type = change['data_type']
        action = change['action']
        summary = change['subject']
        body = change['body']
        if change.discussion:
            baseclass += ' discussion'
    else:
        time = date(change.creation_stamp.timestamp, '%Y-%m-%d')
        person = link_person(change.creation_stamp.person)
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


def cruise_listing(cruises, verbose=False):
    list = []
    for cruise in cruises:
        list.append(
            whh.HTML.tr(whh.HTML.td(link_cruise(cruise)), 
                        whh.HTML.td(link_ship(cruise.ship)),
                        whh.HTML.td(date(cruise.date_start))))
    return whh.HTML.table(*list)


def link_obj(obj):
    if not obj:
        return ''
    return whh.tags.link_to(obj.id, u'/obj/%s' % obj.id)


def link_file_holder(fh, full=False):
    if not fh:
        return ''
    name = fh.file.name
    if not full:
        name = os.path.basename(name)
    return whh.tags.link_to(name, data_uri(fh))


def link_cruise(c):
    if not c:
        return ''
    if not c.expocode:
        return whh.tags.link_to(c.id, u'/cruise/%s' % c.id)
    return whh.tags.link_to(c.expocode, u'/cruise/%s' % c.expocode)


def link_person(p):
    if not p:
        return ''
    return whh.tags.link_to(p.full_name(), u'/person/%s' % p.id)


def link_institution(i):
    if not i:
        return ''
    return whh.tags.link_to(i.get('name'), '/institution/%s' % i.id)


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
        name = link_person(p)
        inst = None
        if i:
            inst = '(%s)' % link_institution(i)
        strings.append(' '.join(filter(None, (name, inst))))
    return whh.HTML.literal(', '.join(strings))


def link_collection(c):
    if not c:
        return ''
    return whh.tags.link_to(c.name, '/collection/%s' % c.id)


def link_collections(cs):
    if not cs:
        return ''
    links = map(link_collection, cs)
    return whh.HTML.literal(', '.join(links))


def link_ship(s):
    if not s:
        return ''
    return whh.HTML.literal(whh.tags.link_to(s.name, '/ship/%s' % s.id))


def link_country(c):
    if not c:
        return ''
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
            logging.error('Cannot link to nothing')
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
