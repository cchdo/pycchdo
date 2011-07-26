import os
import urllib
import urllib2
import json
import datetime
     
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPInternalServerError

import paste.fileapp

import pycchdo.models as models


signin_uri = "/session/identify"


_janrain_api_key = 'f7b289d355eadb8126008f619702389daf108ae5'


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


def require_signin(request):
    request.session['signin_return_uri'] = request.url
    return HTTPSeeOther(location=signin_uri)


def _sign_in_user(request, profile):
    identifier = profile['identifier']
     
    # these fields MAY be in the profile, but are not guaranteed. it
    # depends on the provider and their implementation.
    name = profile.get('name')
    email = profile.get('email')

    p = models.Person.find_one({'identifier': identifier})
    if not p:
        p = models.Person(identifier=identifier, name_first=name['givenName'],
                          name_last=name['familyName'], email=email)
        p.save()
    return remember(request, str(p['_id']))


def home(request):
    return {'project': 'pycchdo'}


def clear_db(request):
    models.cchdo().objs.drop()
    models.cchdo().attrs.drop()
    return Response('OK')


def session_show(request):
    person = request.user
    return {'person': person}


def session_identify(request):
    return {}


def session_new(request):
    token = request.params['token']
     
    # auth_info expects an HTTP Post with the following paramters:
    api_params = {
        'token': token,
        'apiKey': _janrain_api_key,
        'format': 'json',
    }
     
    # make the api call
    http_response = urllib2.urlopen(
        'https://rpxnow.com/api/v2/auth_info', urllib.urlencode(api_params))

    # read the json response
    auth_info_json = http_response.read()
     
    # Step 3) process the json response
    auth_info = json.loads(auth_info_json)
     
    # Step 4) use the response to sign the user in
    if auth_info['stat'] == 'ok':
        profile = auth_info['profile']

        try:
            redirect_uri = request.session['signin_return_uri']
            del request.session['signin_return_uri']
        except KeyError:
            redirect_uri = '/session'

        return HTTPSeeOther(location=redirect_uri,
                            headers=_sign_in_user(request, profile))
    else:
        print 'ERROR: During signin: ' + auth_info['err']['msg']
        return HTTPInternalServerError()


def session_delete(request):
    return HTTPSeeOther(location='/session', headers=forget(request))


def objs(request):
    return {'objs': models.Obj.all()}


def obj_new(request):
    if not request.user:
        return require_signin(request)
    obj = models.Obj(request.user)
    obj['_obj_type'] = request.params.get('_obj_type', models.Obj.__name__)
    obj.save()
    return {}


def obj_show(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    if not obj:
        return HTTPNotFound()
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
    method = _http_method(request)

    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    if not obj:
        return HTTPNotFound()

    if method  == 'GET':
        return {'obj': obj}

    if not request.user:
        return require_signin(request)

    key = request.params.get('key', None)
    if not key:
        return HTTPBadRequest('Attr key required')

    # TODO note
    note = None

    if method == 'POST':
        value = request.params.get('value', None)
        type = request.params.get('type', None)

        if type == 'text':
            pass
        elif type == 'datetime':
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        elif type == 'list':
            def unescape(s, escape='\\'):
                n = s.find(escape)
                while n > -1:
                    s = s[:n] + s[n + 1:]
                    n = s.find(escape, n + 1)
                return s
            value = [unescape(x) for x in value.split(',')]
        elif type == 'id':
            value = models.Obj.get_id(id)
            if value:
                value = value['_id']
        else:
            # file upload sends the field storage anyway
            pass
        obj.attrs.set(key, value, request.user, note)
        return {'obj': obj}
    elif method == 'DELETE':
        obj.attrs.delete(key, request.user, note)
        return {'obj': obj}


def obj_attr(request):
    obj_id = request.matchdict['obj_id']
    key = request.matchdict['key']
    attr = models.Attr.get_id(key)
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


def cruises_index(request):
    return {'cruises': models.Cruise.map_mongo(models.Cruise.find())}


def cruise_show(request):
    cruise_id = request.matchdict['cruise_id']
    cruise_obj = models.Cruise.get_id(cruise_id)

    # If the id is not an ObjectId, try searching based on ExpoCode
    if not cruise_obj:
        # TODO
        pass

    cruise = {}
    history = []
    if cruise_obj:
        cruise['expocode'] = cruise_obj.attrs.get('expocode', '')
        cruise['collections'] = None # TODO
        cruise['ship'] = cruise_obj.attrs.get('ship', None)
        try:
            cruise['ship_name'] = cruise['ship']['name']
        except TypeError:
            cruise['ship_name'] = ''
        except KeyError:
            cruise['ship_name'] = ''
        cruise['country'] = cruise_obj.attrs.get('country', None)
        try:
            cruise['country_name'] = cruise['country']['name']
        except TypeError:
            cruise['country_name'] = ''
        except KeyError:
            cruise['country_name'] = ''
        cruise['chief_scientists'] = [{'name_first': 'ALICE'}, {'name_first': 'BOB'}]
        cruise['date_start'] = cruise_obj.attrs.get('date_start')
        cruise['date_end'] = cruise_obj.attrs.get('date_end')
        cruise['cruise_dates'] = ''
        if cruise['date_start'] and cruise['date_end']:
            cruise['cruise_dates'] = '/'.join(map(str, (cruise['date_start'], cruise['date_end'])))
        cruise['statuses'] = cruise_obj.attrs.get('statuses')

        def getAttr(cruise_obj, type):
            id = None
            for c in cruise_obj.attrs.accepted_changes:
                if c['key'] == type:
                    id = c['_id']
            return models.Attr.get_id(id)

        data_files = {}
        data_files['map'] = {
            'full': getAttr(cruise_obj, 'map_full'),
            'thumb': getAttr(cruise_obj, 'map_thumb'),
        }
        data_files['exchange'] = {
            'ctdzip_exchange': getAttr(cruise_obj, 'ctdzip_exchange'),
            'bottle_exchange': getAttr(cruise_obj, 'bottle_exchange'),
        }
        data_files['netcdf'] = {
            'ctdzip_netcdf': getAttr(cruise_obj, 'ctdzip_netcdf'),
            'bottlezip_netcdf': getAttr(cruise_obj, 'bottlezip_netcdf'),
        }
        data_files['woce'] = {
            'sum_woce': getAttr(cruise_obj, 'sum_woce'),
            'bottle_woce': getAttr(cruise_obj, 'bottle_woce'),
            'ctdzip_woce': getAttr(cruise_obj, 'ctdzip_woce'),
        }
        data_files['doc'] = {
            'doc_txt': getAttr(cruise_obj, 'doc_txt'),
            'doc_pdf': getAttr(cruise_obj, 'doc_pdf'),
        }

        history = models.Attr.map_mongo(cruise_obj.attrs.history())

    return {
        'cruise': cruise,
        'data_files': _collapsed_dict(data_files) or {},
        'history': history,
        }

class GridOutWrapper(object):
    def __init__(self, g):
        self._g = g

    def __len__(self):
        return self._g.length

    def __getattr__(self, name):
        return self._g[name]


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

    project_path = os.path.dirname(__file__)
    static_path = os.path.join('templates', 'static')

    path = os.path.join(project_path, static_path, subpath)
    relpath = os.path.join(static_path, subpath)

    if os.path.isfile(path):
        return {'_static': relpath}
    return HTTPNotFound()
