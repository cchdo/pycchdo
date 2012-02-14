import urllib
import urllib2
import json

from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPSeeOther, HTTPInternalServerError

import pycchdo.models as models


_janrain_api_key = 'f7b289d355eadb8126008f619702389daf108ae5'


def _save_request(request, uri=None):
    if uri is None:
        uri = request.referrer
    if uri is None:
        uri = request.url
    request.session['signin_return_uri'] = uri


def _redirect_uri(request):
    try:
        redirect_uri = request.session['signin_return_uri']
        del request.session['signin_return_uri']
    except KeyError:
        redirect_uri = '/session/identify'
    if redirect_uri is None:
        redirect_uri = '/session/identify'
    return redirect_uri


def _restore_request(request, profile):
    return HTTPSeeOther(location=_redirect_uri(request),
                        headers=_sign_in_user(request, profile))


def require_signin(request):
    _save_request(request)
    request.session['skip_save_signin_return_uri'] = True
    return HTTPSeeOther(location='/session/identify')


def session_show(request):
    person = request.user
    return {'person': person}


def session_identify(request):
    if not request.session.get('skip_save_signin_return_uri', False):
        _save_request(request)
        try:
            del request.session['skip_save_signin_return_uri']
        except KeyError:
            pass
    try:
        del request.session['anonymous']
    except KeyError:
        pass
    return {}


def _sign_in_user(request, profile):
    identifier = profile['identifier']
     
    # these fields MAY be in the profile, but are not guaranteed. it
    # depends on the provider and their implementation.
    name = profile.get('name')
    email = profile.get('email')

    p = models.Person.get_one({'identifier': identifier})
    if not p:
        p = models.Person(identifier=identifier, name_first=name['givenName'],
                          name_last=name['familyName'], email=email)
        p.save()
    try:
        return remember(request, str(p.id))
    except AttributeError:
        request.session.flash('Currently unable to sign in', 'help')
        return []


def session_new(request):
    if request.params.get('anonymous') == 'optin':
        request.session['anonymous'] = True
        return HTTPSeeOther(location=_redirect_uri(request))

    token = request.params.get('token', None)

    if not token:
        return HTTPSeeOther(location=_redirect_uri(request))
     
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
     
    # process the json response
    auth_info = json.loads(auth_info_json)
     
    # use the response to sign the user in
    if auth_info['stat'] == 'ok':
        profile = auth_info['profile']
        return _restore_request(request, profile)
    else:
        print 'ERROR: During signin: ' + auth_info['err']['msg']
        return HTTPSeeOther(location='/session/identify')


def session_delete(request):
    return HTTPSeeOther(location=request.referrer, headers=forget(request))
