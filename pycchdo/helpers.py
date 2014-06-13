from datetime import datetime, date
from urllib import quote
from json import dumps
from copy import copy
from collections import OrderedDict
import os.path
import os
import re
from os.path import (
    sep as pthsep, join as pthjoin,
    )

import transaction

import webhelpers.html as whh
H = whh.HTML
from webhelpers.html import tags, tools as whhtools
from webhelpers import text as whtext

from pyramid.url import route_path

from pycchdo.log import getLogger, INFO, DEBUG
from pycchdo.models.serial import (
    Note, FSFile
    )
from pycchdo.models.file_types import DataFileTypes
from pycchdo.models.serial import (
    Person, Country, Cruise, Collection, Ship, Institution,
    )
from pycchdo.util import collapse_dict
from pycchdo.views.datacart import get_datacart, ZIP_FILE_LIMIT
from pycchdo.models.searchsort import Sorter


log = getLogger(__name__)
log.setLevel(DEBUG)


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


def has_argo(request):
    """Determines if the request's user has Argo SFR priviledges."""
    if 'argo' in request.user.permissions:
        return True
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


_re_expocode_usa_ship = re.compile('^3[1-3]')
def is_expocode_usa_ship(expocode):
    return _re_expocode_usa_ship.match(expocode)


def is_usa_ship(ship):
    ship_code = ship.nodc_platform_code
    if ship_code:
        return _re_expocode_usa_ship.match(ship_code)
    return False


def needs_specifics_reduction(cruise, date):
    """Determine whether a cruise needs its date and port specifics reduced to
    comply with UNOLS and Navy security regulations.

    """
    if not cruise:
        return False

    if (    (   (cruise.expocode and is_expocode_usa_ship(cruise.expocode) or
                (cruise.ship and is_usa_ship(cruise.ship)))
            ) and 
            (date and (
                (cruise.date_start and 
                 type(cruise.date_start) == datetime and
                 cruise.date_start > date) or
                (cruise.date_end and type(cruise.date_end) == datetime and
                 cruise.date_end > date)))):
        return True
    return False


def reduce_specificity(request, *cruises):
    """Comply with federal security regulations and remove specifics.

    regarding USA ships in the future
    specifics include ports of call and departure/arrival dates
    It is allowed to specify year and season, however.

    """
    if not cruises:
        return

    # Password protected does not require reduction.
    if has_edit(request):
        return

    now = datetime.now()
    for cruise in cruises:
        if needs_specifics_reduction(cruise, now):
            log.info(
                u'Reducing specifics for cruise {0}'.format(cruise))
            attr = cruise.get_attr('date_start')
            if attr:
                av = attr.attr_value
                av.value = datetime(av.value.year, 1, 1)
                transaction.doom()
            attr = cruise.get_attr('date_end')
            if attr:
                av = attr.attr_value
                av.value = datetime(av.value.year, 1, 1)
                transaction.doom()


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
               content=None, extra=None):
    """Gives back a mailto link that is slightly obfuscated."""
    obfuscator = '@spam.net'
    parts = email.split('@')
    type = ''
    if microformat_type:
        type = H.span(microformat_type, class_='type hidden')

    if extra:
        extra = '+' + extra
    else:
        extra = ''

    email = ''.join([parts[0], extra, '@', parts[1]])

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


def lazyload_image(request, src, lazyload=True, **kwargs):
    """Produce HTML to enable this plugin.

    http://www.appelsiini.net/projects/lazyload

    """
    if lazyload:
        lazy_kwargs = copy(kwargs)
        lazy_kwargs['data-original'] = src
        lazy_kwargs['src'] = request.route_path('transparent')
        return H.img(**lazy_kwargs) + H.noscript(H.img(src=src, **kwargs))
    return H.img(src=src, **kwargs)


# Pretty printers


def pdate(d, format='%F'):
    if not d:
        return ''
    try:
        return d.strftime(format)
    except AttributeError:
        return str(d)


