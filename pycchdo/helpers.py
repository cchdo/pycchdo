import webhelpers.html as whh
import webhelpers.html.tags

def title(**kwargs):
    try:
        return ' | ' + kwargs['caller']()
    except KeyError:
        return ''


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
