class Staff::CruiseStatusController < ApplicationController
  layout 'staff'

  before_filter :check_authentication
  #cache_sweeper :task_tracker

  def index
    redirect_to :controller => '/cruise_status', :action => 'cruise_information'
  end

  def cruise_information
     @cruises = organize_cruises_by_group
     (@no_files_cruises, @some_files_cruises) = flag_cruises
     get_data_history(params[:Note], params[:entry], params[:Sort])
     get_cruise_doc_files_for_expo(params[:expo])
  end

  def note
     @entry = params[:Entry]
     @note_entry = Event.find(:first, :conditions => ['ID = ?', @entry])
     render :partial => "note"
  end

  def all_cruise_meta
     get_data_history(params[:Note], params[:entry], params[:Sort])
     get_cruise_doc_files_for_expo (params[:expo])
     render :partial => "all_cruise_meta"
  end

  def organize_cruises_by_group
     @cruises_by_group = Hash.new{|@cruises_by_group,key| @cruises_by_group[key]=[]}
     if @cruise_list = Cruise.find(:all)
       @cruise_list.each do |cruise|
         if groups = cruise.Group and groups =~ /\w/
           group = groups.split(',').first
           if group.empty?
             group = 'No_Group'
           end
           @cruises_by_group[group] << cruise
         end
       end
     end
     return @cruises_by_group
  end

  def flag_cruises
    file_counts = {}
    file_types_expected = ['Woce Sum', 'Woce CTD (Zipped)', 'Woce Bottle', 'Exchange Bottle', 'Exchange CTD (Zipped)', 'NetCDF CTD', 'NetCDF Bottle', 'Documentation', 'PDF Documentation', 'Large Plot', 'Small Plot', 'Large Volume file']
    
    # count the number of expected files for each cruise
    where_clause = file_types_expected.collect {|type| "FileType='#{type}'"}.join(' OR ')
    cruise_files = Document.find(:all, :conditions => [where_clause]) # no user input->no injections
    cruise_files.each do |file|
      file_counts[file.ExpoCode] ||= 0
      if type = file.FileType and file_types_expected.include? type
        file_counts[file.ExpoCode] += 1
      end
    end

    # filter the cruise counts for medium and serious omissions
    cruises_missing_all = Array.new
    cruises_missing_some = Array.new
    file_counts.each_pair do |expocode, count|
      if count <= 0
        cruises_missing_all << expocode 
      elsif count <= 10
        cruises_missing_some << expocode
      end
    end

    # add in cruises that weren't in the documents table at all
    cruises = Cruise.find(:all, :select => 'DISTINCT ExpoCode').collect {|cruise| cruise.ExpoCode}.compact
    cruises_missing_all += (cruises - file_counts.keys)
    return cruises_missing_all, cruises_missing_some
  end

private
  def get_cruise_doc_files_for_expo (expocode)
    if expocode
      @cruise = Cruise.find(:first, :conditions => {:ExpoCode => expocode})
    else
      @cruise = Cruise.find(:first)
    end
    @doc = Document.find(:first, :conditions => ["FileType = 'Directory' AND ExpoCode = ?", expocode])
    @file_result = file_obj_hash_for(expocode)
  end

  def get_data_history (note, entry, cur_sort)
    @note = note
    @entry = entry
    @cur_sort = cur_sort
    if @cur_sort != "LastName" and @cur_sort != "Data_Type"
      @cur_sort = 'Date_Entered DESC'
    end
    @events = Event.find(:all, :conditions => {:ExpoCode => params[:expo]}, :order => [@cur_sort])
    if @note
       @note_entry = Event.find(:first, :conditions => {:ID => @entry})
    end
  end

  def file_obj_hash_for (expocode)
    file_objs = Document.find(:all, :conditions => {:ExpoCode => expocode})
    key_type_hash = {'woce_sum' => 'Woce Sum',
                     'woce_ctd' => 'Woce CTD (Zipped)',
                     'woce_bot' => 'Woce Bottle',
                     'exchange_bot' => 'Exchange Bottle',
                     'exchange_ctd' => 'Exchange CTD (Zipped)',
                     'netcdf_ctd' => 'NetCDF CTD',
                     'netcdf_bot' => 'NetCDF Bottle',
                     'text_doc' => 'Documentation',
                     'pdf_doc' => 'PDF Documentation',
                     'big_pic' => 'Large Plot',
                     'small_pic' => 'Small Plot',
                     'large_volume' => 'Large Volume file'}

    file_results = Hash.new
    key_type_hash.each_pair do |key, type|
      file_results[key] = file_objs.select {|x| x.FileType == type }.first
    end
    return file_results
  end
end