def pdatetime(dt, format='%F %T'):
    if not dt:
        return ''
    try:
        return dt.strftime(format)
    except AttributeError:
        return str(dt)


def attr_value(a):
    v = a.value
    try:
        v.read
        return 'file(%s)' % v.name
    except AttributeError:
        try:
            return str(v)
        except TypeError:
            return repr(v)


def is_reduced(d):
    try:
        return (
            d.year >= date.today().year and d.month == 1 and d.day == 1)
    except AttributeError:
        return False


def date_to_nice(d):
    """Convert datetime or string to a nice date.

    seahunt cruises may have a string date. Comply with security restrictions 
    by cutting short dates in the future of USA ships. If a string date has
    extra precision, we have no way of knowing and can't comply yet.

    """
    try:
        if is_reduced(d):
            d = d.year
        d = pdate(d)
    except TypeError, e:
        pass
    return d


def ports_to_nice(ports, cruise=None):
    """Convert list of ports to a nice string.

    In order to comply with security restrictions, ports of call for a USA ship
    cannot be shown. Since there is currently no simple way to get the country
    of the port of call, the ports will be omitted.

    """
    if not ports:
        return ports
    if cruise and needs_specifics_reduction(cruise, datetime.now()):
        return u''
    return u' to '.join(ports)


def cruise_dates(cruise):
    try:
        start = date_to_nice(cruise.date_start)
    except AttributeError:
        start = None
    try:
        end = date_to_nice(cruise.date_end)
    except AttributeError:
        end = None
    joiner = H.span('/', class_='datesep')
    combined = whh.literal(joiner.join(map(str, filter(None, (start, end)))))
    return (start, end, combined)


def cruise_date_summary(cruise):
    """ Provide an English summary of the cruise's dates

    """
    text = ''
    if cruise.date_start:
        text += 'starting %s ' % date_to_nice(cruise.date_start)
        if cruise.date_end:
            text += 'and ending %s' % date_to_nice(cruise.date_end)
    elif cruise.date_end:
        text += 'ending %s' % date_to_nice(cruise.date_end)
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
    """Provide an English summary of the cruise's salient facts.

    """
    sentences = []
    sentence = '%s is planned ' % link_cruise(cruise)
    if cruise.ship:
        sentence += "on the %s " % link_ship(cruise.ship)
    ports = cruise.get('ports')
    if ports:
        sentence += "from %s " % ports[0]
        if len(ports) > 1:
            sentence += "to %s " % ports[1]
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


def cruise_map_thumb(request, cruise, show_full_link=True):
    thumb_link = ''
    thumb_img = tags.image(
        request.route_path('cruise_map_thumb', cruise_id=cruise.id),
        'Cruise Map thumbnail')
    if cruise.get('map_full'):
        full_uri = request.route_path('cruise_map_full', cruise_id=cruise.id)
        if cruise.get('map_thumb'):
            thumb_link = H.p(tags.link_to(thumb_img, full_uri))
        thumb_link += H.p(
            tags.link_to('Full Map', full_uri), class_='caption')
    else:
        if cruise.get('map_thumb'):
            thumb_link = H.p(thumb_img)
    return H.div(thumb_link, class_='thumb')


def cruise_suggested_attr(attr):
    person = link_person(attr.p_c)
    if attr.deleted:
        verb = 'deleting'
        obj_phrase = [H.span(attr.key, class_='key')]
    else:
        verb = 'changing'
        obj_phrase = [H.span(attr.key, class_='key'), ' to ',
                      H.span(attr.value, class_='value')]
    when = attr.ts_c
    if attr.ts_ack:
        followup = \
           '(Under review as of %s)' % (attr.ts_ack)
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

    if type(change) == Note:
        time = pdate(change.ts_c, '%Y-%m-%d')
        person = link_person(change.p_c)
        data_type = change.data_type
        action = change.action
        summary = change.subject
        body = change.body
        if change.discussion:
            baseclass += ' discussion'
    else:
        time = pdate(change.ts_c, '%Y-%m-%d')
        person = link_person(change.p_c)
        data_type = change.attr
        if change.deleted:
            action = 'Deleted'
            summary = 'Deleted'
        else:
            action = 'Updated'
            summary = change.value
        body = ''

    note_id = 'history_{0}'.format(change.id)

    return H.tr(
            H.td(tags.link_to(time, '#' + note_id), class_='date'),
            H.td(data_type, class_='data_type'),
            H.td(action, class_='action'),
            H.td(summary, class_='summary'),
            id=note_id,
            class_=baseclass + " meta"
        ) + H.tr(
            H.td(person, class_='person'),
            H.td(H.pre(body), colspan=3, class_='body'),
            class_=baseclass + " body"
        )


