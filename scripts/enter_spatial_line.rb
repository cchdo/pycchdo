RAILS_ENV = 'production'
require File.dirname(__FILE__) + '/../config/environment'
  
require '/usr/local/cchdo/cchdo_hydro_lib.rb'
#require 'find'


unless ARGV[0] 
  puts "Please enter a file with coordinates in columns (Lat, Lon)."
  coord_file = gets()
else
  coord_file = ARGV[0] or raise "Please include a file with coordinates"
end
file_obj = File.open(coord_file) or raise "Couldn't open #{file}"
coordinates = file_obj.read

puts "Please enter an ExpoCode:"
expocode = STDIN.gets().chomp
@coordinates = String.new
@point_array = []
# Create a TrackLine object and save it in track_lines
for coordinate in coordinates#_with_station_cast_code
  (lat,lon) = coordinate.split
  if lat and lon
    @point_array << Point.from_x_y(lon.to_f,lat.to_f )
  end
end
trackline = TrackLine.new(:ExpoCode => "#{expocode}",:Track => LineString.from_points(@point_array),:Basins => "Default")
if trackline
  begin
    trackline.save
    puts "saved #{coord_file}"
  rescue
    puts "Couldn't save #{coord_file}"
  end
end