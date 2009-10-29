class GeoDataController < ApplicationController
  layout "geo_map", :except => [:update_map, :map_select, :cruise_table]
  def index
    @basin  = Basin.find(:first,:conditions => ["Name = 'North West South Atlantic'"])
    @map = GMap.new("map_div")
    @map.control_init(:large_map => true,:map_type => true)
    @map.center_zoom_init([75.5,-42.56],4)
    

    
  end
  
  def track_info
    expocode = params[:cruise][:ExpoCode]
    @track = track_coords_in(expocode)
    @track_array = Array.new()
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
    trackline = TrackLine.find(:first,:conditions => ["ExpoCode = '#{expocode}'"])
    if trackline
      @track_result = "track line - #{trackline.inspect}"
      @track = GPolyline.from_georuby(trackline.Track, "#ff0000",3,1.0)
    else
      @track_result = "Old way"
       @track = GPolyline.new(@track_array,"#ff0000",3,1.0)
    end
    #render :partial => "track_info"
  end
  
  def show_basin
     # Make js that puts the cruise table in and updates the map
     @basin_name = params[:Basin]
     @basin  = Basin.find(:first,:conditions => ["Name = '#{@basin_name}'"])
     @map = Variable.new("map")
     
     nw = Point.from_x_y(-48.167,-0.633 )
     ne = Point.from_x_y(-19.917,-0.633 )
     se = Point.from_x_y(-16.917,-0.633 )
     sw = Point.from_x_y(-16.917,-30.15 )
     ww = Point.from_x_y(-49.65,-30.15 ) 
     ee = Point.from_x_y(-48.167,-0.633 )

     poly = @basin.Description#Polygon.from_points([[nw, ne, se, sw,ww, nw]])
     #poly = switch_x_y_polygon(poly)
     envelope = Envelope.from_coordinates( [poly.bounding_box])
     @polygon = GPolygon.from_georuby(poly,"#000000",0,0.0,"#ff0000",0.6)
     #@center = GLatLng.from_georuby(envelope.center)
     #@zoom = @map.get_bounds_zoom_level(GLatLngBounds.from_georuby(envelope))
     
  end
 def show_basin_with_tracks
   @tracks = []
   # Make js that puts the cruise table in and updates the map
   @basin_name = params[:Basin]
   @tracklines = TrackLine.find(:all, :conditions => ["`Basins` REGEXP '#{@basin_name}'"])
   for track in @tracklines
     @track = GPolyline.from_georuby(track.Track, "#ff0000",3,1.0)
     @tracks << @track
   end
   @basin  = Basin.find(:first,:conditions => ["Name = '#{@basin_name}'"])
   @map = Variable.new("map")
   poly = @basin.Description
   envelope = Envelope.from_coordinates( [poly.bounding_box])
   @polygon = GPolygon.from_georuby(poly,"#000000",0,0.0,"#ff0000",0.6)
   
 end
end
