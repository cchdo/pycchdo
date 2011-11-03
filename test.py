import datetime
import os
from urllib import quote
from json import dumps

from flask import Flask, request, render_template, make_response

import webhelpers.html as whh
import webhelpers.html.tags


app = Flask(__name__)
app.debug = True


RADIUS_EARTH = 6371.01 # km
DEFAULT_PARAMS = {
    'max_coords': 50,
    'time_min': 1967,
    'time_max': datetime.datetime.now(),
}


@app.route("/")
def index():
    return render_template(
        'map.jinja2', 
        default=DEFAULT_PARAMS,
        whh=whh,
        encode=quote,
        to_json=dumps,
    )


@app.route("/ids")
def ids():
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
    ids = []

    req_shapes = request.args.get('shapes', None)
    req_ids = request.args.get('ids', None)
    req_q = request.args.get('q', None)

    if req_shapes:
        polygons = []
        filters = []

        for shape in req_shapes:
            special, vs = shape.split(':')
            coords = [[float(x) for x in c.split(',')] for c in vs.split('_')]

            if special == 'polygon':
                pass
    #            polygon = Polygon.from_coordinates(coords)
    #            polygons.push(polygon)
    #            filters.push(Proc.new {|track|
    #                track_in_polygon?(polygon, track)})
            elif special == 'rectangle':
                pass
    #            # Do a rotl-1 to turn nw, se into sw, ne
    #            if coords[0] and coords[2] and coords[0][0] < coords[2][0]
    #                coords.unshift(coords.pop)
    #            end
    #            polygon = Polygon.from_coordinates(coords)
    #            polygons.push(polygon)
    #            filters.push(Proc.new {|track|
    #                track_in_polygon?(polygon, track)})
    #            #filters.push(Proc.new {|track|
    #            #    track_in_rectangle?(polygon, track)})
            elif special == 'circle':
                pass
    #            polygon = Polygon.from_coordinates(coords)
    #            polygons.push(polygon)
    #            filters.push(Proc.new {|track|
    #                track_in_polygon?(polygon, track)})
    #            #filters.push(Proc.new {|track|
    #            #    track_in_circle?(center, radius, track)})

        time_min = int(request.args.get('time_min', DEFAULT_PARAMS['time_min']))
        # Bump the year forward because we want searches up to Jan 1 00:00 year + 1
        time_max = int(request.args.get('time_max',
                                        DEFAULT_PARAMS['time_max'])) + 1

        # All geo searches need to be refiltered because MySQL only selects for
        # MaxBoundingRectangleIntersection
        for polygon, filter in zip(polygons, filters):
            raw_tracks = getTracksInSelection(polygon, time_min, time_max)
            ids += filter(lambda t: filter(t.track), raw_tracks)
    elif req_ids:
        ids = [Cruise.get_by_id(id) for id in req_ids]
    elif req_q:
        ids = []
        #ids = find_cruises(params[:q])[0]

    # Build JSON response with id: track
    id_track = {}
    for c in ids:
        id_track[c.id] = None
        try:
            id_track[c.id] = c.id
        except AttributeError:
            pass

    cruises = [(id, Cruise.get_by_id(id)) for id in id_track.keys()]

    response = {
        'id_t': id_track,
        'i': _info(cruises),
        't': _track(cruises, request.args.get('max_coords', '')),
    }
    resp = make_response(dumps(response))
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route("/layers")
def layers():
    """ Provides a mirror for KML/NAV files that need to be publicly served.

    This is necessary for a user to view their local files.
    
    Returns: text (path to the mirrored file)

    """
    # XXX
    dirname = ''
    filename = ''

    #dirname = 'map_mirror'
    #dir = File.join(RAILS_ROOT, 'public', dirname)
    #Dir.mkdir(dir) unless File.directory? dir
    #now = Time.now.to_i
    #Dir.foreach(dir) do |file|
    #    if file !~ /\./ and file.to_i < now - 60
    #        File.unlink(File.join(dir, file))
    #    end
    #end
    #filename = File.join(dir, now.to_s)
    #f = File.new(filename, 'w')
    #input = params[:file]
    #input.each_line {|line| f.write line }
    #f.flush.close

    filepath = os.path.join(dirname, os.path.basename(filename))
    return whh.HTML.textarea(whh.literal(dumps({'url': filepath})))