def cruises_sort_by_date_start(cruises):
    zero = datetime(1, 1, 1)
    return sorted(cruises, key=lambda c: c.date_start or zero)


def cruise_track_image(map, cruise, classes=[]):
    return tags.image(map, cruise_nice_name(cruise) + ' thumbnail',
        class_=' '.join(['cruise-track-img'] + classes))


def _curr_direction(sorter, key):
    orderkeys = dict(sorter.orderkeys)
    if key in orderkeys:
        if orderkeys[key]:
            direction = 'asc'
        else:
            direction = 'desc'
    else:
        direction = None
    return direction


def _sortable_link(request, link, key):
    """Return an HTML link to a order the current page."""
    sorter = Sorter(request.params.get('orderby', ''))
    direction = _curr_direction(sorter, key)
    uarrow = '<span class="sortdir asc">&#x25B2;</span>'
    darrow = '<span class="sortdir desc">&#x25BC;</span>'
    if direction:
        if direction == 'asc':
            title = '{0} {1}'.format(link, 'descending')
            link = link + darrow
        elif direction == 'desc':
            title = '{0} {1}'.format(link, 'ascending')
            link = link + uarrow
    else:
        link = link
        title = '{0} {1}'.format(link, '(click to sort ascending)')
    return tags.link_to(
        whh.literal(link),
        _orderby_path(request, direction, key),
        title=title)


def _orderby_path(request, direction, key):
    if direction:
        orderby = '{0}:{1}'.format(key, direction)
    else:
        orderby = key
    return request.current_route_path(
        _query=dict(request.params, **{'orderby': orderby}))


