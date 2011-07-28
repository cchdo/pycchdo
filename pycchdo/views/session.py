import urllib
import urllib2
import json

from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPSeeOther, HTTPInternalServerError

import pycchdo.models as models


_janrain_api_key = 'f7b289d355eadb8126008f619702389daf108ae5'


def require_signin(request):
    request.session['signin_return_uri'] = request.url
    return HTTPSeeOther(location='/session/identify')


def session_show(request):
    person = request.user
    return {'person': person}


def session_identify(request):
    return {}


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