def _max_coords(max_coords=None):
    if max_coords:
        return int(max_coords)
    return int(DEFAULT_PARAMS['max_coords'])


def _track(idcruises, max_coords=None):
    max_coords = _max_coords(max_coords)
    d = {}
    for id, cruise in idcruises:
        try:
            t = cruise.track
            d[id] = [[p.x, p.y] for p in pareDown(t, max_coords)]
        except (KeyError, AttributeError):
            pass
    return d


def _info(idcruises):
    infos = {}
    for id, cruise in idcruises:
        try:
            # CCHDO
            infos[id] = {
                'name': c.expocode or '',
                'programs': c.collections or '',
                'contacts': c.Chief_Scientist or '',
                'ship': c.Ship_Name or '',
                'cruise_dates': [c.Begin_Date, c.EndDate].join('/') or '',
            }

            # SEAHUNT
            #infos[id] = {
            #    :name => (c.aliases && c.aliases.first &&
            #              c.aliases.first.alias) || '',
            #    :programs => c.programs.map {|p| p.name.strip}.join(', '),
            #    :ship => (c.ship && c.ship.full_name.strip) || '',
            #    :country => (c.country && c.country.name.strip) || '',
            #    :cruise_dates => c.cruise_dates || '',
            #    :contacts => c.contacts.map {|c| c.fullname}.join(', '),
            #    #:institutions => c.institutions.map {|c| c.name}.join(', '),
            #}
        except (KeyError, AttributeError):
            pass
    return infos


def getTracksInSelection(selection, time_min, time_max):
    return []
    #return Cruise.find_by_sql([[
    #    # CCHDO
    #    "SELECT DISTINCT cruises.id,cruises.ExpoCode,Track as track FROM cruises JOIN track_lines ",
    #    "ON cruises.ExpoCode = track_lines.ExpoCode WHERE ",
    #    "EndDate > '?' AND Begin_Date < '?' AND ",

    #    # SEAHUNT
    #    #"SELECT DISTINCT id,track FROM cruises WHERE ",
    #    #"realdate_start > '?' AND realdate_start < '?' AND ",

    #    # MySQL
    #     "Intersects(GeomFromText(",
    #     "\"LINESTRING#{selection.text_representation}\"),track)"
    #    # PostgresQL
    #    #"Intersects(track,", "GeomFromText(\"#{selection.as_wkt}\"))"
    #].join(''), min_time, max_time])


def pareDown(coords, max=50):
    """
    Args:
        max: a maximum number of coordinates in the track to return. The
            coordinates will be thinned out but the first and last will remain.

    """
    step_size = max(len(coords) / max(max, 1), 1)
    return [coords[i] for i in range(0, len(coords), step_size)]


def between_lat(lower, test, upper):
    return lower <= test and test < upper 


def between_lng(lower, test, upper):
    if lower > upper: # crossed the date-line
        return ((lower <= test and test < 180) or 
                (-180 <= test and test < upper))
    return lower <= test and test < upper 


def track_in_rectangle(rect, track):
    sw, ne = rect.points[0], rect.points[2]
    def testcoords(coords):
        for coord in coords:
            yield (between_lng(sw.x, coord.lng, ne.x) and
                   between_lat(sw.y, coord.lat, ne.y))
    return any(testcoords(track))


def track_in_circle(center, radius, track):
    def test_coord(coords):
        for coord in coords:
            d = center.ellipsoidal_distance(coord) / 1000
            yield 1 <= d and d < radius
    return any(test_coord(track))


def track_in_polygon(polygon, track):
    def in_polygon(poly, pt):
        len = len(poly)
        j = len - 1
        c = False
        for i in range(0, len):
            v1 = poly[i]
            v2 = poly[j]
            if (((v1.y > pt.y) != (v2.y > pt.y)) and
                (pt.x < (v2.x - v1.x) * (pt.y - v1.y) / (v2.y - v1.y) + v1.x)):
                c = not c
            j = i
        return c

    # Our polygons are only single ringed. GeoRuby has multi-ringed polygons so
    # take the first one.
    def test_coords(coords):
        for coord in coords:
            yield in_polygon(polygon[0], coord)
    return any(test_coords(track))


def track_in_any_loci(loci, radius, track):
    def test_coords(coords):
        for center in coords:
            yield track_in_circle(center, radius, track)
    return any(test_coords(loci))


if __name__ == '__main__':
    app.run()
