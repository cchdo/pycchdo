"""Datacart controller.

"""
from datetime import datetime
from copy import copy
from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from logging import getLogger
from traceback import format_exc


log = getLogger(__name__)


from pyramid.response import Response
from pyramid.renderers import render_to_response
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPMethodNotAllowed, HTTPNotFound, HTTPSeeOther)

from webhelpers.text import plural

from tempfilezipstream import (
    TempFileStreamingZipFile, FileWrapper, ZIP_DEFLATED)

from pycchdo.views import *
from pycchdo.models.datacart import Datacart
from pycchdo.models.serial import store_context, Change, Cruise


ZIP_FILE_LIMIT = 20


TEMPNAME = 'cchdo_datacart_{0}.zip' 


def get_datacart(request):
    """Retrieve the datacart from the session or create a new one."""
    try:
        return request.session['datacart']
    except KeyError:
        request.session['datacart'] = Datacart()
        return request.session['datacart']


def _redirect_back_or_default(request):
    if request.referrer:
        return HTTPSeeOther(location=request.referrer)
    else:
        return HTTPSeeOther(location=request.route_path('datacart'))


def _json_response(obj):
    resp = render_to_response('json', obj)
    resp.content_type = 'application/json'
    return resp


def index(request):
    return {'ZIP_FILE_LIMIT': ZIP_FILE_LIMIT}


def add(request):
    try:
        id = request.params['id']
    except (KeyError, ValueError):
        raise HTTPNotFound()
    
    dattr = Change.query().get(id)
    if not dattr:
        request.session.flash('Error adding file to data cart.', 'error')
        raise HTTPNotFound()

    request.datacart.add(dattr.id)

    if request.is_xhr:
        return _json_response({'cart_count': len(request.datacart)})
    else:
        request.session.flash(
            'Added {0} to data cart'.format(dattr.value.name), 'success')
        return _redirect_back_or_default(request)


def remove(request):
    try:
        id = request.params['id']
    except (KeyError, ValueError):
        raise HTTPNotFound()
    
    dattr = Change.query().get(id)
    if not dattr:
        request.session.flash('Error removing file from data cart.', 'error')
        raise HTTPNotFound()

    request.datacart.remove(dattr.id)

    if request.is_xhr:
        return _json_response({'cart_count': len(request.datacart)})
    else:
        request.session.flash(
            'Removed {0} from data cart'.format(dattr.value.name), 'success')
        return _redirect_back_or_default(request)


def add_cruise(request):
    try:
        cruise_id = request.params['id']
    except KeyError:
        raise HTTPNotFound()

    file_count, count_diff = _add_single_cruise(request, cruise_id)

    if request.is_xhr:
        return _json_response(
            {'cart_count': len(request.datacart), 'diff': count_diff})
    else:
        message = "Added {0} to data cart".format(
            plural(count_diff, 'file', 'files'))
        present_count = file_count - count_diff
        if present_count > 0:
            message += " ({0} already present).".format(present_count)
        else:
            message += "."
        request.session.flash(message, 'notice')
        return _redirect_back_or_default(request)


def remove_cruise(request):
    try:
        cruise_id = request.params['id']
    except KeyError:
        raise HTTPNotFound()

    file_count, count_diff = _remove_single_cruise(request, cruise_id)

    if request.is_xhr:
        return _json_response(
            {'cart_count': len(request.datacart), 'diff': count_diff})
    else:
        message = "Removed {0} from data cart".format(
            plural(count_diff, 'file', 'files'))
        present_count = file_count - count_diff
        if present_count > 0:
            message += " ({0} not present).".format(present_count)
        else:
            message += "."
        request.session.flash(message, 'notice')
        return _redirect_back_or_default(request)


def add_cruises(request):
    try:
        cruise_ids = request.params.getall('ids')
    except KeyError:
        raise HTTPNotFound()
    log.debug(cruise_ids)

    file_count_all = 0
    count_diff_all = 0
    for id in cruise_ids:
        try:
            file_count, count_diff = _add_single_cruise(request, id)
        except HTTPNotFound:
            file_count = 0
            count_diff = 0
        file_count_all += file_count
        count_diff_all += count_diff

    if request.is_xhr:
        return _json_response(
            {'cart_count': len(request.datacart), 'diff': count_diff})
    else:
        message = "Added {0} to datacart".format(
            plural(count_diff_all, 'file', 'files'))
        present_count = file_count_all - count_diff_all
        if present_count > 0:
            message += " ({0} already present).".format(present_count)
        else:
            message += "."
        request.session.flash(message, 'success')
        return _redirect_back_or_default(request)