def cruise_listing(request, cruises, pre_expand=False, allow_empty=False,
                   show_data=True):
    cruises = filter(None, cruises)
    if not cruises and not allow_empty:
        return ''

    headers = [
        H.th(
            _sortable_link(request, 'ExpoCode', 'uid'), ' / ', 
            _sortable_link(request, 'Cruise dates', 'date_start'),
            class_='identifier'),
        H.th(_sortable_link(request, 'Aliases', 'aliases'),
            class_='aliases'),
        H.th(
            _sortable_link(request, 'Chief scientist(s)', 'chiscis'), ' / ',
            _sortable_link(request, 'Ship', 'ship'), ' / ',
            _sortable_link(request, 'Country', 'country'),
            class_='who'),
    ]
    if show_data:
        headers.append(H.th('Dataset', class_='dataset'))
        # Extra column for the datacart cruise link
        headers.append(H.th())
    headers.append(H.th(class_='map'))

    list = [
        H.tr(*headers, class_='header'),
    ]
    for i, cruise in enumerate(cruises):
        hl = 'odd'
        if i % 2 == 0:
            hl = 'even'

        map_path = '/static/img/etopo_static/etopo_thumb_no_track.png'
        if cruise.get('map_thumb'):
            map_path = '/cruise/{id}/map_thumb'.format(id=cruise.uid)

        baseclass = 'mb-link{i} {hl}'.format(i=i, hl=hl)
        metaclass = 'meta metadata-cruise batch-open ' + baseclass
        bodyclass = 'body ' + baseclass

        aliases = ', '.join(cruise.aliases)

        cruise_page_buttons = H.div(
            tags.form(
                request.route_path('cruise_show', cruise_id=cruise.uid),
                method='get', class_='button-to'),
            H.div(tags.submit('', 'Cruise page')),
            tags.end_form(),
            tags.form(
                request.route_path(
                    'cruise_show', cruise_id=cruise.uid, _anchor='history'),
                method='get', class_='button-to'),
            H.div(tags.submit('', 'History')),
            tags.end_form(),
            class_='links body {0}'.format(baseclass))
        data_files = collect_data_files(cruise)
        row = [
            H.td(
                H.div(link_cruise(cruise), class_='expocode'),
                H.div(cruise_dates(cruise)[2], class_='cruise_dates'),
                cruise_page_buttons,
                class_='identifier'
            ),
            H.td(aliases, class_='aliases'),
            H.td(
                H.div(link_person_institutions(cruise.chief_scientists),
                    class_='chief_scientists'),
                H.div(link_ship(cruise.ship), class_='ship'),
                H.div(link_country(cruise.country), class_='country'),
                class_='who'
            ),
        ]
        if show_data:
            row.append(H.td(
                data_files_lists(request, data_files, condensed=True,
                                 classes=['body', baseclass]),
                class_='dataset'
            ))
            row.append(H.td(datacart_link_cruise(request, cruise)))
        row.append(
            H.td(
                cruise_track_image(
                    map_path, cruise, classes=['body', baseclass]),
                class_='map'
            ))
        list.append(H.tr(*row, class_=metaclass))
        # TODO number of stations, parameters (and count)
        #list.append(
        #    H.tr(
        #        H.td('{0} stations with the following parameters:',
        #            colspan=2), 
        #        class_=bodyclass
        #    ),
        #)

    table_class = 'has-meta-bodies cruise-listing'
    if pre_expand:
        table_class += ' pre-expand'
    table = H.table(*list, class_=table_class)

    if request.params.get('expanded', False):
        expanded_query = {'query': request.params.get('query')}
        expanded_button_str = 'Condense'
    else:
        expanded_query = {'query': request.params.get('query'), 'expanded': True}
        expanded_button_str = 'Expand'

    return H.div(
        H.div(
            H.div(
                tags.form(request.current_route_path(),
                    method='GET', class_='button-to', hidden_fields=expanded_query),
                tags.submit('', expanded_button_str),
                tags.end_form(),
                whtext.plural(len(cruises), 'result', 'results'),
                    class_='tool tool-count'
            ),
            datacart_link_cruises(request, cruises), 
            class_='tools'
        ),
        table,
        class_='cruise-listing'
    )


def track_as_string(track):
    return '\n'.join([', '.join(map(str, coord)) for coord in track.coords])


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
    if isinstance(obj, Person):
        return link_person(obj)
    elif isinstance(obj, Collection):
        return link_collection(obj)
    elif isinstance(obj, Country):
        return link_country(obj)
    elif isinstance(obj, Cruise):
        return link_cruise(obj)
    elif isinstance(obj, Ship):
        return link_ship(obj)
    elif isinstance(obj, Institution):
        return link_institution(obj)
    else:
        return obj


def link_file_holder(fh, full=False, original=False):
    """Return a link to the file that is the given file holder's value.

    File holder is an _Attr.
    Args:
    original - link to the original value, not the accepted value

    """
    if original:
        val = fh.value_original
    else:
        val = fh.value
    if not fh or not val:
        log.error(u'Unable to link a fileholder: {0!r}'.format(fh))
        return ''
    name = val.name
    if not full:
        name = os.path.basename(name)
    if not name:
        name = val.name
    if not name:
        name = 'unnamed_file'
    return tags.link_to(name, data_uri(fh, original), title=name)


def link_cruise(c):
    if not c:
        return ''
    label = cruise_nice_name(c)
    return tags.link_to(label, path_cruise(c), title=label)


