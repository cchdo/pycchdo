# Dependencies: GeoRuby
# All geo searches need to be refiltered because MySQL only selects for
# MaxBoundingRectangleIntersection

class SearchMapsController < ApplicationController
  $RADIUS_EARTH = 6371.01 #km
  $DEFAULT = {
    :max_coords => '50',
    :min_time => 1967,
    :max_time => Date.today.year
  }

  def index
      @DEFAULT = $DEFAULT
  end

  def ids
      # Perform search and give a mapping of result ids and track ids.
      # There are a few ways this search can be performed:
      # 1. Shapes
      #     Params:
      #         - shapes - areas of interest
      #         - min_time, max_time - the time range allowable.
      # 2. IDs
      #     Params:
      #         - ids - the IDs that need to be returned with their track mapping.
      # 3. q
      #     Params:
      #         - q - a string query
      # Returns: JSON
      #     {cruise_id: track_id, ...}

      ids = []
      if shapes = params[:shapes]
          polygons = []
          filters = []

          shapes.each do |shape|
              special, vs = shape.split(':')
              coords = [vs.split('_').map {|c| c.split(',').map {|x| x.to_f}}]

              if special == 'polygon'
                  polygon = Polygon.from_coordinates(coords)
                  polygons.push(polygon)
                  filters.push(Proc.new {|track|
                      track_in_polygon?(polygon, track)})
              elsif special == 'rectangle'
                  # Do a rotl-1 to turn nw, se into sw, ne
                  if coords[0] and coords[2] and coords[0][0] < coords[2][0]
                      coords.unshift(coords.pop)
                  end
                  polygon = Polygon.from_coordinates(coords)
                  polygons.push(polygon)
                  filters.push(Proc.new {|track|
                      track_in_polygon?(polygon, track)})
                  #filters.push(Proc.new {|track|
                  #    track_in_rectangle?(polygon, track)})
              elsif special == 'circle'
                  polygon = Polygon.from_coordinates(coords)
                  polygons.push(polygon)
                  filters.push(Proc.new {|track|
                      track_in_polygon?(polygon, track)})
                  #filters.push(Proc.new {|track|
                  #    track_in_circle?(center, radius, track)})
              end
          end

          min_time, max_time = params[:min_time].to_i, params[:max_time].to_i
          polygons.zip(filters).each do |polygon, filter|
              raw_tracks = getTracksInSelection(polygon, min_time, max_time)
              ids += raw_tracks.select {|t| filter.call(t.track)}
          end
      elsif params[:ids]
          ids = params[:ids].map {|id| Cruise.find(id) }
      elsif params[:q]
          ids = find_cruises(params[:q])[0]
      end

      # Build JSON response with id: track
      id_track = {}
      ids.each do |c|
        id_track[c.id] = nil
        if c.respond_to?('track') and c.track
          id_track[c.id] = c.id
        end
      end

      response = {
        "id_t" => id_track,
        "i" => _info(id_track.keys),
        "t" => _track(id_track.keys)
      }

      render :json => response
  end

  def layer
      # Provides a mirror for KML/NAV files that need to be loaded from a web site.
      # Returns: text
      #     path to the mirrored file
      dirname = 'map_mirror'
      dir = File.join(RAILS_ROOT, 'public', dirname)
      Dir.mkdir(dir) unless File.directory? dir
      now = Time.now.to_i
      Dir.foreach(dir) do |file|
          if file !~ /\./ and file.to_i < now - 60
              File.unlink(File.join(dir, file))
          end
      end
      filename = File.join(dir, now.to_s)
      f = File.new(filename, 'w')
      input = params[:file]
      input.each_line {|line| f.write line }
      f.flush.close
      json = "<textarea>" +
        "{\"url\":\"" + 
        File.join(dirname, File.basename(filename)) + 
        "\"}" +
        "</textarea>"
      render :text => json
  end

  private

  def _max_coords
    params[:max_coords] || $DEFAULT[:max_coords].to_i()
  end

  def _track(ids)
    max_coords = _max_coords()
    ids.inject({}) do |h, k|
        c = Cruise.find(k)
        if t = c.track
          h[k] = pareDown(t, max_coords).map {|p| [p.x, p.y]}
        end
        h
    end
  end

  def _info(ids)
      infos = {}
      ids.each do |id|
          if c = Cruise.find(id)
              # CCHDO
              infos[id] = {
                :name => c.ExpoCode || '',
                :programs => c.Line || '',
                :contacts => c.Chief_Scientist || '',
                :ship => c.Ship_Name || '',
                :cruise_dates => [c.Begin_Date, c.EndDate].join('/') || '',
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
          end
      end
      infos
  end

  private

  def getTracksInSelection(selection, min_time=nil, max_time=nil)
      min_time = min_time || $DEFAULT[:min_time]
      # Bump the year forward because we want searches up to Jan 1 00:00 year + 1
      max_time = (max_time || $DEFAULT[:max_time]) + 1
      return Cruise.find_by_sql([[
          # CCHDO
          "SELECT DISTINCT cruises.id,cruises.ExpoCode,Track as track FROM cruises JOIN track_lines ",
          "ON cruises.ExpoCode = track_lines.ExpoCode WHERE ",
          "EndDate > '?' AND Begin_Date < '?' AND ",

          # SEAHUNT
          #"SELECT DISTINCT id,track FROM cruises WHERE ",
          #"realdate_start > '?' AND realdate_start < '?' AND ",

          # MySQL
           "Intersects(GeomFromText(",
           "\"LINESTRING#{selection.text_representation}\"),track)"
          # PostgresQL
          #"Intersects(track,", "GeomFromText(\"#{selection.as_wkt}\"))"
      ].join(''), min_time, max_time])
  end

  def pareDown(coords, max=50)
      #     - max: a maximum number of coordinates in the track to
      #         return. The coordinates will be thinned out but the first and
      #         last will remain.
      step_size = [coords.length / [max, 1].max, 1].max
      pared = []
      (0...coords.length).step(step_size) {|index| pared << coords[index]}
      return pared
  end

  def between_lat (lower, test, upper)
      return (lower...upper).include?(test)
  end

  def between_lng (lower, test, upper)
      if lower > upper # crossed the date-line
        return (lower...180).include?(test) || (-180...upper).include?(test)
      end
      return (lower...upper).include?(test)
  end

  def track_in_rectangle?(rect, track)
      sw, ne = rect.points[0], rect.points[2]
      return track.any? do |coord|
        between_lng(sw.x, coord.lng, ne.x) and between_lat(sw.y, coord.lat, ne.y)
      end
  end

  def track_in_circle?(center, radius, track)
      return track.any? do |coord|
        (1...radius).include?(
          center.ellipsoidal_distance(coord) / 1000)
      end
  end

  def track_in_polygon?(polygon, track)
      def in_polygon?(poly, pt)
          len = poly.length
          j = len - 1
          c = false
          (0..len - 1).each do |i|
              v1 = poly[i]
              v2 = poly[j]
              if ((v1.y > pt.y) != (v2.y > pt.y)) and
                 (pt.x < (v2.x - v1.x) * (pt.y - v1.y) / (v2.y - v1.y) + v1.x)
                  c = !c
              end
              j = i
          end
          return c
      end
      # Our polygons are only single ringed. GeoRuby has multi-ringed polygons so
      # take the first one.
      return track.any? {|coordinate| in_polygon?(polygon[0], coordinate)}
  end

  def track_in_any_loci? (loci, radius, track)
      return loci.any? {|center| track_in_circle?(center, radius, track)}
  end
end
