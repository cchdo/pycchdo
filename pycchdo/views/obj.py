from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPSeeOther

import pycchdo.models as models

from . import *
from session import require_signin


def objs(request):
    return {'objs': models.Obj.all()}


def obj_new(request):
    if not request.user:
        return require_signin(request)

    obj_type = request.params.get('_obj_type', models.Obj.__name__)

    try:
        obj = models.__dict__[obj_type](request.user)
        obj.save()
    except KeyError:
        raise ValueError('No such obj type (%s) allowed' % obj_type)
    return {'obj': obj}


def obj_show(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    if not obj:
        return HTTPNotFound()

    link = request.url
    if _http_method(request) == 'DELETE':
        if obj:
            obj.remove()
            obj = None
            request.session.flash('action_taken', 'Removed Obj %s' % obj_id)
            return HTTPSeeOther(location='/objs')
    else:
        if obj.type == 'Cruise':
            link = request.url.replace('/obj/', '/cruise/')
        elif obj.type == 'Obj':
            link = None

    return {
        'id': obj_id,
        'obj': obj,
        'link': link,
    }


def obj_attrs(request):
    method = _http_method(request)

    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    if not obj:
        return HTTPNotFound()

    if method  == 'GET':
        return {'obj': obj, 'type': __builtins__['type']}

    if not request.user:
        return require_signin(request)

    note = None
    note_body = request.params.get('note_body', None)
    note_action = request.params.get('note_action', None)
    note_data_type = request.params.get('note_data_type', None)
    note_subject = request.params.get('note_subject', None)
    if note_body or note_action or note_data_type or note_subject:
        note = models.Note(note_body, note_action, note_data_type, note_subject)

    key = request.params.get('key', None)
    if method == 'POST':
        value = request.params.get('value', None)
        if not key and value:
            return HTTPBadRequest('Attr key required if setting value')
        type = request.params.get('type', None)

        if type == 'text':
            pass
        elif type == 'datetime':
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        elif type == 'list':
            value = [_unescape(x) for x in value.split(',')]
        elif type == 'id':
            value = models.Obj.get_id(value)
            if value:
                value = value['_id']
        else:
            # file upload should send the FieldStorage unchanged
            # notes should not change anything either
            pass
        obj.set(key, value, request.user, note)
    elif method == 'DELETE':
        obj.delete(key, request.user, note)
    return {'obj': obj, 'type': __builtins__['type']}


def obj_attr(request):
    obj_id = request.matchdict['obj_id']
    key = request.matchdict['key']
    attr = models._Attr.get_id(key)
    if not attr:
        return HTTPNotFound()
    if not str(attr['obj']) == obj_id:
        return HTTPNotFound()

    method = _http_method(request)
    if method == 'GET':
        pass
    elif method == 'POST':
        if not request.user:
            return require_signin(request)
        try:
            action = request.params['action']
        except KeyError:
            return HTTPBadRequest()
        if action == 'Accept':
            attr.accept(request.user)
            request.session.flash('action_taken', 'Attribute accepted')
        elif action == 'Acknowledge':
            attr.acknowledge(request.user)
            request.session.flash('action_taken', 'Attribute acknowledged')
        elif action == 'Reject':
            attr.reject(request.user)
            request.session.flash('action_taken', 'Attribute rejected')
        else:
            return HTTPBadRequest()

    return {'attr': attr}



