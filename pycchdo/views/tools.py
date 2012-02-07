from cgi import FieldStorage
import json
import logging
import os
from contextlib import contextmanager
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response

from pykml.factory import KML_ElementMaker as KML

from lxml import etree

from libcchdo import LOG
from libcchdo.fns import read_arbitrary, uniquify
from libcchdo.model.datafile import DataFile
from libcchdo.formats import google_wire
import libcchdo.formats.netcdf_oceansites as nc_os
import libcchdo.formats.ctd.netcdf as ctdnc
import libcchdo.formats.ctd.exchange as ctdex
import libcchdo.formats.ctd.netcdf_oceansites as ctdnc_os
import libcchdo.formats.ctd.zip.netcdf as ctdzipex
import libcchdo.formats.ctd.zip.netcdf_oceansites as ctdzipnc_os
import libcchdo.formats.bottle.exchange as botex

from pycchdo.views import _file_response


_ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']


_ALLOWED_FILE_FORMATS = ['botex', 'ctdzipex']


def data_cmp(request):
    return {}


def visual(request):
    return {}


def convert(request):
    return {'OCEANSITES_TIMESERIES_SELECT': _ALLOWED_OCEANSITES_TIMESERIES}


def _xhr_response(request, obj, status=None):
    if status is not None:
        request.response.status = status
    if request.is_xhr:
        return obj
    return '<textarea>%s</textarea>' % json.dumps(obj)


@contextmanager
def _libcchdo_log_capture(level=logging.INFO):
    orig_log_level = LOG.getEffectiveLevel()
    LOG.setLevel(level)

    log_stream = StringIO()
    conversion_log_handler = logging.StreamHandler(log_stream)
    conversion_log_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s'))
    LOG.addHandler(conversion_log_handler)

    yield log_stream

    LOG.removeHandler(conversion_log_handler)
    LOG.setLevel(orig_log_level)


def convert_any_to_google_wire(request):
    try:
        file = request.POST['file']
    except KeyError:
        request.response.status = 400
        return {'error': 'No file.'}

    input_type = request.params.get('input_type', 'detect')
    if input_type not in _ALLOWED_FILE_FORMATS or input_type == 'detect':
        input_type = None

    errors = ''
    with _libcchdo_log_capture() as log_stream:
        try:
            read_file = read_arbitrary(file.file, input_type, file.filename)
        except ValueError, e:
            if input_type == 'detect' or input_type is None:
                return {'error': 'Failed to detect file type'}
            else:
                return {'error': str(e)}
        output = StringIO()
        google_wire.write(read_file, output, json=True)
        errors = uniquify(log_stream.getvalue().split('\n'))

    if not output:
        return {'error': 'Failed to parse: %s' % json.dumps(errors)}
    return {'data': json.loads(output.getvalue()), 'errors': errors}


def _get_oceansites_timeseries(request):
    ts = request.params.get('timeseries')
    if ts not in _ALLOWED_OCEANSITES_TIMESERIES:
        return None
    return ts


def _convert(request, fn, filename_callback, *args):
    try:
        file = request.params['file']
    except KeyError:
        request.response.status = 400
        return {'error': 'Please give a file to convert'}
    try:
        with _libcchdo_log_capture() as log:
            try:
                df, output = fn(file.file, *args)
            except:
                errors = uniquify(log.getvalue().split('\n'))
                return {'error': errors}
        output_file = FieldStorage()
        output_file.file = output
        output.seek(0, os.SEEK_END)
        output_file.length = output.tell()
        output.seek(0)
        output_file.name = filename_callback(file, df, output)
        return _file_response(output_file, 'attachment')
    except Exception, e:
        logging.debug(e)
        request.response.status = 500
        return {'error': 'Could not convert file: %r' % e}


def _ctd_netcdf_to_ctd_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFile()
        ctdnc.read(df, file)
        out = StringIO()
        ctdnc_os.write(df, out)
        return df, out

    ts = _get_oceansites_timeseries(request)

    def filename(file, df, output):
        timeseries_info = nc_os.TIMESERIES_INFO[ts]
        return nc_os.file_and_timeseries_info_to_id(
            output, timeseries_info, 'CTD')
    return _convert(request, cvt, filename, ts)


def _ctdzip_netcdf_to_ctdzip_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFileCollection()
        ctdzipnc.read(df, file)
        out = StringIO()
        ctdzipnc_os.write(df, out)
        return df, out
    ts = _get_oceansites_timeseries(request)

    def filename(file, df, output):
        return '%s_nc_ctd_oceansites.zip' % os.path.splitext(file.filename)[0]
    return _convert(request, cvt, filename, ts)


def _ctd_exchange_to_ctdzip_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFile()
        ctdex.read(df, file)
        out = StringIO()
        ctdnc_os.write(df, out)
        return df, out

    ts = _get_oceansites_timeseries(request)

    def filename(file, df, output):
        timeseries_info = nc_os.TIMESERIES_INFO[ts]
        return nc_os.file_and_timeseries_info_to_id(
            output, timeseries_info, 'CTD')
    return _convert(request, cvt, filename, ts)


def _bottle_exchange_to_kml(request):
    def cvt(file):
        df = DataFile()
        botex.read(df, file)
        out = StringIO()
        placemarks = ['%3.5f,%3.5f' % coord for coord \
            in zip(df.columns['LONGITUDE'].values,
                   df.columns['LATITUDE'].values)]
        kml = KML.kml(
            KML.Document(
                KML.Style(
                    KML.LineStyle(
                        KML.width(4),
                        KML.color('ff0000ff'),
                    ),
                    id='linestyle'
                ),
                KML.Placemark(
                    KML.styleUrl('#linestyle'),
                    KML.LineString(
                        KML.tessellate(1),
                        KML.coordinates(' '.join(placemarks)),
                    ),
                ),
            ),
        )
        out.write(etree.tostring(kml, pretty_print=True))
        out.seek(0)
        return df, out
    def filename(file, df, output):
        return os.path.splitext(file.filename)[0] + '.kml'
    return _convert(request, cvt, filename)


available_converters = {
    ('ctd_netcdf', 'ctd_oceansites_netcdf'): _ctd_netcdf_to_ctd_oceansites_netcdf,
    ('ctdzip_netcdf', 'ctdzip_oceansites_netcdf'): _ctdzip_netcdf_to_ctdzip_oceansites_netcdf,
    ('ctd_exchange', 'ctdzip_oceansites_netcdf'): _ctd_exchange_to_ctdzip_oceansites_netcdf,
    ('bottle_exchange', 'kml'): _bottle_exchange_to_kml,
}


def convert_from_to(request):
    cfrom = request.params.get('from')
    cto = request.params.get('to')
    if not cfrom or not cto:
        return HTTPBadRequest()
    return available_converters.get((cfrom, cto))(request)
