class SearchController < ApplicationController

  def index
    # If the user used q and there is no query, grab it.
    if params[:q]
      params[:query] ||= params[:q]
      params.delete :q
    end

    @skip = (params[:skip] || '0').to_i
    @limit = (params[:limit] || '10').to_i

    # reformat the param hash into a string
    saved_query = params[:query] || ''

    ignored_keys = ['commit', 'action', 'controller', 'query.x', 'query.y', 'query', 'limit', 'skip']
    ignored_keys.each {|key| params.delete(key)}

    params.delete_if {|key, value| value.empty?}
    params[:query] = saved_query + params.to_a.collect {|pair| pair.join(':')}.join(' ')

    unless params[:query].blank?
      @cruises, best_queries, @num_results = find_cruises(params[:query], @skip, @limit, true)

      if @cruises
        @recognized = best_queries || {}
        @scientists = Hash.new
        if @recognized.include? 'Chief_Scientist'
          @recognized.each_pair do |type, query|
            if type == 'Chief_Scientist'
              @scientists[query] = Contact.find(:first, :conditions => {:LastName => query})
            end
          end
        end

        # Used for the maps
        @large_maps = Hash.new
        @small_maps = Hash.new

        # Used to generate num stations and parameter summary
        @num_stations = Hash.new
        @parameter_list_htmls = Hash.new

        # Used to generate file summary table
        @cruise_files = Hash.new {|h, k| h[k] = Hash.new}

        @cruises.each do |cruise|
          chief_scientists_to_links!(cruise.Chief_Scientist ||= '')
          cruise.Begin_Date ||= Date.parse('0000-01-01')
          cruise.EndDate ||= Date.parse('0000-01-01')
          cruise.Alias ||= ''

          maps = Document.find(:all, :select => "FileName,FileType", :conditions => {:ExpoCode => cruise.ExpoCode, :FileType => ['Large Plot', 'Small Plot']})
          if maps and maps.length == 2
            maps.each do |map|
              if map.FileType == 'Large Plot'
                @large_maps[cruise] = map.FileName
              else
                @small_maps[cruise] = map.FileName
              end
            end
          end

          cruise.Alias = cruise.Alias.split(',').collect {|a| "<a href='/search?alias=\"#{a}\"'>#{a}</a>"}.join(', ')

          if cruise_parameters = BottleDB.find(:first, :select => "Stations,Parameters,Parameter_Persistance", :conditions => {:ExpoCode => cruise.ExpoCode})
             @num_stations[cruise] = cruise_parameters.Stations
             cruise_params = Hash.new

             parameter_persistence_pairs = Hash.new

             # make parameter persistence hash
             if parameter_list = cruise_parameters.Parameters.split(',') and persistence_list = cruise_parameters.Parameter_Persistance.split(',')
               parameter_list.each_index {|index| parameter_persistence_pairs[parameter_list[index]] = persistence_list[index]}
               ignored_parameters = [/castno/i, /flag/i, /time/i, /expocode/i, /sampno/i, /sectid/i, /depth/i, /latitude/i, /longitude/i, /stnnbr/i, /btlnbr/i, /sect_id/i, /date/i, /^$/]
               ignored_parameters.each do |ignore|
                  parameter_persistence_pairs.delete_if{|param, persist| param =~ ignore}
               end
             end
             
             parameter_links = []
             parameter_persistence_pairs.each_pair do |parameter, persistence|
               link = "<a href='/search?query=\"#{parameter}\"'>#{parameter}"
               if persistence.to_i < 10
                 link << '*'
               end
               parameter_links << link + '</a>'
             end
             @parameter_list_htmls[cruise] = parameter_links.join(' ')
          end

          # Make file list for generating the check boxes

          # Get min file age first
          min_file_age = '1970-00-00'
          if params[:query] =~ /\bfile.?year.?start\:\s?(\w{4})\b/i
            params[:file_year_start] = $1
          end
          if params[:query] =~ /\bfile.?month.?start\:\s?(\w{1,2})\b/i
            params[:file_month_start] = $1
          end
          if params[:file_year_start] and params[:file_month_start]
            min_file_age = "#{sprintf("%04u", params[:file_year_start])}-#{sprintf("%02u", params[:file_month_start])}-00"
          end

          file_hash = Hash.new
          Document.find(:all, :select => "*", :conditions => ["ExpoCode=? AND LastModified > ?", cruise.ExpoCode, min_file_age]).each do |file|
            file_hash[file.FileType] = file
          end

          if params[:query] =~ /\bFileType\:\s?(\w+)\b/i
            params[:FileType] ||= $1
          end
          case params[:FileType]
            when /woce/i          then @no_exchange=@no_netcdf=true
            when /exchange/i      then @no_woce=@no_netcdf=true
            when /netcdf/i        then @no_woce=@no_exchange=true
          end
          case params[:FileType]
            when /all/i           then nil
            when /bottle/i        then @no_ctd=@no_documentation=@no_large_volume=@no_sum=true
            when /sum/i           then @no_bottle=@no_ctd=@no_documentation=@no_large_volume=true
            when /ctd/i           then @no_bottle=@no_documentation=@no_large_volume=@no_sum=true
            when /documentation/i then @no_bottle=@no_ctd=@no_large_volume=@no_sum=true
          end
          file_hash.delete_if {|type, file| type =~ /woce/i} if @no_woce
          file_hash.delete_if {|type, file| type =~ /exchange/i} if @no_exchange
          file_hash.delete_if {|type, file| type =~ /netcdf/i} if @no_netcdf
          file_hash.delete_if {|type, file| type =~ /Bottle/i} if @no_bottle
          file_hash.delete_if {|type, file| type =~ /CTD/i} if @no_ctd
          file_hash.delete_if {|type, file| type =~ /Documentation/i} if @no_documentation
          file_hash.delete_if {|type, file| type =~ /Volume/i} if @no_large_volume
          file_hash.delete_if {|type, file| type =~ /Sum/i} if @no_sum

          if file_hash.empty?
            # Remove the listing if advanced result
            if params[:commit] == 'Search'
              @cruises.delete(cruise)
            end
          else
            @cruise_files[cruise] = file_hash
          end
        end
      end
    end
  end

  def advanced
    # If a query has been submitted do the request, else display advanced form
    if params[:commit]
      index
      render :action => 'index'
    end
  end

end
