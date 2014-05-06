import inspect
import urllib
import urllib2
import json

import transaction

from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPSeeOther, HTTPInternalServerError

from pycchdo.models.serial import DBSession, Person
from pycchdo.log import ColoredLogger


log = ColoredLogger(__name__)


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


def _profile_to_person(profile):
    identifier = profile['identifier']
     
    # these fields MAY be in the profile, but are not guaranteed. it
    # depends on the provider and their implementation.
    name = profile.get('name')
    email = profile.get('email')

    person = Person.query().filter(Person.identifier == identifier).first()
    if not person:
        person = Person.create().obj
        person.set_id_names(identifier=identifier, name=name['formatted'])
        person.email = email
        pid = person.id
        transaction.commit()
        person = Person.query().get(pid)
    return person


def _do_signin(request, person):
    raise HTTPSeeOther(
        location=_redirect_uri(request),
        headers=_sign_in_user(request, person))


def require_signin(request):
    _save_request(request)
    request.session['skip_save_signin_return_uri'] = True
    raise HTTPSeeOther(location='/session/identify')


def signin_required(check_signin):
    """Decorate a view_callable so that the signed in user must fulfill a check
    in order to view.

    """
    def checked_signin(view_callable):
        numargs = len(inspect.getargspec(view_callable)[0])
        if numargs == 1:
            def decorator(request):
                response = check_signin(request)
                if response is None:
                    response = view_callable(request)
                return response
            return decorator
        elif numargs == 2:
            def decorator(context, request):
                response = check_signin(request)
                if response is None:
                    response = view_callable(context, request)
                return response
            return decorator
        else:
            def decorator(*args, **kwargs):
                request = args[1]
                response = check_signin(request)
                if response is None:
                    response = view_callable(*args, **kwargs)
                return response
            return decorator
    return checked_signin


def session_show(request):
    person = request.user
    return {'person': person}


def session_identify(request):
    if request.user:
        raise HTTPSeeOther(location=request.route_url('session'))
    if not request.session.get('skip_save_signin_return_uri', False):
        _save_request(request)
        try:
            del request.session['skip_save_signin_return_uri']
        except KeyError:
            pass
    return {}


def _sign_in_user(request, person):
    try:
        return remember(request, str(person.id))
    except AttributeError, e:
        log.error(e)
        request.session.flash('Currently unable to sign in', 'help')
        return []


def session_new(request):
    if 'direct_name' in request.params or 'direct_email' in request.params:
        try:
            direct_name = request.params['direct_name']
            direct_email = request.params['direct_email']
        except KeyError:
            raise HTTPSeeOther(location=_redirect_uri(request))
        if not direct_email:
            raise HTTPSeeOther(location=_redirect_uri(request))
        person = Person.create().obj
        person.set_id_names(name=direct_name)
        person.email = direct_email
        pid = person.id
        transaction.commit()
        person = Person.query().get(pid)
        return _do_signin(request, person)

    # Sign in a user for real from Janrain
    token = request.params.get('token', None)

    if not token:
        raise HTTPSeeOther(location=_redirect_uri(request))
     
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
        return _do_signin(request, _profile_to_person(profile))
    else:
        print 'ERROR: During signin: ' + auth_info['err']['msg']
        raise HTTPSeeOther(location='/session/identify')


def session_delete(request):
    location = request.params.get('location', request.referrer)
    if not location:
        location = '/'
    raise HTTPSeeOther(location=location, headers=forget(request))
