class Staff::DpoTasksController < Staff::TaskManagerController
   layout 'staff'
   before_filter :check_authentication

   def index
   end

   def search_assignments
      @cols = []
      @names = []
      @results = []
      @cur_max = 0
      @dir = []
      @text

      @user = User.find(session[:user]).username
      @query = params[:query]
      if @show_completed = params[:complete]
         completed_string = ''
      else
         if @query == "all"
            completed_string = "`complete` = '0'"
         else
            completed_string = "AND `complete` = '0'"
         end
      end
      @sort = params[:Sort] || "priority"

      #Past Due code

      if params[:commit] =~ /(s?ave|update)/
         @assignments = []
         DpoAssignment.update(params[:assignment].keys, params[:assignment].values)
         if params[:commit] =~ /update/
            for param in params.keys
               if param =~ /(snooze)/
                  (trash, @assignment_id) = param.split('_')
                  @assignment = DpoAssignment.find(@assignment_id)
                  @new_deadline = nil
                  case params[:"#{param}"]
                  when /(1 week)/:   @new_deadline = (Time.now + (60*60*24*7)).strftime("%Y-%m-%d")
                  when /(2 weeks)/:  @new_deadline = (Time.now + (60*60*24*14)).strftime("%Y-%m-%d")
                  when /(1 month)/:  @new_deadline = (Time.now + (60*60*24*30)).strftime("%Y-%m-%d")
                  when /(3 months)/: @new_deadline = (Time.now + (60*60*24*90)).strftime("%Y-%m-%d")
                  end
                  if @new_deadline
                     @assignment.deadline = @new_deadline
                     @assignment.save
                  end
                  #@val = @assignment_deadline
               end
            end
         end
         if @query
            if @query.eql?("all")
              if completed_string =~ /complete/
                 @assignments = DpoAssignment.find(:all, :conditions => ["#{completed_string}"], :order => [@sort])
              else
                 @assignments = DpoAssignment.find(:all, :order => [@sort])
              end
            else
              for column in DpoAssignment.columns
                 @names << column.human_name
                 unless (column.name.eql? "history" or column.name.eql? "manager")
                    @results = DpoAssignment.find(:all, :conditions => ["`#{column.name}` regexp '#{@query}' #{completed_string}"], :order => [@sort])
                    if @results.length > @cur_max
                       @cur_max = @results.length
                       @best_result = []
                       @assignments = @results
                       @results=[]
                    end
                 end
              end
            end
         end
         render :partial => "assignments"
      elsif(params[:New]) # If not saving or updating, and creating a new entry
         render :partial => "new_assignment"
      else                # If we're just reordering
         if (params[:query])
            @best_result = []
            @assignments = []
            if @query.eql?("all")
               if completed_string =~ /complete/
                  @assignments = DpoAssignment.find(:all,:conditions => ["#{completed_string}"],:order=>["#{@sort}"])
               else
                  @assignments = DpoAssignment.find(:all,:order=>["#{@sort}"])
               end
            else
               for column in DpoAssignment.columns
                  @names << column.human_name
                  unless (column.name.eql? "history" or column.name.eql? "manager")
                     @results = DpoAssignment.find(:all ,:conditions => ["`#{column.name}` regexp '#{@query}' #{completed_string}"],:order=>["#{@sort}"])
                     if @results.length > @cur_max
                        @cur_max = @results.length
                        @best_result = []
                        @assignments = @results
                        @results=[]
                     end
                  end
               end # for column in DpoAssignment.columns
            end # if @query.eql?("all") .. else .. end
         else
            if completed_string =~ /complete/
               @assignments = DpoAssignment.find(:all,:conditions => ["`complete` = '0'"],:order=>["#{@sort}"])
            else
               @assignments = DpoAssignment.find(:all, :order=>["#{@sort}"])
            end
         end # if (params[:query]) .. else .. end
         render :partial => "assignments"
      end #  if(params[:commit] =~ /ave/ or params[:commit] =~ /update/) .. elsif(params[:New]) .. else
    end

    # Override unwanted methods
    undef manager_v
end
