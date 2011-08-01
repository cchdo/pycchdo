import os

from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


__all__ = ['_collapsed_dict', '_http_method', '_unescape'] + \
          ['home', 'clear_db', 'submit', 'data', 'catchall_static']


def _collapsed_dict(d, n=None):
    """ Collapses a dict recursively into the value n if it has no values that
    are not n """
    e = {}
    for k, v in d.items():
        if type(v) is dict:
            v = _collapsed_dict(v, n)
        if v is not n:
            e[k] = v
    if len(e) < 1:
        return n
    return e


def _http_method(request):
    try:
        return request.params['_method']
    except KeyError:
        return request.method


def _unescape(s, escape='\\'):
    n = s.find(escape)
    while n > -1:
        s = s[:n] + s[n + 1:]
        n = s.find(escape, n + 1)
    return s


def home(request):
    return {}


def clear_db(request):
    # XXX REMOVE
    cchdo = models.cchdo()
    for obj in cchdo.objs.find():
        if obj['_obj_type'] != 'Person':
            cchdo.objs.remove(obj)
    cchdo.attrs.drop()
    return Response('OK')


def submit(request):
    return {}


def data(request):
    """ Returns data """
    id = request.matchdict['data_id']
    try:
        data = models.Attr.get_id(id)
    except ValueError:
        return HTTPNotFound()

    file = data.file

    resp = Response()
    resp.app_iter = file
    resp.content_length = file.length
    resp.content_type = file.content_type
    resp.content_disposition = 'inline; filename="{name}"'.format(name=file.name)
    return resp


def catchall_static(request):
    """ Wraps any static templates with the layout """
    subpath = os.path.join(*request.matchdict['subpath'])

    project_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    static_path = os.path.join('templates', 'static')

    path = os.path.join(project_path, static_path, subpath)
    relpath = os.path.join(static_path, subpath)

    if os.path.isfile(path):
        return {'_static': relpath}
    return HTTPNotFound()
