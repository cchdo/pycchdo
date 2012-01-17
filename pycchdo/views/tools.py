from cgi import FieldStorage
import json
import logging
from StringIO import StringIO

from pyramid.response import Response

from libcchdo import LOG
from libcchdo.fns import read_arbitrary, uniquify
from libcchdo.model.datafile import DataFile
from libcchdo.formats import google_wire
import libcchdo.formats.ctd.netcdf as ctdnc
import libcchdo.formats.ctd.exchange as ctdex
import libcchdo.formats.ctd.netcdf_oceansites as ctdnc_os
import libcchdo.formats.ctd.zip.netcdf as ctdzipex
import libcchdo.formats.ctd.zip.netcdf_oceansites as ctdzipnc_os


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


def convert_any_to_google_wire(request):
    try:
        file = request.POST['file']
    except KeyError:
        request.response.status = 400
        return {'error': 'No file.'}

    input_type = request.params.get('input_type', 'detect')
    if input_type not in _ALLOWED_FILE_FORMATS or input_type == 'detect':
        input_type = None

    orig_log_level = LOG.getEffectiveLevel()
    LOG.setLevel(logging.INFO) 

    log_stream = StringIO()
    conversion_log_handler = logging.StreamHandler(log_stream)
    conversion_log_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s'))
    LOG.addHandler(conversion_log_handler)

    read_file = read_arbitrary(file.file, input_type, file.filename)
    output = StringIO()
    google_wire.write(read_file, output, json=True)

    LOG.removeHandler(conversion_log_handler)
    LOG.setLevel(orig_log_level) 

    errors = uniquify(log_stream.getvalue().split('\n'))

    if not output:
        return {'error': 'Failed to parse: %s' % json.dumps(errors)}

    return {'data': json.loads(output.getvalue()), 'errors': errors}


def _get_oceansites_timeseries(request):
    ts = request.params.get('timeseries')
    if ts not in _ALLOWED_OCEANSITES_TIMESERIES:
        return None
    return ts


def _convert(request, fn, filename, *args):
    try:
        file = request.params['file']
    except KeyError:
        request.response.status = 400
        return 'Please give a file to convert'
    try:
        output = fn(file, *args)
        output_file = FieldStorage()
        output_file.file = output
        output_file.name = filename
        return _file_response(output_file)
    except Exception, e:
        logging.debug(e)
        request.response.status = 500
        return 'Error converting file: %s' % e


def ctd_netcdf_to_ctd_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFile()
        ctdnc.read(df, file)
        out = StringIO()
        ctdnc_os.write(df, out)
        return out
    ts = _get_oceansites_timeseries(request)
    return _convert(request, cvt, ts, 'OS_.nc' % (ts or ''))


def ctdzip_netcdf_to_ctdzip_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFile()
        ctdzipnc.read(df, file)
        out = StringIO()
        ctdzipnc_os.write(df, out)
        return out
    ts = _get_oceansites_timeseries(request)
    return _convert(request, cvt, ts, 'OS_.zip' % (ts or ''))


def ctd_exchange_to_ctdzip_oceansites_netcdf(request):
    def cvt(file, ts):
        df = DataFile()
        ctdex.read(df, file)
        out = StringIO()
        ctdnc_os.write(df, out)
        return out
    ts = _get_oceansites_timeseries(request)
    return _convert(request, cvt, ts, 'OS_%s.nc' % (ts or ''))


def bottle_exchange_to_kml(request):
    def cvt(file, ts):
        df = DataFile()
        botex.read(df, file)
        out = StringIO()
        placemarks = ['%f,%f' % coord for coord \
            in zip(df.columns['LONGITUDE'].values,
                   df.columns['LATITUDE'].values)]
        out.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"
     xmlns:gx="http://www.google.com/kml/ext/2.2"
     xmlns:kml="http://www.opengis.net/kml/2.2"
     xmlns:atom="http://www.w3.org/2005/Atom">
<Document>
<name></name>
<Style id="linestyle">
  <LineStyle>
    <width>4</width>
    <color>ff0000ff</color>
  </LineStyle>
</Style>
<Placemark>
<styleUrl>#linestyle</styleUrl>
<LineString>
  <tessellate>1</tessellate>
  <coordinates>%s</coordinates>
</LineString>
</Placemark>
</Document></kml>""" % ' '.join(placemarks))
        return out
    return _convert(request, cvt, None, 'converted.kml')
