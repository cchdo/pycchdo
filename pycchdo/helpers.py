import datetime as dt
from urllib import quote
from json import dumps
import logging
import os.path
import os
from os.path import sep as pthsep
from os.path import join as pthjoin

import webhelpers.html as whh
H = whh.HTML
import webhelpers.html.tags as tags
import webhelpers.html.tools as whhtools
import webhelpers.text as whtext

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
    return tags.javascript_link(uri)


def has_edit(request):
    if not request:
        return False
    try:
        return request.user is not None
    except AttributeError:
        return False


def has_mod(request):
    """ Determines if the request's user has moderator powers """
    if has_edit(request):
        if has_staff(request):
            return True
        if 'moderator' in request.user.permissions:
            return True
    return False


def has_staff(request):
    """ Determines whether the request's user has staff powers.
        This is even more powerful than moderator.

    """
    if has_edit(request):
        if 'staff' in request.user.permissions:
            return True
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
        errors = [H.span(x, class_='form-error') for x in \
                  request.session.pop_flash(error_key)]
        return whh.literal(''.join(errors))
    return ''


form_errors = form_errors_for


PAGER_FORMAT = '$link_first $link_previous ~5~ $link_next $link_last'


def pager_for(page, format=PAGER_FORMAT):
    if not page.next_page and not page.previous_page:
        return ''

    next_url = whh.literal(page._url_generator(page.next_page))
    return H.div(
        page.pager(format),
        H.a(rel='next', href=next_url, style='display: none;'),
        class_='pager autopagerize_insert_before')


def email_link(email, microformat_type=None, microformat_classes=[],
               content=None):
    """ Gives back a mailto link that is slightly obfuscated. """
    obfuscator = '@spam.net'
    parts = email.split('@')
    type = ''
    if microformat_type:
        type = H.span(microformat_type, class_='type hidden')
    if not content:
        content = ''.join(
            [type, parts[0], H.span(obfuscator, class_='copythis'),
             '@', parts[1]])
    classes = [('email', True)] + [(x, True) for x in microformat_classes]
    return whhtools.mail_to(email, whh.literal(content), encode='hex',
                            class_=tags.css_classes(classes))


def boxed(title='', **attrs):
    classes = [('boxed', True)]
    box_content_classes = [('box_content', True)]
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
    except KeyError:
        pass
    caller = lambda: ''
    try:
        caller = attrs['caller']
        del attrs['caller']
    except KeyError:
        pass
    return H.div(H(
                H.h1(whh.literal(title)),
                H.div(caller(), class_=tags.css_classes(box_content_classes)),
                H.div('', class_='box_bottom'),
            ), class_=tags.css_classes(classes), _nl=True, **attrs)


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


def cruise_date_summary(cruise):
    """ Provide an English summary of the cruise's dates

    """
    text = ''
    if cruise.date_start:
        text += 'starting %s ' % date(cruise.date_start)
        if cruise.date_end:
            text += 'and ending %s' % date(cruise.date_end)
    elif cruise.date_end:
        text += 'ending %s' % date(cruise.date_end)
    return text


def cruise_nice_name(cruise):
    """ Runs through the cruise's attributes to try to produce a nice name
        before falling back to the id

    """
    label = cruise.expocode
    if not label:
        aliases = cruise.aliases
        if aliases:
            label = aliases[0]
        else:
            label = str(cruise.id)
    return label


