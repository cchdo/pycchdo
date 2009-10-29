class Staff::StaffController < ApplicationController
   layout "staff"
   before_filter :check_authentication, :except => [:signin, :images]

   def signin
      if session[:user] # Already signed in
         redirect_to :controller => '/staff'
      end
      if request.post?
         if user = User.authenticate(params[:username],params[:password])
            session[:user] = user.id
            session[:username] = params[:username]
            session[:intended_action] = '' if session[:intended_action] == 'signin'
            redirect_to :controller => session[:intended_controller], :action => session[:intended_action]
         else
            flash[:notice] = "Username password pair not authorized. Please try again."
         end
      end
   end

   def signout
      session[:user] = nil
      session[:intended_action] = 'signin'
      session[:intended_controller] = '/staff'
      redirect_to :controller => "/staff", :action => "signin"
   end

   def index
      @user = User.find(session[:user]).username
      params[:query] = @user
      #search_assignments
      @assignments = Assignment.find(:all, :conditions => ["`cchdo_contact` regexp ?", @user])
   end

   def recent_updates
   end

   def create
      @user = User.find(session[:user]).username
      @assignment = Assignment.create(params[:assignment])
      @assignments = Assignment.find(:all, :conditions => { :ExpoCode => @assignment.ExpoCode })
      @query = @assignment.ExpoCode
      render :partial => "assignments"
   end

   def cruise_entry
      @cruise = Cruise.new
      @parameter_codes = Code.find(:all, :order => "Code").map {|u| [u.Code, u.Status]}
   end

   def create_cruise
      @cruise = Cruise.new(params[:cruise])
      @cruise.save
      @cruises = Cruise.find(:all, :conditions => { :ExpoCode => @cruise.ExpoCode })
      @param_list = Parameter.column_names.reject {|name| name =~ /ExpoCode/ or name =~ /id/ or name =~ /_PI/}
      @new_parameter = Parameter.new(:ExpoCode => @cruise.ExpoCode)
      params.each_key do |param|
         if @param_list.include?(param)
            @new_parameter[:"#{param}"] = 0
            @new_parameter[:"#{param}_PI"] = params[:"#{param}"]
         end
      end
      @new_parameter.save
      render :partial => "cruises"
   end

   def assignment_list
      @user = User.find(session[:user]).username
   end

   def search_assignments
      @cols=[]
      @results=[]
      @cur_max = 0
      @dir=[]
      @text

      @user = User.find(session[:user]).username
      @sort = params[:Sort] || 'priority'

      #Past Due code
      if params[:commit] =~ /ave/
         Assignment.update(params[:assignment].keys, params[:assignment].values)
         @assignments = Assignment.find(:all, :conditions => ["`cchdo_contact` REGEXP ?", @user], :order => [@sort])
         #render :partial => "assignments"
      elsif(params[:New])
         #render :partial => "new_assignment"
      else
         @assignments = Assignment.find(:all, :conditions => ["`cchdo_contact` REGEXP ?", @user], :order => [@sort])
      end
      render :partial => "user_tasks"
   end

   def csv_dump
      CSV::Writer.generate(output="") do |task_file|
         task_file << ['ID', 'ExpoCode','Project', 'CurrentStatus','AssignedTo','DataContact', 'Action','Parameter', 'Priority', 'Deadline','LastChanged', 'Notes','History']
         Assignment.find(:all).each do |task|
            task_file << [task.id, task.ExpoCode, task.project, task.current_status,  task.cchdo_contact, task.data_contact, task.action, task.parameter, task.priority, task.deadline, task.changed, task.notes, task.history]
         end
      end
      open('/Users/Shared/cchdo2/public/submissions/tasks.csv', "w") do |file|
         output.each do |p|
            file.puts p
         end
      end
      send_data(output,:type => "text/csv",:filename => "Tasks.csv")
   end

   def past_due
      render :action => "assignment_list"
   end

   def show_note
      @note_id = params[:sub_id]
      @submission_note = Submission.find(@note_id)
      @submission_note[:notes].gsub!(/[\n]/,"<br>")
      @submission_note[:notes].gsub!(/[\t]/,"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")
      render :partial => "show_note"
   end

   def hide_note
      @note_id = params[:sub_id]
      @submission = Submission.find(@note_id)
      render :partial => "hide_note"
   end

   def submissions
      @user = User.find(session[:user]).username
      @submissions = Submission.find(:all, :order => "submission_date DESC")
   end

   def submission_list
      #If a submission has been assigned, update the assignment table
      if params[:assignment]
         @user = User.find(session[:user]).username
         @assignment = Assignment.create(params[:assignment])
         @submission = Submission.find(params[:submission_id])
         @submission.assigned = true
         @submission.save
         params[:submission_list] = 'all'
      end

      condition = params[:submission_list]
      @parameters = params
      if condition == 'all'
         @submissions = Submission.find(:all,:order => "submission_date DESC")
      elsif condition == 'unassigned'
         @submissions = Submission.find(:all, :conditions => ["assigned = '0'"],:order => "submission_date DESC")
      elsif condition == 'unassimilated'
         @submissions = Submission.find(:all, :conditions => ["assimilated = '0'"],:order => "submission_date DESC")
      end
      render :partial => "submission_list"
   end

   def assign_submission
      @user = User.find(session[:user]).username
      @sub_id = params[:sub_id]
      @submission = Submission.find(params[:sub_id])
      render :partial => "assign_submission"
   end

   def update_parameters

   end

end
