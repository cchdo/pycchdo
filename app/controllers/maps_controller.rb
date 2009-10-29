BASIN_ORDER = ['North Atlantic','Central Atlantic','South Atlantic','East Pacific','South West Pacific', 'West Pacific','Indian','Southern']
BASIN_COORDS = {
   'north atlantic' => '49 -25',
   'central atlantic' => '15 -28',
   'south atlantic' => '-25 -10',
   'east pacific' => '-4 155',
   'south west pacific' => '-30 160',
   'west pacific' => '20 150',
   'indian' => '-34 80',
   'southern' => '-65 50'
}
BASIN_ZOOM = {
   'north atlantic' => '3',
   'central atlantic' => '3',
   'south atlantic' => '3',
   'east pacific' => '1',
   'south west pacific' => '3',
   'west pacific' => '3',
   'indian' => '2',
   'southern' => '2'
}
class MapsController < ApplicationController

  def index
     if(params[:basin])
        @basin = params[:basin]
     else
        @basin = "indian"
     end
     get_tracks
     #render :action => "get_tracks"
  end


  def line_sort(a,b)
     complete_a = complete_b = 1
     if(a =~ /^([a-z]+)([0-9]+)/i)
        a_basin = $1
        @a_number = $2
     else
        complete_a = nil
     end
     if(b =~ /^([a-z]+)([0-9]+)/i)
        b_basin = $1
        @b_number = $2
     else
        complete_b = nil
     end
     if( complete_a and complete_b)
        @a = a_basin.split('')
        @b = b_basin.split('')
        if(@a.length == @b.length)
           if(@a_number.to_i < @b_number.to_i)
              ret_val = -1
           elsif(@b_number.to_i < @a_number.to_i)
              ret_val = 1
           else
              ret_val = 0
           end
        else
           if(@a.length > @b.length)
              ret_val = 1
           elsif(@b.length > @a.length)
              ret_val = -1
           else
              ret_val = 0
           end
        end
     else
        ret_val = 0
     end
     return (ret_val)
  end

  def get_tracks
     @lines = Track.find(:all, :conditions=>["`Basin` = '#{@basin}'"])
     @tracks = Hash.new
     @temp_tracks = Hash.new
     @expos = []
     for line in @lines
        @expos << Cruise.find(:first, :conditions => ["`ExpoCode` = '#{line.ExpoCode}'"])
        @temp_tracks[line.ExpoCode] = Array.new
        @tracks[line.ExpoCode] = Array.new
        @temp_tracks[line.ExpoCode] = line.Track.split(/\n/)
        ctr = 10
        for coord in @temp_tracks[line.ExpoCode]
           if ctr % 10 == 0
              @tracks[line.ExpoCode] << coord
           end
           ctr = ctr+1
        end
     end
     @expos.compact!
     bad_line = nil
     if @basin.eql?("East Pacific")
        bad_line = @expos.include? nil
     end
     unless bad_line
        @expos.sort!{|a,b| line_sort(a.Line,b.Line)}
     end
  end
end