def cruise_summary(cruise):
    """ Provide an English summary of the cruise's salient facts.

    """
    sentences = []
    sentence = '%s is planned ' % link_cruise(cruise)
    if cruise.ship:
        sentence += "on the %s " % link_ship(cruise.ship)
    if cruise.ports:
        sentence += "from %s " % cruise.ports[0]
        if len(cruise.ports) > 1:
            sentence += "to %s " % cruise.ports[1]
    sentence += cruise_date_summary(cruise)
    sentences.append(sentence.rstrip())

    sentence = 'It is being run '
    institutions = []
    if cruise.institutions:
        institutions = [link_institution(i) for i in cruise.institutions]
    if institutions or cruise.country:
        sentence += 'by '
    if institutions:
        sentence += whh.literal(whtext.series(institutions)) + ' '
        if cruise.country:
            sentence += 'and '
    if cruise.country:
        sentence += link_country(cruise.country)

    collections = [link_collection(c) for c in cruise.collections]
    if collections:
        sentence += ' as part of the '
        sentence += whh.literal(whtext.series(collections)) + ' '
        sentence += whtext.plural(
                        len(collections), 'collection', 'collections', False)
    if institutions or cruise.country or collections:
        sentences.append(sentence)

    if cruise.statuses:
        sentences.append(
            "The cruise is %s" % whtext.series(cruise.statuses))

    return whh.literal(' '.join(["%s." % x for x in sentences]))


def cruise_map_thumb(thumb=None, full=None, show_full_link=True):
    thumb_link = ''
    thumb_img = tags.image(data_uri(thumb), 'Cruise Map thumbnail')
    if full:
        full_uri = data_uri(full)
        if thumb:
            thumb_link = H.p(
                tags.link_to(thumb_img, full_uri))
        thumb_link += H.p(tags.link_to('Full Map', full_uri),
                                 class_='caption')
    else:
        if thumb:
            thumb_link = H.p(thumb_img)
    return H.div(thumb_link, class_='thumb')


def cruise_suggested_attr(attr):
    person = link_person(attr.creation_stamp.person)
    if attr.deleted:
        verb = 'deleting'
        obj_phrase = [H.span(attr.key, class_='key')]
    else:
        verb = 'changing'
        obj_phrase = [H.span(attr.key, class_='key'), ' to ',
                      H.span(attr.value, class_='value')]
    when = attr.creation_stamp.timestamp
    if attr.pending_stamp:
        followup = \
           '(Under review as of %s)' % (attr.pending_stamp.timestamp)
    else:
        followup = ''

    return H.div(
        person, ' suggested ', 
        H.span(verb, class_='verb'), ' the ', 
        H.span(*obj_phrase, class_='change'), ' at ',
        H.span(when, class_='when'), '. ',
        H.span(followup, class_='pending'), class_='suggestion')


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

    return H.tr(
            H.td(time, class_='date'),
            H.td(data_type, class_='data_type'),
            H.td(action, class_='action'),
            H.td(summary, class_='summary'),
            class_=baseclass + " meta"
        ) + H.tr(
            H.td(person, class_='person'),
            H.td(H.pre(body), colspan=3, class_='body'),
            class_=baseclass + " body"
        )


def cruises_sort_by_date_start(cruises):
    zero = dt.datetime(1, 1, 1)
    return sorted(cruises, key=lambda c: c.date_start or zero)


def cruise_listing(cruises, pre_expand=False, allow_empty=False):
    cruises = filter(None, cruises)
    if not cruises and not allow_empty:
        return ''
    list = [
        H.tr(
            H.th('Identifier', class_='identifier'),
            H.th('Ship', class_='ship'),
            H.th('Country', class_='country'),
            H.th('Cruise dates', class_='cruise_dates'),
            H.th('Chief scientist(s)', class_='chief_scientists'),
            class_='header'),
    ]
    for i, cruise in enumerate(cruises):
        hl = 'odd'
        if i % 2 == 0:
            hl = 'even'

        map = '/static/img/etopo_static/etopo_thumb_no_track.png'
        if cruise.get('map_thumb'):
            map = '/cruise/{id}/map_thumb'.format(id=cruise.uid)

        baseclass = 'mb-link{i} {hl}'.format(i=i, hl=hl)
        metaclass = 'meta ' + baseclass
        bodyclass = 'body ' + baseclass

        aliases = '(%s)' % ', '.join(cruise.aliases)
        if aliases == '()':
            aliases = ''

        list.append(
            H.tr(
                H.td(link_cruise(cruise)), 
                H.td(link_ship(cruise.ship)),
                H.td(link_country(cruise.country)),
                H.td(cruise_dates(cruise)[2]),
                H.td(link_person_institutions(cruise.chief_scientists)),
                class_=metaclass
            ),
        )
        list.append(
            H.tr(
                H.td(aliases, colspan=5), 
                class_=bodyclass
            ),
        )
        list.append(
            H.tr(
                H.td(link_collections(cruise.collections), colspan=4), 
                H.td(
                    tags.image(
                        map,
                        cruise_nice_name(cruise) + ' thumbnail',
                        class_='cruise-track-img',
                    )
                ), 
                class_=bodyclass
            ),
        )
        # TODO
        # number of stations
        # parameters (and count)
        #list.append(
        #    H.tr(
        #        H.td('', colspan=5), 
        #        class_=bodyclass
        #    ),
        #)

    table_class = 'has-meta-bodies cruise-listing'
    if pre_expand:
        table_class += ' pre-expand'
    return H.table(*list, class_=table_class)


