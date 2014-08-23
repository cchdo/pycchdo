import logging
import json
import os
from cgi import FieldStorage
from contextlib import contextmanager

from tempfile import NamedTemporaryFile
import sqlite3

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response

from pykml.factory import KML_ElementMaker as KML

from lxml import etree

from libcchdo.model.datafile import DataFile
from libcchdo.fns import uniquify
from libcchdo.formats.formats import read_arbitrary
from libcchdo.formats import google_wire
import libcchdo.formats.netcdf_oceansites as nc_os
import libcchdo.formats.ctd.netcdf as ctdnc
import libcchdo.formats.ctd.exchange as ctdex
import libcchdo.formats.ctd.netcdf_oceansites as ctdnc_os
import libcchdo.formats.ctd.zip.netcdf as ctdzipex
import libcchdo.formats.ctd.zip.netcdf_oceansites as ctdzipnc_os
import libcchdo.formats.bottle.exchange as botex

from pycchdo import models, helpers as h
from pycchdo.models.serial import Cruise
from pycchdo.models.file_types import data_file_descriptions
from pycchdo.views import file_response
from pycchdo.views.staff import staff_signin_required
from pycchdo.util import StringIO
from pycchdo.log import getLogger, DEBUG, INFO


log = getLogger(__name__)
log.setLevel(DEBUG)


_ALLOWED_OCEANSITES_TIMESERIES = ['BATS', 'HOT']


_ALLOWED_FILE_FORMATS = ['botex', 'ctdzipex']


@staff_signin_required
def data_cmp(request):
    return {}


@staff_signin_required
def visual(request):
    return {}


@staff_signin_required
def convert(request):
    return {'OCEANSITES_TIMESERIES_SELECT': _ALLOWED_OCEANSITES_TIMESERIES}


def _xhr_response(request, obj, status=None):
    if status is not None:
        request.response.status = status
    if request.is_xhr:
        return obj
    return '<textarea>%s</textarea>' % json.dumps(obj)


@contextmanager
def _libcchdo_log_capture(level=INFO):
    log = getLogger('libcchdo')
    orig_log_level = log.getEffectiveLevel()
    log.setLevel(level)

    log_stream = StringIO()
    conversion_log_handler = logging.StreamHandler(log_stream)
    conversion_log_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s'))
    log.addHandler(conversion_log_handler)

    yield log_stream

    log.removeHandler(conversion_log_handler)
    log.setLevel(orig_log_level)


@staff_signin_required
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
        return file_response(request, output_file, 'attachment')
    except Exception, e:
        log.debug(e)
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


@staff_signin_required
def convert_from_to(request):
    cfrom = request.params.get('from')
    cto = request.params.get('to')
    if not cfrom or not cto:
        raise HTTPBadRequest()
    return available_converters.get((cfrom, cto))(request)


@staff_signin_required
def archives(request):
    return {}


@staff_signin_required
def dumps(request):
    return {}


@staff_signin_required
def dumps_sqlite(request):
    type = request.params.get('type')
    datatype = request.params.get('datatype')
    seahunt = request.params.get('seahunt')

    if type == 'metadata' and datatype == 'ctd':
        temp = NamedTemporaryFile()
        conn = sqlite3.connect(temp.name)

        cur = conn.cursor()
        cur.execute(
            'CREATE TABLE metadata_ctd (filename, dac, id, date date, '
            'latitude numeric, longitude numeric, profile_type, cruise, '
            'institution, nb_parameters, date_update, avail_exchange bool, '
            'avail_woce bool, avail_netcdf bool)')
        conn.commit()

        ctd_formats = filter(lambda x: x.startswith('ctd'),
                             data_file_descriptions.keys())

        insert_vals = [
            'filename', 'dac', 'id', 'date', 'latitude', 'longitude', 
            'profile_type', 'cruise', 'institution', 'date_update',
            'avail_exchange', 'avail_woce', 'avail_netcdf', ]

        dac = 'CCHDO'
        profile_type = 'ctd'
        cruises = Cruise.query().all()
        h.reduce_specificity(request, *cruises)
        for c in cruises:
            if any(c.get(format) for format in ctd_formats):
                cruise = c.uid
                date = c.date_start

                lat = None
                lng = None
                if c.track:
                    lng, lat = c.track.coords[0]

                #try:
                #    institutions = [c.institution]
                #except AttributeError:
                #    institutions = []
                #for rpi in c.get('participants'):
                #    try:
                #        institutions.append(rpi['institution'])
                #    except KeyError:
                #        pass
                try:
                    institution = c.institution.name
                except AttributeError:
                    institution = None

                files = dict((format.split('_')[-1],
                              c.get(format)) for format in ctd_formats)

                if files['exchange']:
                    file = files['exchange']
                else:
                    if files['netcdf']:
                        file = files['netcdf']
                    else:
                        file = files['woce']

                avail_exchange = bool(files['exchange'])
                avail_woce = bool(files['woce'])
                avail_netcdf = bool(files['netcdf'])

                filename = file.name
                id = str(file.id)
                date_update = file.upload_date

                cur.execute(
                    'INSERT INTO metadata_ctd (%s) VALUES (%s)' % (
                        ','.join(insert_vals),
                        ','.join(['?'] * len(insert_vals))),
                    (filename, dac, id, date, lat, lng, profile_type, cruise,
                     institution, date_update, avail_exchange, avail_woce,
                     avail_netcdf))
        conn.commit()
        conn.close()

        field = FieldStorage()
        field.file = temp
        field.name = 'metadata_ctd.sqlite'
        temp.seek(0, os.SEEK_END)
        field.length = temp.tell()
        temp.seek(0)
        return file_response(request, field, disposition='attachment')
    elif seahunt and type == 'metadata':
        temp = NamedTemporaryFile()
        conn = sqlite3.connect(temp.name)

        cur = conn.cursor()
        cur.execute(
            'CREATE TABLE metadata_seahunt (id, aliases, collections, ship, '
            'country, chi_sci, ports, date_start date, date_end date, track)')
        conn.commit()

        ctd_formats = filter(lambda x: x.startswith('ctd'),
                             data_file_descriptions.keys())

        insert_vals = [
            'id', 'aliases', 'collections', 'ship', 'country', 'chi_sci', 
            'ports', 'date_start', 'date_end', 'track', ]

        cruises_seahunt = Cruise.only_if_accepted_is(False).all()
        h.reduce_specificity(request, *cruises_seahunt)
        for c in cruises_seahunt:
            id = c.uid
            aliases = ', '.join(c.aliases)
            collections = ', '.join([x.name for x in c.collections])
            ship = None
            if c.ship:
                ship = c.ship.name
            country = None
            if c.country:
                country = c.country.name
            chi_sci = None
            if c.chief_scientists:
                chi_sci = c.chief_scientists[0].full_name
            ports = None
            if c.ports:
                ports = ', '.join(c.ports)
            date_start = c.date_start
            date_end = c.date_end

            track = None
            if c.track:
                track = str(c.track)

            cur.execute(
                'INSERT INTO metadata_seahunt (%s) VALUES (%s)' % (
                    ','.join(insert_vals),
                    ','.join(['?'] * len(insert_vals))),
                (id, aliases, collections, ship, country, chi_sci, ports,
                 date_start, date_end, track))
        conn.commit()
        conn.close()

        field = FieldStorage()
        field.file = temp
        field.name = 'metadata_ctd.sqlite'
        temp.seek(0, os.SEEK_END)
        field.length = temp.tell()
        temp.seek(0)
        return file_response(request, field, disposition='attachment')

    raise HTTPBadRequest()
