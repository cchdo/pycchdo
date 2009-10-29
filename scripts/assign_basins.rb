RAILS_ENV = 'production'
require File.dirname(__FILE__) + '/../config/environment'

Basins = [
  'Central West North Atlantic',
  'North West North Atlantic',
  'North East North Atlantic',
  'Central East North Atlantic',
  'South West North Atlantic',
  'South North Atlantic',
  'South East North Atlantic',
  'North West South Atlantic',
  'North East South Atlantic',
  'Central West South Atlantic',
  'South South Atlantic',
  'South East South Pacific',
  'South West South Pacific',
  'West North Pacific',
  'North North Pacific',
  'Central North Pacific',
  'East North Pacific',
  'West South Pacific',
  'Central South Pacific',
  'East South Pacific'
]

@tracklines = TrackLine.find(:all)
for track in @tracklines
   puts track.ExpoCode
   for basin_title in Basins
     @basin  = Basin.find(:first,:conditions => ["Name = '#{basin_title}'"])
      poly = @basin.Description
     @points = []
      rings = poly.rings
      for ring in rings 
          for coord in ring
            @points << "#{coord.x} #{coord.y}"
          end
      end
      text_track = track.Track.as_ewkt(allow_srid=false)
      #puts "Text Track:#{text_track}"
      @sql_result = Basin.find_by_sql("select Intersects(GeomFromText('#{text_track}'),GeomFromText(\"Polygon((#{@points.join(',')}))\") ) AS Name;")
      #puts @sql_result.inspect
      if @sql_result[0].Name
        if @sql_result[0].Name == '1'
          puts "#{track.ExpoCode} is in #{@basin.Name}"
          if track.Basins =~ /\w/
            track.Basins = "#{track.Basins},#{@basin.Name}"
          else
            track.Basins = "#{@basin.Name}"
          end
          track.save
        end
      end
    end
end