def link_person(p):
    if not p:
        return ''
    name = p.name.strip()
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
            p = pi.person
        except KeyError:
            continue
        name = link_person(p)
        #try:
        #    i = pi.institution
        #except KeyError:
        #    i = None
        #inst = None
        #if i:
        #    inst = '(%s)' % link_institution(i)
        inst = None
        strings.append(' '.join(filter(None, (name, inst))))
    return whh.literal(', '.join(strings))


def link_collection(c):
    if not c:
        return ''
    return tags.link_to(c.name or c.id, '/collection/%s' % c.id)


def link_collections(cs):
    if not cs:
        return ''
    links = map(link_collection, cs)
    return whh.literal(', '.join(links))


def link_ship(s):
    if not s:
        return ''
    return whh.literal(tags.link_to(s.name or s.id, '/ship/%s' % s.id))


def link_country(c):
    if not c:
        return ''
    return whh.literal(tags.link_to(
        c.preferred_name or c.id, '/country/%s' % c.id))


def link_parameter(p):
    if not p:
        return ''
    return whh.literal(
        tags.link_to(p.get('name'), '/parameter/%s.json' % p.get('name')))


def link_pdf_preview(link):
    """Gives a URL that uses Google Docs to preview a PDF."""
    # TODO add preview link for pdf docs?
    # Another option that gview takes is "embedded=true"
    return "http://docs.google.com/gview?url={link}".format(link=link)


def link_submission(sub):
    """Return a link to a specific submission."""
    return tags.link_to(
        sub.id, '/staff/submissions.html?ltype=id&query={0}'.format(sub.id))


def link_q(request, attached):
    """Return a link to a queue file.
    This is really a link to the cruise page with the queue file fragment.

    """
    ident = attached.obj.uid
    return tags.link_to(attached.id,
        request.route_path(
            'cruise_show', cruise_id=ident,
            _anchor='as_received_{0}'.format(attached.id)))


def change_pretty(change):
    person = change.p_c
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
        span(person.full_name, class_='person'), status,
        span(change.key, class_='key'), ' to ',
        span(change.value, class_='value'), ' at ',
        span(change.ts_c, class_='date'),
        class_='change')


def data_uri(data, original=False):
    """ Given an _Attr with a file, provides a link to a file. """
    if not data:
        log.error('Cannot link to nothing')
    if original:
        val = data.value_original
    else:
        val = data.value
    if not val:
        log.error('Cannot link to nothing')
    if type(val) is not FSFile:
        log.error('Cannot link to non-FSFile value %s' % data.id)
        return '/404.html'
    if original:
        return '/data/b/{id}?orig=1'.format(id=data.id)
    else:
        return '/data/b/{id}'.format(id=data.id)


def short_data_type(type):
    if type.startswith('ctd'):
        return 'CTD'
    if type.startswith('bot'):
        return 'Bottle'
    if type.startswith('sum'):
        return 'Summary'
    if type.startswith('large_volume_samples'):
        return 'Large Volume'
    if type.startswith('trace_metals'):
        return 'Trace Metal'
    if type.startswith('doc'):
        if 'pdf' in type:
            return 'PDF'
        elif 'txt' in type or 'text' in type:
            return 'Text'
    return ''


def collect_data_files(cruise_obj):
    """Return ordered sections with files of a cruise's dataset."""
    if not cruise_obj:
        return {}

    mapped = cruise_obj.file_attrs

    data_files = OrderedDict()
    data_files['exchange'] = {
        'ctd_zip_exchange': mapped.get('ctd_zip_exchange'),
        'bottle_exchange': mapped.get('bottle_exchange'),
        'large_volume_samples_exchange': mapped.get(
            'large_volume_samples_exchange'),
        'trace_metals_exchange': mapped.get('trace_metals_exchange'),
    }
    data_files['netcdf'] = {
        'ctd_zip_netcdf': mapped.get('ctd_zip_netcdf'),
        'bottle_zip_netcdf': mapped.get('bottle_zip_netcdf'),
    }
    data_files['doc'] = {
        'doc_txt': mapped.get('doc_txt'),
        'doc_pdf': mapped.get('doc_pdf'),
    }
    data_files['woce'] = {
        'bottle_woce': mapped.get('bottle_woce'),
        'ctd_zip_woce': mapped.get('ctd_zip_woce'),
        'sum_woce': mapped.get('sum_woce'),
        'large_volume_samples_woce': mapped.get('large_volume_samples_woce'),
    }
    data_files['map'] = {
        'full': mapped.get('map_full'),
        'thumb': mapped.get('map_thumb'),
    }
    return collapse_dict(data_files) or {}


