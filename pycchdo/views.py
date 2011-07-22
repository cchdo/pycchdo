import os
import urllib
import urllib2
import json
import datetime
     
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPBadRequest, HTTPInternalServerError

import pycchdo.models as models


signin_uri = "/session/identify"


_janrain_api_key = 'f7b289d355eadb8126008f619702389daf108ae5'


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
    if method  == 'GET':
        obj_id = request.matchdict['obj_id']
        obj = models.Obj.get_id(obj_id)
        return {'obj': obj}
    elif method == 'POST':
        if not request.user:
            return require_signin(request)
        obj_id = request.matchdict['obj_id']
        obj = models.Obj.get_id(obj_id)
        key = request.params.get('key', None)
        value = request.params.get('value', None)
        type = request.params.get('type', 'text')
        if not key:
            return HTTPBadRequest()
        if type == 'datetime':
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

        # TODO note
        note = None
        obj.attrs.set(key, value, request.user, note)
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

        history = models.Attr.map_mongo(cruise_obj.attrs.history())

    return {'cruise': cruise, 'maps': {'thumb': '/data/onetime/atlantic/a20/a20_316N151_3trk.jpg', 'full': '/data/onetime/atlantic/a20/a20_316N151_3trk.gif'}, 'history': history}


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


def advanced_search(request):
    return {}

def search_results(request):
    str = request.params['query']
    return Response("%s"%(str))

def search(request):
    params = request.str_params
    if params: 
        query = ''
        if 'query' in params:
            return HTTPSeeOther(location='/search/results?query=%s'%(params['query']))
        if params.get('line'): 
            query = query + "line:" + urllib.quote_plus(params['line']) + '+'
        if params.get('expocode'): 
            query = query + "expocode:" + urllib.quote_plus(params['expocode']) + '+'
        if params.get('ship'):
            query = query + "ship:" + urllib.quote_plus(params['ship']) + '+'
        if params.get('people'):
            query = query + "people:" + urllib.quote_plus(params['people']) + '+'
        if params.get('country'):
            query = query + "country:" + urllib.quote_plus(params['country']) + '+'
        if params.get('search_date_min'):
            query = query + "from:" + urllib.quote_plus(params['search_date_min']) + '+'
        if params.get('search_date_max'):
            query = query + "to:" + urllib.quote_plus(params['search_date_min']) + '+'
        return HTTPSeeOther(location='/search/results?query=%s'%(query))
    return HTTPSeeOther(location='/search/advanced') 
