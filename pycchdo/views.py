from pyramid.view import view_config

import pycchdo.models as models

def _http_method(request):
    try:
        return request.params['_method']
    except KeyError:
        return request.method

def home(request):
    return {'project': 'pycchdo'}


def objs(request):
    return {'objs': models.Obj.all()}


def obj_new(request):
    models.Obj().save()
    return {}


def obj_show(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.find(obj_id)
    if _http_method(request) == 'DELETE':
        if obj:
            obj.remove()
            obj = None
            attrs = []
    else:
        try:
            attrs = obj['attrs']
        except KeyError:
            attrs = []
    return {'obj': obj, 'attrs': attrs}


def obj_attrs(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.find(obj_id)
    return {'obj': obj}


def obj_attr(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.find(obj_id)
    key = request.matchdict['key']
    return {'obj': obj}
