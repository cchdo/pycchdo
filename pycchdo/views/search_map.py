import datetime
import os
import json
import math
import time
import tempfile

from pyramid.response import Response
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPBadRequest, HTTPInternalServerError,
    )

from webhelpers import html as whh

from shapely.geometry import polygon as poly

from pycchdo import models, helpers as h
from pycchdo.models import search
from pycchdo.models.serial import Cruise, Change
from pycchdo.views import file_response
from pycchdo.log import ColoredLogger, DEBUG


log = ColoredLogger(__name__)
log.setLevel(DEBUG)


RADIUS_EARTH = 6371.01 # km
DEFAULTS = {
    'max_coords': 50,
    'time_min': 1967,
    'time_max': datetime.date.today().year,
    'roi_result_limit': 50,
}


class MapsJSONEncoder(json.JSONEncoder):
    """ Encodes ObjectIds and floats in a different way

    http://stackoverflow.com/questions/1447287/format-floats-with-standard-json-module

    Notes:
      - _iterecode and _iterencode_dict are lame overrides to allow for
        float formatting override. Poor design in STL...
        http://stackoverflow.com/questions/1447287/

    """
    FLOAT_FRMT = '{0:.4f}'

    def floatstr(self, obj):
        return self.FLOAT_FRMT.format(obj)

    def _iterencode(self, obj, markers=None):
        # stl JSON lame override #1
        new_obj = obj
        if isinstance(obj, float):
            if not math.isnan(obj) and not math.isinf(obj):
                return self.floatstr(obj)
        return super(MapsJSONEncoder, self)._iterencode(
            new_obj, markers=markers)

    def _iterencode_dict(self, dct, markers=None):
        # stl JSON lame override #2
        new_dct = {}
        for key, value in dct.iteritems():
            if isinstance(key, float):
                if not math.isnan(key) and not math.isinf(key):
                    key = self.floatstr(key)
            new_dct[key] = value
        return super(MapsJSONEncoder, self)._iterencode_dict(
            new_dct, markers=markers)

    def default(self, obj):
        return json.JSONEncoder.default(self, obj)


def index(request, commands=''):
    context = {'default': DEFAULTS}
    if commands:
        context['commands'] = commands
    return context


def ids(request):
    """ Perform search and give a mapping of result ids and track ids.

    There are a few ways this search can be performed:
    1. Shapes
        Params:
            - shapes - areas of interest
            - min_time, max_time - the time range allowable.
    2. IDs
        Params:
            - ids - the IDs that need to be returned with their track mapping.
    3. q
        Params:
            - q - a string query
    Returns: JSON
        {cruise_id: track_id, ...}

    """
    try:
        req_shapes = request.params.get('shapes', None).split('|')
    except AttributeError:
        req_shapes = None
    try:
        req_ids = request.params.get('ids', None).split(',')
    except AttributeError:
        req_ids = None
    req_q = request.params.get('q', None)

    cruises = []
    limited = False

    if req_shapes:
        polygons = []
        filters = []

        for shape in req_shapes:
            special, vs = shape.split(':')
            try:
                coords = [[float(x) for x in c.split(',')] for c in vs.split('_')]
            except ValueError:
                raise HTTPBadRequest()

            if special == 'polygon':
                polygon = poly.Polygon(coords)
                polygons.append(polygon)
                filters.append(lambda track: track_in_polygon(polygon, track))
            elif special == 'rectangle':
                # Do a rotl-1 to turn nw, se into sw, ne
                if coords[0] and coords[2] and coords[0][0] < coords[2][0]:
                    coords = coords[1:] + [coords[0]]
                polygon = poly.Polygon(coords)
                polygons.append(polygon)
                filters.append(lambda track: track_in_polygon(polygon, track))
            elif special == 'circle':
                polygon = poly.Polygon(coords)
                polygons.append(polygon)
                filters.append(lambda track: track_in_polygon(polygon, track))

        time_min = int(request.params.get('time_min', DEFAULTS['time_min']))
        # Bump the year forward because we want searches up to 
        # Jan 1 00:00 year + 1
        time_max = int(request.params.get(
            'time_max', DEFAULTS['time_max'])) + 1

        # All geo searches need to be refiltered because MySQL only selects for
        # MaxBoundingRectangleIntersection
        for polygon, f in zip(polygons, filters):
            raw_tracks, limited = getTracksInSelection(polygon, time_min, time_max)
            cruises.extend(filter(lambda t: f(t.track), raw_tracks))
    elif req_ids:
        def get_by_id_or_expo(id):
            c = Cruise.get_id(id)
            if not c:
                c = Cruise.get_all_by_expocode(id)
                if len(c) > 0:
                    c = c[0]
                else:
                    c = None
            return c
        cruises = [get_by_id_or_expo(id) for id in req_ids]
    elif req_q:
        results = request.search_index.search(request.params.get('q', ''))
        cruises = search.compile_into_cruises(results)
    h.reduce_specificity(cruises)

    # Build JSON response with id: track
    id_track = {}
    id_cruises = []
    for c in cruises:
        try:
            tid = str(c.get_attr('track').id)
        except (KeyError, AttributeError):
            tid = None
        id_track[str(c.id)] = tid
        id_cruises.append((c.id, tid, c))

    response = {
        'id_t': id_track,
        'i': _info(id_cruises),
        't': _track(id_cruises, request.params.get('max_coords', '')),
        'limited': limited,
    }
    resp = Response(json.dumps(response, cls=MapsJSONEncoder))
    resp.content_type = 'application/json'
    return resp