def collection_names(coll_list):
    return filter(None, [c.name for c in coll_list])


def path_cruise(c):
    if not c:
        return ''
    return u'/cruise/%s' % c.uid


def link_obj(obj):
    if not obj:
        return ''
    return tags.link_to(obj.id, u'/obj/%s' % obj.id)


def link_obj_polymorph(obj):
    if obj.obj_type == 'Person':
        return link_person(obj)
    elif obj.obj_type == 'Collection':
        return link_collection(obj)
    elif obj.obj_type == 'Country':
        return link_country(obj)
    elif obj.obj_type == 'Cruise':
        return link_cruise(obj)
    elif obj.obj_type == 'Ship':
        return link_ship(obj)
    elif obj.obj_type == 'Institution':
        return link_institution(obj)
    else:
        return obj


def link_file_holder(fh, full=False):
    if not fh:
        return ''
    name = fh.file.name
    if not full:
        name = os.path.basename(name)
    return tags.link_to(name, data_uri(fh))


def link_cruise(c):
    if not c:
        return ''
    label = cruise_nice_name(c)
    return tags.link_to(label, path_cruise(c), title=label)


def link_person(p):
    if not p:
        return ''
    name = p.full_name().strip()
    if not name or len(name) < 1:
        name = p.id
    return tags.link_to(name, u'/person/%s' % p.id)


def link_institution(i):
    if not i:
        return ''
    return tags.link_to(i.get('name') or i.id, '/institution/%s' % i.id)


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
    return tags.link_to(c.name or '', '/collection/%s' % c.id)


def link_collections(cs):
    if not cs:
        return ''
    links = map(link_collection, cs)
    return whh.literal(', '.join(links))


def link_ship(s):
    if not s:
        return ''
    return whh.literal(tags.link_to(s.name, '/ship/%s' % s.id))


def link_country(c):
    if not c:
        return ''
    return whh.literal(tags.link_to(c.name,
                                        '/country/%s' % c.id))


def link_parameter(p):
    if not p:
        return ''
    return whh.literal(
        tags.link_to(p.get('name'),
                         '/parameter/%s.json' % p.get('name')))


def link_pdf_preview(link):
    """ Gives a URL that uses Google Docs to preview a PDF """
    # TODO add preview link for pdf docs?
    # Another option that gview takes is "embedded=true"
    return "http://docs.google.com/gview?url={link}".format(link=link)


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
    span = H.span
    return H.p(
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
        H.th(tags.link_to(data_type, link)),
        H.td(description),
    ]

    classes = [type.replace('_', ' ')]
    if preliminary:
        classes.append('preliminary')
        if has_mod(request):
            items.append(
                H.td(
                    tags.form(
                        '', 'PUT', hidden_fields={
                            'cruise_id': data.obj.id,
                            'action': 'edit_attr',
                            'key': type + '_status'}),
                    H.input(type='submit', name='edit_action',
                                   value='Mark reviewed'),
                    tags.end_form()))
    classname = ' '.join(classes)

    return H.tr(*items, class_=classname)


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

