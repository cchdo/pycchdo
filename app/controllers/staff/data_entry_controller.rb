STAFF = {
   'danie' =>'Danie Kincade',
   'sdiggs' => 'Steve Diggs',
   'jkappa' => 'Jerry Kappa',
   'dave'   => 'Dave Muuse',
   'sarilee' => 'Sarilee Anderson',
   'jfields' => 'Justin Fields'
}
STATUS = {
   'Proposed' => '5',
   'On_Line' => '1',
   'Submitted' => '3',
   'Not_Measured' => '4',
   'No_Information' => '6',
   'Reformatted' => '2'
}

NUMSTATUS = {
   '5' => 'Proposed',
   '1' => 'On_Line',
   '3' => 'Submitted',
   '4' => 'Not_Measured',
   '6'=> 'No_Information',
   '2'=> 'Reformatted'
}

class Staff::DataEntryController < ApplicationController
   layout "staff"
   before_filter :check_authentication

   def index
      @user = User.find(session[:user])
      @user = @user.username
      @update_radio = " "
      @create_radio = "checked"
      #render :action => 'cruise_entry'
   end

   def cruise_entry
      #@cruise = Cruise.new
      @update_radio = " "
      @create_radio = "checked"
      @parameter_codes = Code.find(:all,:order => "Code").map {|u| [u.Code, u.Status]}
      render :partial => "cruise_entry"
   end

   def event_entry
      @user = User.find(session[:user])
      @user = @user.username
      user = STAFF[@user]
      (first, last) = user.split(' ')
      @event = Event.new

      render :partial => "event_entry"
   end

   def find_name
      if params[:LastName]
         #@event.First_Name = first
         @last_name = params[:LastName]
         if @tmp_event = Contact.find(:first, :conditions => {:LastName => @last_name})
            @first_name = @tmp_event.FirstName
            @event = Event.new

            @event.First_Name = @first_name
            @event.LastName = @last_name
         end
      end
     render :partial => "event_names"
   end

   def contact_entry
      render :partial => "contact_entry"
   end

   def parameter_entry
      @p_list = []
      @other_column_names = []
      @groups = ParameterGroup.find_by_sql("SELECT DISTINCT `group`,`parameters` FROM parameter_groups")
      for group in @groups
         g_list = group.parameters
         for g_param in (g_list.split(/,/))
            @p_list << g_param
         end
      end
      @column_names = Parameter.column_names
      for col in @column_names
         unless @p_list.include?(col)
            @other_column_names << col
         end
      end
      if params[:ExpoCode] =~ /\w/
         @expo = ""
         if @parameter = Parameter.find(:first, :conditions => {:ExpoCode  => params[:ExpoCode]})
            @expo = params[:ExpoCode]
         end
      end
      render :partial => "parameter_entry"
   end

   def submit_parameter
      @p_list = []
      @other_column_names = []
      @groups = ParameterGroup.find_by_sql("SELECT DISTINCT `group`,`parameters` FROM parameter_groups")
      for group in @groups
         g_list = group.parameters
         for g_param in (g_list.split(/,/))
            @p_list << g_param
         end
      end
      @column_names = Parameter.column_names
      for col in @column_names
         unless @p_list.include?(col)
            @other_column_names << col
         end
      end
      @parameter = Parameter.new
      if params[:parameter]
         @par = Hash.new
         @par_temp = params[:parameter]
         @expo = params[:parameter][:ExpoCode]
         for key in (@par_temp.keys) do
            if key =~ /NO3$/
               good_key = "NO2+NO3"
               @par[good_key] = @par_temp[key]
            elsif key =~/NO3_(.*)/
               good_key = "NO2+NO3_#{$1}"
               @par[good_key] = @par_temp[key]
            else
               @par[key] = @par_temp[key]
            end
         end
         #Parameter.update(@par.keys,@par.values)
         if @parameter = Parameter.find(:first, :conditions => {:ExpoCode  => @expo})
            @parameter.attributes = @par
            @parameter.save!
         end
      end
      render :partial => "parameter_entry"
   end

   # create_cruise takes the information from the _cruise_entry.rhtml partial and processes it.
   # If the cruise entry is valid, it's created and saved.  If it's not valid, error messages are
   # passed back to the _cruise_entry.rhtml page.
   def create_cruise
      @parameter_codes = Code.find(:all, :order => 'Code').map {|u| [u.Code, u.Status]}
      @message = ""
      @notice = "nothing"
      @param_list = Parameter.column_names.reject {|name| name =~ /ExpoCode/ or name =~ /id/ or name =~ /_PI/ or name =~ /_Date/i}
      saved = nil

      # holds entered parameters when a cruise entry needs to be re-entered
      @form_parameters = Hash.new 

      if params[:cruise]
         if params[:entry_type] =~ /Update/  # If we're editing an existing cruise
         ############################################################################################################
         ###                                              U P D A T E                                             ###
            @update_radio = "checked"
            @create_radio = " "
            @cruise = Cruise.find(:first, :conditions => {:ExpoCode => params[:cruise][:ExpoCode]})
            parameters = Parameter.find(:first, :conditions => {:ExpoCode => params[:cruise][:ExpoCode]})

            if params[:cruise][:ExpoCode] =~ /\w/
              if params[:cruise][:Line] !~ /\w/ # If we're pulling cruise info, Prepare to edit an existing cruise
                @message = "Updating #{params[:cruise][:ExpoCode]}  #{params[:cruise][:Line]}"
              else # Check that the values have changed, then save changes
                params.keys.each do |param|
                  if @param_list.include?(param) and params[:"#{param}_status"] =~ /\w/
                     @stat_test = params[:"#{param}_status"]
                     @stat = STATUS[@stat_test]
                     parameters[:"#{param}"] = @stat
                     parameters[:"#{param}_PI"] = params[:"#{param}"]
                     @form_parameters["#{param}"] = @stat_test
                     @form_parameters["#{param}_PI"] = params[:"#{param}"]

                     if params[:"#{param}_year"] =~ /\d/ and params[:"#{param}_month"] =~ /\d/ and params[:"#{param}_day"] =~ /\d/
                        day = params[:"#{param}_day"]
                        month = params[:"#{param}_month"]
                        year = params[:"#{param}_year"]
                        parameters[:"#{param}_Date"] = "#{year}-#{month}-#{day}"
                        @form_parameters["#{param}_year"] = year
                        @form_parameters["#{param}_month"] = month
                        @form_parameters["#{param}_day"] = day
                        if param =~ /CTD/i
                           @notice = "#{year}-#{month}-#{day}"
                        end
                     end
                  end
                end
                @message = "<strong>#{params[:cruise][:ExpoCode]}</strong> Updated<br /><br />"
                parameters.update
                parameters = Parameter.find(:first, :conditions => {:ExpoCode => params[:cruise][:ExpoCode]})
              end
            end
            @param_list.each do |col|
              if parameters[:"#{col}"]
                 @form_parameters["#{col}_year"] = ""
                 @form_parameters["#{col}_month"] = ""
                 @form_parameters["#{col}_day"] = ""
                 if parameters[:"#{col}_Date"]
                    year,month,day = parameters[:"#{col}_Date"].strftime("%Y-%m-%d").split("-")
                    @form_parameters["#{col}_year"] = year
                    @form_parameters["#{col}_month"] = month
                    @form_parameters["#{col}_day"] = day
                 end
                 param_state = parameters[:"#{col}"]
                 @form_parameters["#{col}"] = NUMSTATUS[param_state] #@parameter_codes[parameters[:"#{col}"].to_i]
                 @form_parameters["#{col}_PI"] = parameters[:"#{col}_PI"]
              end
            end
            render :partial => 'cruise_entry'
            ###                            E N D   U P D A T E                           ###
            ################################################################################
         elsif params[:entry_type] =~ /Create/
         ################################################################################
         ###                               C R E A T E                                ###
            if params[:cruise][:ExpoCode] =~ /\w/
               expo = params[:cruise][:ExpoCode]
               @update_radio = ' '
               @create_radio = "checked"

               if @existing_cruise = Cruise.find(:first, :conditions => {:ExpoCode => expo})
                  @message = "<strong>Cruise Exists</strong><br />Please enter a unique ExpoCode<br />"
                  render :partial => "cruise_entry"
               else
                  @cruise = Cruise.new(params[:cruise])

                  # Check that the new cruise object is valid
                  @new_parameter = Parameter.find(:first, :conditions => {:ExpoCode => params[:cruise][:ExpoCode]}) || Parameter.new
                  for param in params.keys do
                    if @param_list.include?(param)
                       if params[:"#{param}_status"] =~ /\w/
                          @stat_test = params[:"#{param}_status"]
                          @stat = STATUS[@stat_test]
                          @new_parameter[:"#{param}"] = @stat
                          @new_parameter[:"#{param}_PI"] = params[:"#{param}_PI"]
                          @form_parameters["#{param}"] = @stat_test
                          @form_parameters["#{param}_PI"] = params[:"#{param}_PI"]

                          if params[:"#{param}_year"] =~ /\d/ and params[:"#{param}_month"] =~ /\d/ and params[:"#{param}_day"] =~ /\d/
                             day = params[:"#{param}_day"]
                             month = params[:"#{param}_month"]
                             year = params[:"#{param}_year"]
                             @new_parameter[:"#{param}_Date"] = "#{year}-#{month}-#{day}"
                             @form_parameters["#{param}_year"] = year
                             @form_parameters["#{param}_month"] = month
                             @form_parameters["#{param}_day"] = day
                             #@form_parameters["#{param}_Date"] = "#{year}-#{month}-#{day}"
                          end
                       end
                    end
                  end

                  begin
                    Cruise.transaction do
                       @cruise.Country.strip!
                       @cruise.ExpoCode.strip!
                       saved = @cruise.save!
                    end
                  rescue ActiveRecord::RecordInvalid => e
                    render :partial => "cruise_entry"
                  end

                  if saved
                     @new_parameter.ExpoCode = @cruise.ExpoCode
                     @parameters = params
                     @new_parameter.save
                     @theta_status = params[:THETA_status]
                     @message = "#{@cruise.ExpoCode} row created in the cruises table"
                     render :partial => "cruise_entry"
                  end
               end
            end
         end
         #                                        E N D   C R E A T E                                         #
         ######################################################################################################
      else
         render :partial => "cruise_entry"
      end
   end

   def create_event
     if params[:event]
       @event = Event.new(params[:event])
       #@event.Date_Entered = Time.now.strftime("%Y-%m-%d")
       @event.save
       if @expo = @event.ExpoCode
         @events = Event.find(:all, :conditions => {:ExpoCode => @expo}, :order => ['Date_Entered DESC'])
         @cruise = Cruise.find(:first, :conditions => {:ExpoCode => @expo})
       end
       render :partial => "display_events"
     end
   end

   def display_events
     @expo = params[:ExpoCode]
     @cur_sort = params[:Sort]
     #@updated = Event.find_by_sql("SELECT * FROM events ORDER BY Date_Entered DESC LIMIT 1")
     @updated = [Event.find(:first, :order => 'Date_Entered DESC')]
     if @expo
       order_by = 'Date_Entered DESC'
       if order_by =~ /(LastName|Data_Type)/
         order_by = @cur_sort
       end
       @events = Event.find(:all, :conditions => {:ExpoCode => @expo}, :order => [order_by])
       @cruise = Cruise.find(:first, :conditions => {:ExpoCode => @expo})
     end
     if @note
       @note_entry = Event.find(:first, :conditions => {:ID => params[:Entry]})
     end
     render :partial => "display_events"
   end

   def note
      @entry = params[:Entry]
      @note_entry = Event.find(:first, :conditions => {:ID => @entry})
      render :partial => "note"
   end

   def find_contact_entry
      if params[:LastName]
         @contact = Contact.find(:first, :conditions => {:LastName => params[:LastName]})
      end
      render :partial => 'contact_entry'
   end

   def create_contact
      render :partial => 'contact_entry'
   end

   def update_parameters
   end
end
