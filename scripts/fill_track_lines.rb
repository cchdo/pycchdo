RAILS_ENV = 'production'
require File.dirname(__FILE__) + '/../config/environment'
  
require '/usr/local/cchdo/cchdo_hydro_lib.rb'
require 'find'

entry_ctr = 0
Find.find("/data") do |cur_path| # For each file, recursively through the directory tree
  @cruise_object = nil
  if cur_path !~ /original/ and cur_path !~ /tmp/
    if FileTest.directory? cur_path
      files = `ls #{cur_path}`.split
      if files.include?("ExpoCode")
        if    file = files.detect { |e|  e =~ /su\.txt/ }
          if FileTest.file?("#{cur_path}/#{file}") 
               begin 
                 @cruise_object = WoceSum.new("#{cur_path}/#{file}") 
               rescue => error
                 puts error
               end
          end
        elsif file = files.detect { |e|  e =~ /hy1\.csv$/ }
          #puts "Data available for: #{cur_path}/#{file}"
          #if FileTest.file?("#{cur_path}/#{file}") then @cruise_object = ExchangeBotComplete.new("#{cur_path}/#{file}") end
        elsif file = files.detect { |e|  e =~ /ct1\.zip/ }
          #puts "Data available for: #{cur_path}/#{file}"
          #if FileTest.file?("#{cur_path}/#{file}") then @cruise_object = CTDZip.new("#{cur_path}/#{file}") end
        else
          puts "No file with coordinates found for #{cur_path}"
        end      
      end#if files.include?("ExpoCode")
    end#if FileTest.directory? cur_path
  end # if cur_path !~ /original/ and cur_path !~ /tmp/
    
  if @cruise_object
    if @cruise_object.type == 'Sum'
      @coordinates = String.new
      if @cruise_object.coordinates
        @point_array = []
        expocode = @cruise_object.expocodes[0]
      # Create a TrackLine object and save it in track_lines
        for coordinate in @cruise_object.coordinates#_with_station_cast_code
          (lat,lon) = coordinate.split
          if lat and lon
            @point_array << Point.from_x_y(lon.to_f,lat.to_f )
          end
          entry_ctr += 1
        end
        trackline = TrackLine.new(:ExpoCode => "#{expocode}",:Track => LineString.from_points(@point_array),:Basins => "Default")
        if trackline
          begin
            trackline.save
            puts "saved #{@cruise_object.file_name}"
          rescue
            puts "Couldn't save #{@cruise_object.file_name}"
          end
        end
      end
      #bounds = get_bounds_from_string(@coordinates)
      #if Station.find(:first,:conditions => ["`ExpoCode` = '#{expocode}'"])
      #  raise "Cruise Track already exists."
      #end

      #track_entry.Basin = bounds['basin']
      #track_entry.Track = @coordinates
      #track_entry.save!
      #puts @cruise_object.coordinates
    end # if @cruise_object.type == 'Sum'
  end # if @cruise_object

end #Find.find("/data") do |cur_path|
puts "#{entry_ctr} Total Entries"