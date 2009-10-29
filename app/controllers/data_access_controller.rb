class DataAccessController < ApplicationController
   layout 'standard', :except => ['autocomplete_arrays']

   def index
      if params[:commit] =~ /Cruises/
         list_cruises
         render :action => 'list_cruises'
      elsif params[:commit] =~ /Files/
         list_files
         render :action => 'list_files'
      elsif params[:ExpoCode]
         show_cruise
         render :action => 'show_cruise'
      else
         redirect_to :controller => 'search', :action => 'advanced'
      end
   end

   class ExpoDate
      attr_reader :expo,:date
      def initialize(expo,date)
         @expo = expo
         @date = date
      end
   end

   def show_cruise
      unless params[:commit] =~ /Cruises/ or params[:commit] =~ /Files/
         expocode = params[:ExpoCode]
         if @cruise = Cruise.find(:first, :conditions => { :ExpoCode => expocode })
            # This section isn't used at all in views?
            #if groups = @cruise.Group.split(',')
            #   @cruise_groups = groups.collect {|group| Cruise.find(:all, :conditions => ["`Group` REGEXP ?", group]) }
            #end
            chief_scientists_to_links! @cruise.Chief_Scientist
            @file_hash = Document.file_hash_for expocode
         end
      end
   end

   def list_cruises
      # Build SQL query
      search_expression = []
      ignored_keys = ['commit', 'YEARSTART', 'MONTHSTART', 'YEAREND', 'MONTHEND', 'post', 'action', 'controller']
      params.each_pair do |key, value|
         unless ignored_keys.include? key and key !~ /Type/ and value =~ /\w/
            term = "#{key} REGEXP '#{value}'"
            search_expression << term
         end
      end
      if params[:YEARSTART] and params[:YEAREND] and params[:MONTHSTART] and params[:MONTHEND]
         begin_date = "#{params[:YEARSTART]}-#{params[:MONTHSTART]}-00"
         end_date   = "#{params[:YEAREND]}-#{params[:MONTHEND]}-00"
         term = "Begin_Date > '#{begin_date}' AND Begin_Date < '#{end_date}'"
         search_expression << term
      end
      search_expression = search_expression.join(' AND ')
      unless search_expression.empty?
         @cruises = Cruise.find_by_sql("SELECT DISTINCT * FROM cruises WHERE #{search_expression} ORDER BY Begin_Date")
         @cruises.map {|cruise| chief_scientists_to_links! cruise.Chief_Scientist}
         @file_hashes = Document.files_for_cruises @cruises
      end
   end

   def list_files
      if params[:FileType] =~ /\w/
         file_type = params[:FileType]
         @expos = Array.new(0)
         @changed_sets = Hash.new{|@changed_sets,key| @changed_sets[key]={}}
         @expo_dates = Array.new
         @begin_date = "#{params[:YEARSTART]}-#{params[:MONTHSTART]}-00"
         case file_type
            when /all/ then @file_expression = "(FileType regexp 'Sum' or FileType regexp 'Bottle' or FileType regexp 'CTD' or FileType regexp 'Documentation') and (documents.ExpoCode = cruises.ExpoCode)"
            when /bottle/  then @file_expression = "(FileType regexp 'Bottle' and cruises.ExpoCode = documents.ExpoCode)"
            when /sum/  then @file_expression = "(FileType regexp 'Sum' and cruises.ExpoCode = documents.ExpoCode)"
            when /ctd/  then @file_expression = "(FileType regexp 'CTD' and cruises.ExpoCode = documents.ExpoCode)"
            when /documentation/  then @file_expression = "(FileType regexp 'Documentation' and cruises.ExpoCode = documents.ExpoCode)"
         end
         if @file_expression
            @file_expression << " AND documents.LastModified > \"#{@begin_date}\""
            @files = Document.find_by_sql("SELECT DISTINCT documents.FileName,documents.ExpoCode,documents.LastModified,cruises.Line,cruises.Ship_Name,cruises.Country,cruises.Begin_Date,cruises.EndDate FROM cruises,documents WHERE #{@file_expression}") # no user input->no injection
            file_path = Array.new
            for file in @files

               unless @expos.include? file.ExpoCode
                  @expos << file.ExpoCode
                  @changed_sets[file.ExpoCode]["Files"] = String.new
                  @changed_sets[file.ExpoCode]["EarliestDate"] = Time.now
               end
               #file_path = file.FileName.split(/\//)
               #file.FileName = file_path[file_path.length-1]
               cur_date = nil
               case file.FileName
               when /su.txt$/ then @changed_sets[file.ExpoCode]['woce_sum'] = file.FileName
                  @changed_sets[file.ExpoCode]['woce_sum_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /ct.zip/  then @changed_sets[file.ExpoCode]['woce_ctd'] = file.FileName
                  @changed_sets[file.ExpoCode]['woce_ctd_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /hy.txt/  then @changed_sets[file.ExpoCode]['woce_bot'] = file.FileName
                  @changed_sets[file.ExpoCode]['woce_bot_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /lv.txt/  then @changed_sets[file.ExpoCode]['large_volume'] = file.FileName
                  @changed_sets[file.ExpoCode]['large_volume_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /lvs.txt/  then @changed_sets[file.ExpoCode]['large_volume'] = file.FileName
                  @changed_sets[file.ExpoCode]['large_volume_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /hy1.csv/ then @changed_sets[file.ExpoCode]['exchange_bot'] = file.FileName
                  @changed_sets[file.ExpoCode]['exchange_bot_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /ct1.zip/ then @changed_sets[file.ExpoCode]['exchange_ctd'] = file.FileName
                  @changed_sets[file.ExpoCode]['exchange_ctd_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /ctd.zip/ then @changed_sets[file.ExpoCode]['netcdf_ctd'] = file.FileName
                  @changed_sets[file.ExpoCode]['netcdf_ctd_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /hyd.zip/ then @changed_sets[file.ExpoCode]['netcdf_bot'] = file.FileName
                  @changed_sets[file.ExpoCode]['netcdf_bot_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /do.txt/  then @changed_sets[file.ExpoCode]['text_doc'] = file.FileName
                  @changed_sets[file.ExpoCode]['text_doc_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /do.pdf/  then @changed_sets[file.ExpoCode]['pdf_doc'] = file.FileName
                  @changed_sets[file.ExpoCode]['pdf_doc_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /.gif/    then @changed_sets[file.ExpoCode]['small_pic'] = file.FileName
                  @changed_sets[file.ExpoCode]['small_pic_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               when /.jpg/    then @changed_sets[file.ExpoCode]['big_pic'] = file.FileName
                  @changed_sets[file.ExpoCode]['big_pic_date'] = file.LastModified
                  cur_date = file.LastModified.to_s
               end
               if cur_date
                  file_time = Time.parse(cur_date)
                  if file_time <  @changed_sets[file.ExpoCode]['EarliestDate']
                     @changed_sets[file.ExpoCode]['EarliestDate'] = file_time
                  end
               end
               #@changed_sets[file.ExpoCode]["Files"] << "#{file.FileName}, "
               @changed_sets[file.ExpoCode]["Line"]  = file.Line
               @changed_sets[file.ExpoCode]["Country"] = file.Country
               @changed_sets[file.ExpoCode]["Ship_Name"] = file.Ship_Name
               @changed_sets[file.ExpoCode]["Begin_Date"] = file.Begin_Date
               @changed_sets[file.ExpoCode]["End_Date"] = file.EndDate
               #@changed_sets[file.ExpoCode]["LastModified"] = file.LastModified

            end # for file in @files
            @expos.uniq!
         end # if(@file_expression)

         if @expos and @changed_sets
            for expo in @expos
               temp_exp = ExpoDate.new(expo,@changed_sets[expo]['EarliestDate'])
               @expo_dates << temp_exp
            end
            @expo_dates.sort!{|a,b| date_sort(a.date,b.date)}
         end

      end #if params[:FileType] =~ /\w/
   end

   def date_sort(a,b)
      if a < b
         ret_val = -1
      elsif a > b
         ret_val = 1
      else
         ret_val = 0
      end
      return ret_val
   end

   def autocomplete_arrays
      pis, expocodes, ships, countries = [], [], [], []
      Cruise.find(:all).each do |cruise|
         pis << cruise.Chief_Scientist
         expocodes << cruise.ExpoCode
         ships << cruise.Ship_Name
         countries << cruise.Country
      end
      pis.uniq!
      expocodes.uniq!
      ships.uniq!
      countries.uniq!

      pistr = pis.join '","'
      expostr = expocodes.join '","'
      shipstr = ships.join '","'
      countrystr = countries.join '","'

      render :text => 'pis=["'+pistr+'"];expocodes=["'+expostr+'"];ships=["'+shipstr+'"];countries=["'+countrystr+'"];', :headers => {'Content-Type' => 'text/javascript'}
   end

end
