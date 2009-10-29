require 'csv'
class Staff::TaskManagerController < ApplicationController
   layout 'staff'
   before_filter :check_authentication

   def index
      @user = User.find(session[:user]).username
      @assignments = Assignment.all(:order=>["priority"])
   end

   def search_assignments
      @cols = []
      @names = []
      @results = []
      @cur_max = 0
      @dir = []
      @text
      @user = nil
      if user = User.find(session[:user])
        user.username
      end
      @query = params[:query]
      @hide_completed_checked = false
      @hide_completed = params[:complete]
      @hide_coworkers = params[:coworkers]
      @query = "all" unless @query =~ /\w/
      completed_string = ""
      
      if @hide_completed =~ /1/
        @hide_completed_checked = true
         if @query.eql?("all")
           completed_string = "`priority` != 6"
         else
           completed_string = " AND `priority` != 6"
         end
      end
      if @hide_coworkers =~ /1/
        @hide_coworkers_checked = true
        if (@query.eql?("all")) and (@hide_completed !~ /1/)
          completed_string = "`cchdo_contact` = '#{@user}'"
        else
          completed_string << " AND `cchdo_contact` = '#{@user}'"
        end
      end
      if(params[:Sort])
         @sort = params[:Sort]
      else
         @sort = "priority"
      end
      #If the user saves changes
      if(params[:commit] =~ /ave/)# or params[:commit] =~ /update/)
         @assignments = []
         # Save all changes
         Assignment.update(params[:assignment].keys, params[:assignment].values)  
         #if params[:commit] =~ /update/
         #  for param in params.keys
         #       if param =~ /(snooze)/
         #          (trash,@assignment_id) = param.split('_')
        #          @assignment = Assignment.find(@assignment_id)
        #          @new_deadline = nil
        #          #@assignment_deadline = Assignment.find_by_sql("SELECT UNIX_TIMESTAMP(deadline) from assignments where id = '#{assignment_id}'")
        #          case params[:"#{param}"]
        ##          when /(1 week)/:   @new_deadline = (Time.now + (60*60*24*7)).strftime("%Y-%m-%d")
        #          when /(2 weeks)/:  @new_deadline = (Time.now + (60*60*24*14)).strftime("%Y-%m-%d")
        #          when /(1 month)/:  @new_deadline = (Time.now + (60*60*24*30)).strftime("%Y-%m-%d")
        #          when /(3 months)/: @new_deadline = (Time.now + (60*60*24*90)).strftime("%Y-%m-%d")
        #          end
        #          if @new_deadline
        #             @assignment.deadline = @new_deadline
        #             @assignment.save
        #          end
        #          #@val = @assignment_deadline
        #       end
        #    end
        # end
         if @query
            if @query.eql?("all")
               if completed_string =~ /(priority)|(cchdo_contact)/
                  @assignments = Assignment.find(:all,:conditions => ["#{completed_string}"],:order=>["#{@sort}"])
               else
                  @assignments = Assignment.find(:all,:order=>["#{@sort}"])
               end
            else
               for column in Assignment.columns
                  @names << column.human_name
                  unless (column.name.eql? "history" or column.name.eql? "manager")
                     @results = Assignment.find(:all ,:conditions => ["`#{column.name}` regexp '#{@query}' #{completed_string}"],:order=>["#{@sort}"])
                     if @results.length > @cur_max
                        @cur_max = @results.length
                        @best_result = []
                        @assignments = @results
                        @results=[]
                     end
                  end
               end
            end # if @query.eql("all") , else,
         end # if @query
         render :partial => "assignments"
      elsif(params[:New]) # If not saving or updating, and creating a new entry
         render :partial => "new_assignment"
      else                # If we're just reordering
         if (params[:query])
            @best_result = []
            @assignments = []
            if @query.eql?("all")
               if completed_string =~ /(priority)|(cchdo_contact)/
                  @assignments = Assignment.find(:all,:conditions => ["#{completed_string}"],:order=>["#{@sort}"])
               else
                  @assignments = Assignment.find(:all,:order=>["#{@sort}"])
               end
            else
               for column in Assignment.columns
                  @names << column.human_name
                  unless (column.name.eql? "history" or column.name.eql? "manager")
                     @results = Assignment.find(:all ,:conditions => ["`#{column.name}` regexp '#{@query}' #{completed_string}"],:order=>["#{@sort}"])
                     if @results.length > @cur_max
                        @cur_max = @results.length
                        @best_result = []
                        @assignments = @results
                        @results=[]
                     end
                  end
               end # for column in Assignment.columns
            end # if @query.eql?("all") .. else .. end
         else
            if completed_string =~ /(priority)|(cchdo_contact)/
               @assignments = Assignment.find(:all,:conditions => ["`priority` != 6"],:order=>["#{@sort}"])
            else
               @assignments = Assignment.find(:all,:order=>["#{@sort}"])
            end
         end # if (params[:query]) .. else .. end
         render :partial => "assignments"
      end #  if(params[:commit] =~ /ave/ or params[:commit] =~ /update/) .. elsif(params[:New]) .. else
   end

   def manager_v
     @workers = User.find(:all)
     @assignments = Assignment.find(:all)
     render :partial => "manager_view"
   end

   def csv_dump
      @cols = []
      @names = []
      @results = []
      @cur_max = 0
      @dir = []
      @text

      @query = params[:query]
      @hide_completed = params[:complete]
      if @hide_completed
         completed_string = ""
      else
         if @query.eql?("all")
            completed_string = "`priority` != 6"
         else
            completed_string = "AND `priority` = 6"
         end
      end
      if @query.eql?("all")
         if completed_string =~ /priority/
            @assignments = Assignment.find(:all,:conditions => ["#{completed_string}"])
         else
            @assignments = Assignment.find(:all)
         end
      else
         for column in Assignment.columns
            @names << column.human_name
            unless (column.name.eql? "history" or column.name.eql? "manager" or column.name.eql? "id" or column.name.eql? "complete")
               @results = Assignment.find(:all ,:conditions => ["`#{column.name}` regexp '#{@query}' #{completed_string}"])
               if @results.length > @cur_max
                  @cur_max = @results.length
                  @best_result = []
                  @assignments = @results
                  @results=[]
               end
            end
         end
      end
      if @assignments
         report = StringIO.new
         CSV::Writer.generate(report, ',') do |csv|
            csv << ['ExpoCode','Project', 'CurrentStatus','AssignedTo','DataContact', 'Action','Parameter', 'Priority', 'Deadline','LastChanged', 'Notes','History']
            @assignments.each do |task|
               csv << [task.ExpoCode, task.project, task.current_status,  task.cchdo_contact, task.data_contact, task.action, task.parameter, task.priority, task.deadline, task.changed, task.notes, task.history]
            end
         end
         report.rewind
         send_data(report.read,:type => 'text/csv; charset=iso-8859-1; header=present',:filename => 'report.csv')
         #send_file("/Users/Shared/cchdo_cchdo/public/whp_atlas/pacific_index.html",:type => 'text',:stream => "false",:disposition => 'attachment')
      end
   end

   def past_due
      render :action => "index"
   end

   def create
      @user = User.find(session[:user])
      @user = @user.username
      @assignment = Assignment.create(params[:assignment])
      @assignments = Assignment.find(:all,:conditions =>["ExpoCode = '#{@assignment.ExpoCode}'"])
      @query = @assignment.ExpoCode
      render :partial => "assignments"
   end

   def toggle
      @toggle_div = params[:id]
   end

   def hide_task
     @assignment_id = params[:task_id]
     @assignment_obj = Assignment.find(@assignment_id)
     @assignment_obj[:visible] = 0
     @assignment_obj.save!
     @assignments = Assignment.find(:all,:order=>["priority"])
     render :partial => "assignments"
   end

end
