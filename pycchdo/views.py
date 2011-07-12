import urllib
import urllib2
import json
     
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPNotFound, HTTPSeeOther, HTTPInternalServerError

import pycchdo.models as models

def _http_method(request):
    try:
        return request.params['_method']
    except KeyError:
        return request.method


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
    from pyramid.security import authenticated_userid
    person = request.user
    return {'person': person}


def session_new(request):
    token = request.params['token']
     
    # auth_info expects an HTTP Post with the following paramters:
    api_params = {
        'token': token,
        'apiKey': 'f7b289d355eadb8126008f619702389daf108ae5',
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
        return HTTPSeeOther(location='/session', headers=_sign_in_user(request, profile))
    else:
        print 'An error occured: ' + auth_info['err']['msg']
        return HTTPInternalServerError()


def session_delete(request):
    return HTTPSeeOther(location='/session', headers=forget(request))


def objs(request):
    return {'objs': models.Obj.all()}


def obj_new(request):
    import pyramid.security as sec
    obj = models.Obj(request.user)
    obj_type = request.params.get('obj_type', None)
    if obj_type:
        obj['_obj_type'] = obj_type
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
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.get_id(obj_id)
    return {'obj': obj}


def obj_attr(request):
    obj_id = request.matchdict['obj_id']
    obj = models.Obj.find_id(obj_id)
    key = request.matchdict['key']
    return {'obj': obj}


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

        history = models.Attr.map_mongo(cruise_obj.attrs.history())

    return {'cruise': cruise, 'maps': {'thumb': '/data/onetime/atlantic/a20/a20_316N151_3trk.jpg', 'full': '/data/onetime/atlantic/a20/a20_316N151_3trk.gif'}, 'history': history}