def sort_data_files(d):
    """ Sort a list of tuples of (data file type, file) by the order CCHDO
        would like them to be in

        Order of preference: CTD, BOT, SUM, Large Volume, Trace Metal, Text, PDF
    
    """
    preferred = [None] * 8

    for type, df in d.items():
        short_type = short_data_type(type)
        i = -1
        if short_type == 'Summary':
            i = 0
        elif short_type == 'CTD':
            i = 1
        elif short_type == 'BTL':
            i = 2
        elif short_type == 'Large Volume':
            i = 3
        elif short_type == 'Trace Metal':
            i = 4
        elif short_type == 'Text':
            i = 5
        elif short_type == 'PDF':
            i = 6
        else:
            i = 7
        preferred[i] = (type, df)
    return filter(None, preferred)


def data_files_list(request, data_files, short_name, title, condensed=False):
    """Display a table of data_files given from views.cruises.show."""
    if short_name not in data_files:
        return ''

    files_html = ''
    for dtype, dfile in sort_data_files(data_files.get(short_name)):
        if condensed:
            leader = title
        else:
            leader = None
        files_html += data_file_link(request, dtype, dfile, leader=leader)

    if condensed:
        return files_html
    return H.h3(title) + H.table(files_html, class_='formats')


def data_files_lists(request, data_files, condensed=False, classes=[]):
    """Display a cruise's dataset."""
    htmllist = whh.literal(''.join([
        data_files_list(request, data_files, 'exchange', 'Exchange', condensed),
        data_files_list(request, data_files, 'netcdf', 'NetCDF', condensed),
        data_files_list(request, data_files, 'woce', 'WOCE', condensed),
        data_files_list(request, data_files, 'doc', 'Documentation', condensed),
        ]))
    if condensed:
        htmllist = H.table(htmllist, class_='formats')
    return H.div(htmllist, class_=' '.join(['formats-sections'] + classes))


def datacart_link(act, link={}, **kwargs):
    """Individual datacart action agnostic link."""
    ref = kwargs.get('ref', '')
    if ref:
        del kwargs['ref']
    rel = 'nofollow' + ref

    return tags.link_to(
        H.div(act, class_='datacart-icon'), link, rel=rel, **kwargs)


def datacart_link_file(request, act, fileattr):
    """Datacart action link for a single file."""
    if act == 'Remove':
        action = 'remove'
        classname = 'datacart-link datacart-remove'
        title = 'Remove from data cart'
    elif act == 'Add':
        action = 'add'
        classname = 'datacart-link datacart-add'
        title = 'Add to data cart'

    return datacart_link(act,
        request.route_path('datacart_' + action, _query={'id': fileattr.id}),
        class_=classname, title=title)


def datacart_link_cruise_action(request, act, cruise):
    if act == 'Remove':
        action = 'remove_cruise'
        classname = 'datacart-link datacart-cruise datacart-remove'
        title = 'Remove all cruise data from data cart'
    elif act == 'Add':
        action = 'add_cruise'
        classname = 'datacart-link datacart-cruise datacart-add'
        title = 'Add all cruise data to data cart'

    return datacart_link("{0} all".format(act),
        request.route_path('datacart_{0}'.format(action),
                           _query={'id': cruise.id}),
        class_=classname, title=title)


