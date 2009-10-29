RAILS_ENV = 'production'
require File.dirname(__FILE__) + '/../config/environment'
  
  
  def track_coords_in(expocode)
    # Returns an array of track coordinates for given expocode.
    track_coords = Array.new
    if track = Track.find(:first, :conditions => { :ExpoCode => expocode})
      coords = track.Track.split(/\n/)
      coords.each_index do |coord_i|
        if coord_i % 10 == 0
          track_coords << coords[coord_i]
        end
      end
    end
    return track_coords
  end
  
   def create_basin(points)
    @basin = Basin.new()
    nw = Point.from_x_y(-55.067, -65.4)
    ne = Point.from_x_y(-77.233,  -65.4)
    se = Point.from_x_y(-73.117,  42.933)
    sw = Point.from_x_y(-55.067, 42.933)
    #ww = Point.from_x_y(-55.067, -13.917)
    #ee = Point.from_x_y(-55.067, -65.4)
    #ep = Point.from_x_y(-47.45, -68.867)
    #e2 = Point.from_x_y(-55.067, 46.933)
    #e3 = Point.from_x_y(-12.25, 42.933)
    #e4 = Point.from_x_y(65.383, -24.633)
    
    
    poly = Polygon.from_points([[nw, ne, se, sw, nw]])
    @basin.Description = poly
    @basin.Name = "South South Atlantic"
    #@basin.save
    @sql_result = Basin.find_by_sql("select Within(GeomFromText('POINT(26 15)'),GeomFromText(\"Polygon((60 20,60 0,20 0,20 20,60 20))\") ) AS Name;")
    @column_hash = Basin.columns_hash
    
    @map = GMap.new("map_div")
    @map.control_init(:large_map => true,:map_type => true)
    @map.center_zoom_init([75.5,-42.56],4)
  end
  
  def create_track_line(expocode)
    @track_array = Array.new
    track = Track.find(:first,:conditions => ["ExpoCode = '#{expocode}'"])
    @track_array = track.Track.split("\n")
    @point_array = Array.new
    for pair in @track_array
      (lat, lon) = pair.split
      puts "#{lat} #{lon}"
      if lat and lon
        @point_array << Point.from_x_y(lat.to_f,lon.to_f )
      end
    end
    for point in @point_array
      puts "#{point.class} #{point}"
    end
    ##### Code for creating and saving a TrackLine object
    tline = TrackLine.new(:ExpoCode => "#{track.ExpoCode}",:Track => LineString.from_points(@point_array),:Basins => "Default")
    tline.save
    return tline
  end
  
  def get_track_line(expocode)
    if trackline = TrackLine.find(:first,:conditions => ["ExpoCode = '#{expocode}'"])
      puts "#{trackline.inspect}  <-- INSPECTION!!"
      return trackline
    else
      return nil
    end
  end
  
    expocode = "3230CITHER2_1"
    @track = track_coords_in(expocode)
    
    #tline = create_track_line(expocode)
    tline = get_track_line(expocode)
    for point in tline.Track
      puts "#{point.x}---#{point.y}"
    end
#    puts "TLine: #{tline.class}  #{tline.inspect}"
    @map = Variable.new("map")
    @points = []
    @results = []
    @contained = ""
    # Get Basin info
    @basin  = Basin.find(:first,:conditions => ["Name = 'North West South Atlantic'"])
    poly = @basin.Description

    rings = poly.rings
    for ring in rings 
        for coord in ring
          @points << "#{coord.x} #{coord.y}"
        end
    end
    for coord in @track
      @sql_result = Basin.find_by_sql("select Within(GeomFromText('POINT(#{coord})'),GeomFromText(\"Polygon((#{@points.join(',')}))\") ) AS Name;")
      if @sql_result[0].Name
        if @sql_result[0].Name == '1'
          @contained = "#{expocode} is in #{@basin.Name}"
        end
        @results << @sql_result[0].Name
      else
        @results << 0
      end
      (x,y) = coord.split()
      @track_array << [x,y]
    end
    @track = GPolyline.new(@track_array,"#ff0000",3,1.0)
    #render :partial => "track_info"
    #puts @track.class
    #puts "Track #{@track.inspect}" 
    #puts "------------------------------------------"
    #puts "#{@track.points}"