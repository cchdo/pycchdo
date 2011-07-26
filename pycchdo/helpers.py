import webhelpers.html as whh
import webhelpers.html.tags

import models

def title(**kwargs):
    try:
        content = kwargs['caller']()
    except KeyError:
        content = None
    if content:
        return ' | ' + content
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
    try:
        classes.extend([(x, True) for x in attrs['class'].split()])
        del attrs['class']
    except KeyError:
        pass
    caller = lambda: ''
    try:
        caller = attrs['caller']
        del attrs['caller']
    except KeyError:
        pass
    return whh.HTML.div(whh.HTML(
                whh.HTML.h1(title),
                whh.HTML.div(caller(), class_='box_content'),
                whh.HTML.div(bottom, class_='box_bottom')
            ), class_=whh.tags.css_classes(classes), _nl=True, **attrs)


def change_pretty(change):
    person = models.Person.get_id(change['creation_stamp']['person'])
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
        span(change['creation_stamp']['timestamp'], class_='date'), ' ',
        whh.tags.link_to('Details', ''), class_='change')

def data_uri(data):
    """ Given a Attr with a file, provides a link to a file. """
    if not data.is_data():
        raise ValueError('Cannot link to a non file')

    return '/data/{id}'.format(id=data['_id'])


def data_file_link(type, data):
    """ Given a Attr with a file, provides a link to a file next to its
        description as a table row

        type - a short form of the file format e.g. ctdzip_exchange,
               bottlezip_netcdf
        data - the Attr with file
    """
    try:
        link = data_uri(data)
    except KeyError:
        return ''

    data_type = ''
    if 'ctd' in type:
        data_type = 'CTD'
    elif 'bot' in type:
        data_type = 'BOT'
    elif 'sum' in type:
        data_type = 'SUM'
    elif 'doc' in type:
        if 'pdf' in type:
            data_type = 'PDF'
        elif 'txt' in type or 'text' in type:
            data_type = 'TXT'

    description = models.data_file_descriptions.get(type, '')
    return whh.HTML.tr(
        whh.HTML.th(whh.tags.link_to(data_type, link)) + \
                    whh.HTML.td(description), class_=type.replace('_', ' '))