def remove_cruises(request):
    try:
        cruise_ids = request.params.getall('ids')
    except KeyError:
        raise HTTPNotFound()

    file_count_all = 0
    count_diff_all = 0
    for id in cruise_ids:
        try:
            file_count, count_diff = _remove_single_cruise(request, id)
        except HTTPNotFound:
            file_count = 0
            count_diff = 0
        file_count_all += file_count
        count_diff_all += count_diff

    if request.is_xhr:
        return _json_response(
            {'cart_count': len(request.datacart), 'diff': count_diff})
    else:
        message = "Removed {0} from datacart".format(
            plural(count_diff_all, 'file', 'files'))
        present_count = file_count_all - count_diff_all
        if present_count > 0:
            message += " ({0} not present).".format(present_count)
        else:
            message += "."
        request.session.flash(message, 'success')
        return _redirect_back_or_default(request)


def clear(request):
    method = http_method(request)
    if method != 'POST':
        raise HTTPMethodNotAllowed()
    try:
        del request.session['datacart']
    except KeyError:
        pass
    if request.is_xhr:
        return _json_response({'cart_count': 0})
    else:
        request.session.flash('Cleared data cart', 'success')
        return _redirect_back_or_default(request)


def _add_single_cruise(request, cruise_id):
    try:
        cruise_obj = Cruise.query().get(cruise_id)
        if cruise_obj is None:
            raise ValueError()
    except ValueError:
        request.session.flash(
            'Error adding cruise {0} dataset from data cart'.format(
            cruise_id), 'error')
        raise HTTPNotFound()

    before_count = len(request.datacart)

    mapped_files = cruise_obj.file_attrs
    file_count = 0
    for ftype, fattr in mapped_files.items():
        if not Datacart.is_file_type_allowed(ftype):
            continue
        request.datacart.add(fattr.id)
        file_count += 1

    after_count = len(request.datacart)
    count_diff = after_count - before_count
    return (file_count, count_diff)


def _remove_single_cruise(request, cruise_id):
    try:
        cruise_obj = Cruise.query().get(cruise_id)
    except ValueError:
        request.session.flash(
            'Error removing cruise dataset from data cart', 'error')
        raise HTTPNotFound()

    before_count = len(request.datacart)

    mapped_files = cruise_obj.file_attrs
    file_count = 0
    for ftype, fattr in mapped_files.items():
        if not Datacart.is_file_type_allowed(ftype):
            continue
        try:
            request.datacart.remove(fattr.id)
        except KeyError:
            pass
        file_count += 1

    after_count = len(request.datacart)
    count_diff = before_count - after_count
    return (file_count, count_diff)


class ChangeFileWrapper(FileWrapper):
    EMPTY_FILE = StringIO('missing, contact the CCHDO')

    def __init__(self, arcname, fileobj):
        super(ChangeFileWrapper, self).__init__(arcname, fileobj)
        self._fobj = None

    @property
    def fobj(self):
        if self._fobj is None:
            try:
                self._fobj = self.__fobj.open_file()
            except (OSError, IOError) as err:
                self._fobj = copy(self.EMPTY_FILE)
                log.error(u'Missing file {0} {1!r}'.format(self.__fobj, err))
            except Exception as error:
                log.error(repr(error))
        return self._fobj

    @fobj.setter
    def fobj(self, value):
        self.__fobj = value
        self._fobj = None

    @fobj.deleter
    def fobj(self):
        del self.__fobj
        self._fobj = None

    def __repr__(self):
        return u'ChangeFileWrapper({0}, {1!r})'.format(self.arcname, self.fobj)


def download(request):
    method = http_method(request)
    if method != 'POST':
        raise HTTPMethodNotAllowed()

    try:
        archive = request.params['archive']
    except KeyError:
        raise HTTPBadRequest()

    try:
        ids = map(int, archive.split(','))
    except ValueError:
        raise HTTPBadRequest()

    attrs = Change.get_all_by_ids(*ids)

    zstream = TempFileStreamingZipFile([])
    for attr in attrs:
        dfile = attr.value
        zstream.write(ChangeFileWrapper(dfile.name, dfile),
                      compress_type=ZIP_DEFLATED)

    fname = TEMPNAME.format(datetime.now().strftime('%FT%T'))

    def app_iter():
        with store_context(request.fsstore):
            for chunk in iter(zstream):
                yield chunk

    return Response(
        app_iter=app_iter(),
        content_type='application/zip', 
        content_disposition='attachment; filename={0}'.format(fname))