def datacart_link_cruise(request, cruise):
    """Datacart action link for all the files in a cruise."""
    nfiles_in_cart, nfiles = request.datacart.cruise_files_in_cart(cruise)
    if nfiles_in_cart > 0:
        link = datacart_link_cruise_action(request, 'Remove', cruise)
    elif nfiles > 0:
        link = datacart_link_cruise_action(request, 'Add', cruise)
    else:
        link = ''
    return H.div(link, class_='datacart-cruise-links')


def datacart_link_cruises(request, cruises, div_attributes={}):
    nfiles_in_cart_all = 0
    nfiles_all = 0
    for cruise in cruises:
        nfiles_in_cart, nfiles = request.datacart.cruise_files_in_cart(cruise)
        nfiles_in_cart_all += nfiles_in_cart
        nfiles_all += nfiles

    ids = [ccc.id for ccc in cruises]
    if nfiles_in_cart_all > 0:
        link_str = 'Remove all data in result'
        link_params = request.route_path(
            'datacart_remove_cruises', _query={'ids': ids})
        link_attrs = {
            'class_': 'datacart-link datacart-results datacart-remove',
            'title': 'Remove all result data from data cart',
        }
    elif nfiles_all > 0:
        link_str = 'Add all data in result'
        link_params = request.route_path(
            'datacart_add_cruises', _query={'ids': ids})
        link_attrs = {
            'class_': 'datacart-link datacart-results datacart-add',
            'title': 'Add all result data to data cart',
        }
    else:
        link_str = ''
        link = ''
        link_params = ''
        link_attrs = {}
    div_attrs = {'class_': "datacart-cruises-links"}
    div_attrs_proper = dict(
        list(div_attributes.items()) + list(div_attrs.items()))
    if 'class_' in div_attributes:
        div_attrs_proper['class_'] = ' '.join(
            filter(None, [
                div_attrs.get('class_', None),
                div_attributes['class_']]))
    link = datacart_link(link_str, link_params, **link_attrs)
    return H.div(link, **div_attrs_proper)


def datacart_num_files_in_archive(request, index):
    return min((len(request.datacart) - index), ZIP_FILE_LIMIT)


def datacart_archive_id(index):
    return int(index / ZIP_FILE_LIMIT)


def data_file_link(request, type, data, leader=None):
    """Given an _Attr with a file, provides a link to a file next to its
    description as a table row.

    Arguments:
        type - a short form of the file format e.g. ctdzip_exchange,
               bottlezip_netcdf
        data - the _Attr with file
        leader - (optional) if given, leader will be prepended onto the short
        representation of the data type.

    """
    try:
        link = data_uri(data)
    except KeyError:
        return ''

    data_type = short_data_type(type)
    if leader:
        data_type = ' '.join([leader, data_type])

    description = DataFileTypes.descriptions.get(type, '')

    preliminary = False
    if data.obj:
        status = data.obj.get(type + '_status', [])
        if status:
            preliminary = 'preliminary' in status
    else:
        log.error('%r has no obj' % data)

    preliminary_marker = ''
    if preliminary:
        preliminary_marker = ' *'

    items = [
        H.th(H.abbr(tags.link_to(data_type + preliminary_marker, link),
                                 title=description)),
    ]

    # If datacart has item
    if data.id in get_datacart(request):
        dcart_link = datacart_link_file(request, 'Remove', data)
    else:
        dcart_link = datacart_link_file(request, 'Add', data)
    items.append(H.td(dcart_link, class_='datacart'))

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


def parameter_bounds(bounds):
    """Pretty-print a parameter's bounds."""
    if not bounds:
        return u''
    return u', '.join([u'{0:.1f}'.format(x) for x in bounds])


def pluralize_category(category):
    if category == 'person':
        return 'People'
    elif category == 'collection':
        return 'Collections'
    elif category == 'country':
        return 'Countries'
    elif category == 'cruise':
        return 'Cruises'
    elif category == 'ship':
        return 'Ships'
    elif category == 'institution':
        return 'Institutions'
    else:
        return category
