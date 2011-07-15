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
    status = 'changed'
    if not change.is_accepted():
        if change.is_acknowledged():
            status = 'has a pending suggestion for'
        elif change.is_rejected():
            status = 'could not change'
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
