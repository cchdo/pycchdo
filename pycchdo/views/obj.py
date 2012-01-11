from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPSeeOther, \
                                   HTTPUnauthorized

import pycchdo.models as models

from . import *
from pycchdo.helpers import has_mod
from session import require_signin


def objs(request):
    objs = models.Obj.get_all()
    objs = _paged(request, objs)
    return {'objs': objs}


def obj_new(request):
    if not request.user:
        return require_signin(request)

    if _http_method(request) != 'PUT':
        return HTTPBadRequest()

    obj_type = request.params.get('_obj_type', models.Obj.__name__)
    attributes = {}
    attrs = {}
    for k, v in request.params.items():
        if k.startswith('attr_'):
            attrs[k[len('attr_'):]] = v
        elif k.startswith('attribute_'):
            attributes[k[len('attribute_'):]] = v

    try:
        obj = models.__dict__[obj_type](request.user)
        obj.save()
    except KeyError:
        raise ValueError('No such obj type (%s) allowed' % obj_type)
    if attributes:
        for k, v in attributes.items():
            if k in obj.allowed_untracked_keys:
                obj[k] = v
        obj.save()
    if attrs:
        for k, v in attrs.items():
            print obj, k, v, request.user
            obj.set(k, v, request.user)

    if obj._obj_type == models.Cruise.__name__:
        return HTTPSeeOther(location=request.route_path('cruise_show',
                                                        cruise_id=obj.id))
    return {'obj': obj}


def obj_show(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    if not obj:
        return HTTPNotFound()

    link = request.url
    method = _http_method(request)
    if method == 'DELETE':
        if obj:
            obj.remove()
            obj = None
            request.session.flash('Removed Obj %s' % obj_id, 'action_taken')
            return HTTPSeeOther(location='/objs')
    elif method == 'PUT':
        if not request.user:
            return require_signin(request)
        if not has_mod(request):
            return HTTPUnauthorized()
        try:
            action = request.params['action']
            obj = obj.polymorph()
            if action == 'Accept':
                obj.accept(request.user)
                request.session.flash(
                    'Accepted Obj %s' % obj_id, 'action_taken')
                request.session.flash(
                    "Reminder: Attributes are not accepted automatically.", 'help')
                return HTTPSeeOther(location=request.referrer)
            if action == 'Reject':
                obj.reject(request.user)
                request.session.flash(
                    'Rejected Obj %s' % obj_id, 'action_taken')
                return HTTPSeeOther(location=request.referrer)
        except KeyError:
            pass
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
        return HTTPNotFound('No attr with key %s' % key)
    if not str(attr['obj']) == obj_id:
        return HTTPNotFound('No obj with id %s' % obj_id)

    method = _http_method(request)
    if method == 'GET':
        pass
    elif method == 'PUT':
        if not request.user:
            return require_signin(request)
        if not has_mod(request):
            return HTTPUnauthorized()

        def redirect():
            # Special case for accepting expocode. The cruise will not exist any
            # more under the original expocode so redirect to the new expocode.
            if attr.key == 'expocode' and action == 'Accept':
                return HTTPSeeOther(location=request.route_url(
                                    'cruise_show', cruise_id=attr.value))
            return HTTPSeeOther(location=request.referrer)

        try:
            action = request.params['action']
        except KeyError:
            return HTTPBadRequest()

        if action == 'Accept':
            if attr.key == 'data_suggestion':
                try:
                    accept_key = request.params['accept_key']
                except KeyError:
                    request.session.flash('You must provide a new key that is '
                                          'a file type', 'help')
                    return redirect()
                if accept_key not in models.data_file_descriptions.keys():
                    request.session.flash(
                        '%s is not a valid file type' % accept_key, 'help')
                    return redirect()
                else:
                    attr.key = accept_key
                    request.session.flash(
                        'Attr key changed to "%s"' % accept_key,
                        'action_taken')

            def accept_suggested():
                attr.accept(request.user)
                request.session.flash('Attr change accepted',
                                      'action_taken')
            try:
                accept_value = request.params['accept_value']
                if accept_value:
                    attr.accept_value(
                        text_to_obj(accept_value,
                                    attr.obj.__class__.attr_type(attr.key)),
                        request.user)
                    request.session.flash(
                        'Attr change accepted with new value "%s"' % (
                            accept_value), 'action_taken')
                else:
                    accept_suggested()
            except KeyError:
                accept_suggested()
        elif action == 'Acknowledge':
            attr.acknowledge(request.user)
            request.session.flash('Attr change acknowledged', 'action_taken')
        elif action == 'Reject':
            attr.reject(request.user)
            request.session.flash('Attr change rejected', 'action_taken')
        return redirect()
    return {'attr': attr}
