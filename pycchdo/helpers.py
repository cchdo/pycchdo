import datetime as dt
from urllib import quote
from json import dumps
import logging
import os.path
import os
from os.path import sep as pthsep
from os.path import join as pthjoin

import webhelpers.html as whh
import webhelpers.html.tags

from gridfs.grid_file import GridOut

import models


GAPI_keys = {
    'cchdo.ucsd.edu':
        'ABQIAAAAZICfw-7ifUWoyrSbSFaNixTec8MiBufSHvQnWG6NDHYU8J6t-xTRqsJkl7OBlM2_ox3MeNhe_0-jXA',
    'whpo.ucsd.edu':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRRrtQtAbE2ICKyeJmE150l9FUtvWRQ_qb0gC6W0P4gBV_W3RstdZXEcOw',
    'watershed.ucsd.edu':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRRkZzjLi0nUJ4TwOC8xt4Ov2IJhKBQTGSNz9nt4_eT3w1Wv_O1VSaMyBA',
    'goship.ucsd.edu:3000':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRSVxuI6xAiiU0y37vRLQcURlSg9FhSh-0iK98GAcbE_yabEYgs-ehj6Xg',
    'ghdc.ucsd.edu:3000':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRQbm_T9Aut8KIkQepcdoibG6hz3ZBSwpsEu6JXesbZc0gcOonL9xKdIBA',
    'dimes.ucsd.edu:8000':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRTTLLgEU0j8TX6lr26R_f7d8ATJsxRXcK1lEshiZNwEVvZrEPwtw91gQw',
    'dimes.ucsd.edu:6543':
        'ABQIAAAATXJifusyeTqIXK5-oRfMqRST_Kiy-Bgmypbw3V1qZCFDO_zjLxT0HrIcYAGtKRot6A0EcjEGIIUqZA',
    'localhost':
        'ABQIAAAAnfs7bKE82qgb3Zc2YyS-oBT2yXp_ZAY8_ufC3CFXhHIE1NvwkxSySz_REpPq-4WZA27OwgbtyR3VcA',
}


def GAPI_key(request):
    try:
        return GAPI_keys[request.host]
    except KeyError:
        return GAPI_keys['localhost']


def GAPI_autoload(request, module_list):
    """ Gives a script tag that uses the Google jsapi URI to preload a certain
        set of modules.

    """
    jsapiload = quote(dumps({'modules': module_list})) or ''
    uri = 'http://www.google.com/jsapi?autoload={jsapiload}&key={key}'.format(
        jsapiload=jsapiload,
        key=GAPI_key(request))
    return whh.tags.javascript_link(uri)


def has_edit(request):
    if not request:
        return False
    return request.user is not None


def is_staff(user):
    if not user:
        return False
    # TODO check against actual list
    if user.name_last == 'Shen' and \
       user.name_first in ['Matthew', 'Andrew']:
        return True
    if user.name_last == 'Barna' and \
       user.name_first == 'Andrew':
        return True
    if user.name_last == 'Berys' and \
       user.name_first == 'Carolina':
        return True
    if user.name_last == 'Fields' and \
       user.name_first == 'Justin':
        return True
    if user.name_last == 'Diggs' and \
       user.name_first == 'Steve':
        return True


def has_mod(request):
    if not request:
        return False
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
        return content + ' | '
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
    if not page.next_page:
        return ''

    next_url = whh.literal(page._url_generator(page.next_page))
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
                whh.HTML.h1(whh.literal(title)),
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


def cruises_sort_by_date_start(cruises):
    zero = dt.datetime(1, 1, 1)
    return sorted(cruises, key=lambda c: c.date_start or zero)


def cruise_listing(cruises, verbose=False):
    list = []
    for cruise in cruises:
        list.append(
            whh.HTML.tr(whh.HTML.td(link_cruise(cruise)), 
                        whh.HTML.td(link_ship(cruise.ship)),
                        whh.HTML.td(date(cruise.date_start))))
    return whh.HTML.table(*list)


def collection_names(coll_list):
    return filter(None, [c.name for c in coll_list])


def path_cruise(c):
    if not c:
        return ''
    return u'/cruise/%s' % c.identifier


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
    label = c.expocode
    if not label:
        aliases = c.aliases
        if aliases:
            label = aliases[0]
        else:
            label = c.id
    return whh.tags.link_to(label, path_cruise(c), title=label)