def layer(request):
    """ Provides a mirror for KML/NAV files that need to be publicly served.

    This is necessary for a user to view their local files.

    If given a path request, will attempt to return the file.
    Cleanup is done during each request.
    
    Returns: text (path to the mirrored file)

    """
    file_age_limit_secs = 120
    temp_suffix = 'layer.map.search.pycchdo'

    temp_dir = None
    global_temp_dir = tempfile.gettempdir()
    for entry in os.listdir(global_temp_dir):
        if entry.endswith(temp_suffix):
            temp_dir = os.path.join(global_temp_dir, entry)
    if temp_dir is None:
        tempdir = tempfile.mkdtemp(temp_suffix, '')
    if temp_dir is None:
        raise HTTPInternalServerError('Failed to make temp directory')

    path = request.params.get('path', '')
    if path:
        # Return the file if the request is for a path
        full_path = os.path.join(temp_dir, path)
        if os.path.isfile(full_path):
            size = os.stat(full_path).st_size
            f = open(full_path, 'r')
            return file_response(request, f)
    else:
        # Do some cleanup
        for entry in os.listdir(temp_dir):
            full_path = os.path.join(temp_dir, entry)
            stat = os.lstat(full_path)
            if stat.st_mtime < time.time() - file_age_limit_secs:
                os.unlink(full_path)

        # Store the file and return a path to get the file
        temp_file, temp_path = tempfile.mkstemp(dir=temp_dir)
        temp_file = os.fdopen(temp_file, 'w')
        file = request.POST.get('file', None)
        if file is None:
            raise HTTPBadRequest()
        else:
            file = file.file
        while True:
            data = file.read(2<<16)
            if not data:
                break
            temp_file.write(data)
        file.close()
        temp_file.close()

        response = {
            'url': request.current_route_url(
                _query={'path': os.path.basename(temp_path)})}
        return Response(unicode(whh.HTML.textarea(
                                    whh.literal(json.dumps(response)))))
    raise HTTPNotFound()


def _info(id_cruises):
    infos = {}
    for id, idt, cruise in id_cruises:
        try:
            id = str(id)
            infos[id] = {
                'name': cruise.expocode or '',
                'contacts': ', '.join(
                    [pi.person.name for pi in cruise.chief_scientists]) or '',
                'cruise_dates': h.cruise_dates(cruise)[2],
            }

            country = cruise.country
            if country:
                infos[id]['country'] = country.name

            try:
                collections = cruise.collections
                if collections:
                    infos[id]['programs'] = ', '.join(
                        [coll.name for coll in collections])
                else:
                    infos[id]['programs'] = ''
            except AttributeError:
                infos[id]['programs'] = ''

            try:
                ship = cruise.ship
                if ship:
                    infos[id]['ship'] = ship.name
                else:
                    infos[id]['ship'] = ''
            except AttributeError, e:
                print e
                infos[id]['ship'] = ''
        except (KeyError, AttributeError) as e:
            log.warn('Unable to read info for %s %s' % (id, e))
    return infos


def _max_coords(max_coords=None):
    if max_coords:
        return int(max_coords)
    return int(DEFAULTS['max_coords'])


def _track(id_cruises, max_coords=None):
    max_coords = _max_coords(max_coords)
    d = {}
    for id, idt, c in id_cruises:
        try:
            t = c.track
            d[idt] = pareDown(t, max_coords)
        except (KeyError, AttributeError) as e:
            log.warn('Unable to get track for %s %s' % (id, e))
    return d


def getTracksInSelection(selection, time_min, time_max):
    return Cruise.cruises_in_selection(
        selection, (time_min, time_max), DEFAULTS['roi_result_limit'])


def pareDown(line, max_coords=50):
    """
    Args:
        max: a maximum number of coordinates in the track to return. The
            coordinates will be thinned out but the first and last will remain.

    """
    l = len(line.coords)
    step_size = max(int(l / max(max_coords, 1)), 1)
    return [list(line.coords[i]) for i in range(0, l, step_size)]


def in_range(lo, x, hi):
    """ Tells if x is in the interval [lo, hi) """
    return lo <= x and x < hi


def between_lat(lower, test, upper):
    return in_range(lower, test, upper) 


def between_lng(lower, test, upper):
    if lower > upper:
        # crossed the date-line
        return in_range(lower, test, 180) or in_range(-180, test, upper)
    return in_range(lower, test, upper)


def track_in_rectangle(rect, track):
    sw, ne = rect.points[0], rect.points[2]
    def in_rect(coord):
        return (between_lng(sw.x, coord.lng, ne.x) and
                between_lat(sw.y, coord.lat, ne.y))
    return any(in_rect(coord) for coord in track.coords)


def _in_circle(pt, center, radius):
    d = center.ellipsoidal_distance(pt) / 1000
    return 1 <= d and d < radius


def track_in_circle(center, radius, track):
    return any(_in_circle(coord, center, radius) for coord in track.coords)


def track_in_polygon(polygon, track):
    def in_polygon(poly, pt):
        l = len(poly)
        j = l - 1
        c = False
        for i in range(0, l):
            v1 = poly[i]
            v2 = poly[j]
            if (((v1[1] > pt[1]) != (v2[1] > pt[1])) and
                (pt[0] < (v2[0] - v1[0]) * (pt[1] - v1[1]) / (v2[1] - v1[1]) +
                 v1[0])):
                c = not c
            j = i
        return c

    # Our polygons are only single ringed. Shapely has multi-ringed polygons so
    # take the first one.
    return any(in_polygon(polygon.exterior.coords, coord) for coord in
               track.coords)


def track_in_any_loci(loci, radius, track):
    def in_any_loci(coord):
        for locus in loci:
            if _in_circle(pt, center, radius):
                return True
    return any(in_any_loci(coord) for coord in track.coords)
