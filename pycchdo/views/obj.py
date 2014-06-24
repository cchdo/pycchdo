import transaction

from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPSeeOther, \
                                   HTTPUnauthorized

from . import *
from pycchdo.models import serial as model
from pycchdo.models.serial import DBSession, Change, Note, Cruise, Obj
from pycchdo.models.file_types import data_file_descriptions
from pycchdo.helpers import has_mod
from pycchdo.views import log
from pycchdo.views.staff import staff_signin_required
from session import require_signin

from sqlalchemy.orm import noload


@staff_signin_required
def objs(request):
    objs = Obj.query().\
        options(
            noload('cache_obj_avs'),
            noload('attrs_accepted'),
            noload('attrs')
        ).all()
    objs = paged(request, objs)
    return {'objs': objs}


def _obj_new(request):
    if http_method(request) != 'PUT':
        raise HTTPBadRequest()

    obj_type = request.params.get('_obj_type', Obj.__name__)
    attributes = {}
    attrs = {}
    notes = []
    for k, v in request.params.items():
        if k.startswith('attr_'):
            attrs[k[len('attr_'):]] = v
        elif k.startswith('attribute_'):
            attributes[k[len('attribute_'):]] = v
        elif k.startswith('note'):
            notes.append(v)

    try:
        obj = model.__dict__[obj_type].propose(request.user).obj
    except KeyError:
        raise ValueError('No such obj type (%s) allowed' % obj_type)
    if attributes:
        for k, v in attributes.items():
            if k in obj.allowed_untracked_keys:
                obj[k] = v
        DBSession.flush()
    if attrs:
        for k, v in attrs.items():
            try:
                if v == '':
                    continue
            except TypeError:
                pass
            if k == 'track' and isinstance(obj, Cruise):
                obj.set(request.user, k, str_to_track(v))
            else:
                if k in ['expocode', 'map_thumb', ]:
                    # Don't try to set it if map_thumb is not a file.
                    if k == u'map_thumb' and type(v) == unicode:
                        continue
                    obj.set(request.user, k, v)
                else:
                    obj.set(request.user, k, v)

    for note in notes:
        if note:
            obj._notes.append(Note(request.user, note))

    DBSession.flush()
    obj_id = obj.id
    transaction.commit()

    if isinstance(obj, Cruise):
        log.info(u'redirecting to {0}'.format(obj_id))
        raise HTTPSeeOther(
            location=request.route_path('cruise_show', cruise_id=obj_id))
    return {'obj': obj}


@staff_signin_required
def obj_new(request):
    return _obj_new(request)


@staff_signin_required
def obj_show(request):
    obj_id = request.matchdict['obj_id']
    obj = Obj.query().get(obj_id)
    if not obj:
        raise HTTPNotFound()

    link = request.url
    method = http_method(request)
    if method == 'DELETE':
        if obj:
            obj.remove()
            obj = None
            request.session.flash('Removed Obj %s' % obj_id, 'action_taken')
            raise HTTPSeeOther(location='/objs')
    elif method == 'PUT':
        if not request.user:
            return require_signin(request)
        if not has_mod(request):
            raise HTTPUnauthorized()
        try:
            action = request.params['action']
            if action == 'Accept':
                obj.accept(request.user)
                request.session.flash(
                    'Accepted Obj %s' % obj_id, 'action_taken')
                request.session.flash(
                    "Reminder: Attributes are not accepted automatically.", 'help')
                raise HTTPSeeOther(location=request.referrer)
            if action == 'Reject':
                obj.reject(request.user)
                request.session.flash(
                    'Rejected Obj %s' % obj_id, 'action_taken')
                raise HTTPSeeOther(location=request.referrer)
        except KeyError:
            pass
        transaction.commit()
        obj = Obj.query().get(obj_id)


    if obj.obj_type in ['Cruise', 'Person', 'Institution', 'Country']:
        link = request.url.replace('/obj/', '/%s/' % obj.obj_type.lower())
    elif obj.obj_type == 'Obj':
        link = None

    return {
        'id': obj_id,
        'obj': obj,
        'asdict': obj.to_dict(),
        'link': link,
    }

@staff_signin_required
def obj_attrs(request):
    method = http_method(request)

    obj_id = request.matchdict['obj_id']
    obj = Obj.query().get(obj_id)
    if not obj:
        raise HTTPNotFound()

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
        note = Note(
            request.user.id, note_body, note_action, note_data_type, note_subject)

    key = request.params.get('key', None)
    if method == 'POST':
        value = request.params.get('value', None)
        if not key and value:
            raise HTTPBadRequest('Attr required if setting value')
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
            value = Obj.query().get(value)
            if value:
                value = value.id
        else:
            # file upload should send the FieldStorage unchanged
            # notes should not change anything either
            pass
        change = obj.set(request.user, key, value)
    elif method == 'DELETE':
        change = obj.delete(request.user, key)

    if change:
        change._notes.append(note)
    return {'obj': obj, 'type': __builtins__['type']}


@staff_signin_required
def obj_attr(request):
    obj_id = request.matchdict['obj_id']
    key = request.matchdict['key']
    attr = Change.query().get(key)
    if not attr:
        log.error(u'No attr with key {0!r}'.format(key))
        raise HTTPNotFound()
    if not str(attr.obj_id) == obj_id:
        log.error(u'No obj with id {0}'.format(obj_id))
        raise HTTPNotFound()

    method = http_method(request)
    if method == 'GET':
        pass
    elif method == 'PUT':
        if not request.user:
            return require_signin(request)
        if not has_mod(request):
            raise HTTPUnauthorized()

        try:
            action = request.params['action']
        except KeyError:
            raise HTTPBadRequest()

        # Special case for accepting expocode. The cruise will not exist any
        # more under the original expocode so redirect to the new expocode.
        if attr.attr == 'expocode' and action == 'Accept':
            redirect = HTTPSeeOther(
                location=request.route_url('cruise_show', cruise_id=attr.value))
        else:
            redirect = HTTPSeeOther(location=request.referrer)

        if action == 'Accept':
            if attr.attr == 'data_suggestion':
                try:
                    accept_key = request.params['accept_key']
                except KeyError:
                    request.session.flash(
                        'You must provide a new key that is a file type',
                        'help')
                    return redirect
                if accept_key not in data_file_descriptions.keys():
                    request.session.flash(
                        u'{0} is not a valid file type'.format(accept_key),
                        'help')
                    return redirect
                else:
                    attr.attr = accept_key
                    request.session.flash(
                        u'Attr key changed to {0!r}'.format(accept_key),
                        'action_taken')

            accept_value = request.params.get('accept_value', None)
            if accept_value == '':
                accept_value = None
            if accept_value is not None:
                try:
                    attr.accept(request.user, 
                        text_to_obj(accept_value,
                                    type(attr.obj).attr_type(attr.attr)))
                    request.session.flash(
                        u'Attr change accepted with new value {0!r}'.format(
                            accept_value), 'action_taken')
                except ValueError, err:
                    log.error(err)
                    request.session.flash(
                        u'{0!r} is not valid'.format(attr.attr), 'help')
                    return redirect
            else:
                attr.accept(request.user)
                request.session.flash('Attr change accepted', 'action_taken')
        elif action == 'Acknowledge':
            attr.acknowledge(request.user)
            request.session.flash(
                '{0} acknowledged'.format(attr), 'action_taken')
        elif action == 'Reject':
            attr.reject(request.user)
            request.session.flash(
                '{0} rejected'.format(attr), 'action_taken')

        transaction.commit()
        return redirect
    return {'attr': attr}