def link_person(p):
    if not p:
        return ''
    return whh.tags.link_to(p.full_name() or p.id, u'/person/%s' % p.id)


def link_institution(i):
    if not i:
        return ''
    return whh.tags.link_to(i.get('name') or i.id, '/institution/%s' % i.id)


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
    return whh.literal(', '.join(strings))


def link_collection(c):
    if not c:
        return ''
    return whh.tags.link_to(c.name, '/collection/%s' % c.id)


def link_collections(cs):
    if not cs:
        return ''
    links = map(link_collection, cs)
    return whh.literal(', '.join(links))


def link_ship(s):
    if not s:
        return ''
    return whh.literal(whh.tags.link_to(s.name, '/ship/%s' % s.id))


def link_country(c):
    if not c:
        return ''
    return whh.literal(whh.tags.link_to(c.name,
                                        '/country/%s' % c.name))


def link_parameter(p):
    if not p:
        return ''
    return whh.literal(
        whh.tags.link_to(p.get('name'),
                         '/parameter/%s.json' % p.get('name')))


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


def data_file_link(request, type, data):
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

    items = [
        whh.HTML.th(whh.tags.link_to(data_type, link)),
        whh.HTML.td(description),
    ]

    classes = [type.replace('_', ' ')]
    if preliminary:
        classes.append('preliminary')
        if has_mod(request.user):
            items.append(
                whh.HTML.td(
                    whh.tags.form(
                        '', 'PUT', hidden_fields={
                            'cruise_id': data.obj.id,
                            'action': 'edit_attr',
                            'key': type + '_status'}),
                    whh.HTML.input(type='submit', name='edit_action',
                                   value='Mark reviewed'),
                    whh.tags.end_form()))
    classname = ' '.join(classes)

    return whh.HTML.tr(*items, class_=classname)


_here = os.path.dirname(__file__)


def _basin_map_exists(path):
    file_path = os.path.join(_here, path[1:])
    return os.path.isfile(file_path)


def get_basin_map(basin, collection, cruises=[]):
    cruise = None
    if len(cruises) > 0:
        cruise = cruises[0]

    basin = basin.lower()
    base_path = os.path.join(os.path.sep, 'static', 'img', 'maps', 'basin',
                             basin)
    basin_img_fmt = '%s_%%s.gif' % basin

    if basin == 'arctic':
        try:
            path = os.path.join(base_path,
                                basin_img_fmt % collection.name.upper())
            if _basin_map_exists(path):
                return path
        except AttributeError:
            pass
        try:
            path = os.path.join(base_path, basin_img_fmt % cruise.expocode)
            if _basin_map_exists(path):
                return path
        except AttributeError:
            pass
    elif basin == 'southern':
        try:
            path = os.path.join(base_path,
                                basin_img_fmt % collection.name.upper())
            if _basin_map_exists(path):
                return path
        except AttributeError:
            pass
        try:
            path = os.path.join(base_path, basin_img_fmt % cruise.expocode)
            if _basin_map_exists(path):
                return path
        except AttributeError:
            pass
    elif basin == 'indian':
        try:
            path = os.path.join(
                base_path, basin_img_fmt % collection.name.replace('/', '_'))
            if _basin_map_exists(path):
                return path
        except AttributeError:
            pass
    return os.path.join(base_path, '%s_base.gif' % basin)


def image_map_id(basin):
    if basin == 'Arctic':
        return '#m_arctic'
    elif basin == 'Indian':
        return '#m_indian'
    elif basin == 'Southern':
        return '#m_southern'


def area_attrs_no():
    return whh.literal('id="base" href="javascript:void(0);"')


def area_attrs_cruise(cruise, title=None, reverse=False, img=None):
    if not title:
        title = cruise
    id = cruise
    if reverse:
        # use title as image id instead of id
        id = title
    if img:
        id = img
    return whh.literal(('id="{id}" href="/cruise/{cruise}" title="{title}" '
                        'alt="{title}"').format(id=id, cruise=cruise,
                                                title=title))


def area_attrs_search(q, title=None, img=None):
    if not title:
        title = q
    id = q
    if img:
        id = img
    return whh.literal(('id="{id}" href="/search?query={q}" title="{title}" '
                        'alt="{title}"').format(id=id, q=q, title=title))

