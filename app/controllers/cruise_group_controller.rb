class CruiseGroupController < ApplicationController
  
  def index
     @group = params[:id] || 'Atlantic Onetime'
     make_lists
  end
  
  def show_cruise
    @cruise = Cruise.find(params[:id])
    render :partial => 'show_cruise'
  end
  
  def show_group
    @group = params[:group]
    make_lists
    render :partial => 'show_group'
  end
  
private
  def make_lists
    @table_list = Hash.new{|@table_list,k| @table_list[k]={}}
    @pi_list = Hash.new{|h,k| h[k]={}}
    @param_list = Hash.new{|h,k| h[k]={}}

    @codes = Hash.new
    Code.find(:all).each {|code| @codes[code.Code] = code.Status}

    @cruises = Cruise.find(:all, :conditions => ["`Group` REGEXP ?", @group])
    @cruises.each do |cruise|
      if cruise.ExpoCode =~ /\w/

         @table_list[cruise.ExpoCode]['woce_sum'] = String.new
         @table_list[cruise.ExpoCode] = Document.file_hash_for(cruise.ExpoCode)

         @param_list[cruise.ExpoCode]['stations'] = 0
         @param_list[cruise.ExpoCode]['parameters']= ""
         if cruise_parameters = BottleDB.find(:first, :conditions => {:ExpoCode => cruise.ExpoCode})
            @param_list[cruise.ExpoCode]['stations'] = cruise_parameters.Stations
            if cruise_parameters.Parameters =~ /\w/
              param_list = cruise_parameters.Parameters
              param_persistance = cruise_parameters.Parameter_Persistance
              @param_list[cruise.ExpoCode]['parameters'] = param_list
              param_array = param_list.split(',')
              persistance_array = param_persistance.split(',')
              (1..param_array.length).each do |ctr|
                @param_list[cruise.ExpoCode][param_array[ctr].to_s] = persistance_array[ctr]
              end
            end
         end
      end
    end
  end
end
