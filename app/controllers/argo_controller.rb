class ArgoController < ApplicationController
   before_filter :check_authentication

   def index
     @files = file_user_ids_to_strs(ArgoSubmission.find(:all, :conditions => {:display => 1}))
   end

   def save_file
     if params[:file] and not params[:file].kind_of? String
       file_name = params[:file].original_filename.gsub(/[^\w\.\-]/,'_')
       submission_info = {
         :user => session[:user] || 1, # default to admin
         :ExpoCode => 'Unknown',
         :filename => file_name,
         :location => "argo_submissions/#{file_name}",
         :datetime_added => Time.now
       }
       @file_submission = ArgoSubmission.new(params[:argo_submission].merge(submission_info))
       @file_submission.save!
       File.open("#{RAILS_ROOT}/public/argo_submissions/#{file_name}", "wb") do |f|
         f.write(params[:file].read)
       end
     end
     index and render :action => 'index'
   end

   def delete
     @user = User.find(session[:user])
     if params[:file]
       begin
         if submission = ArgoSubmission.find(params[:file]) and submission.user.to_i == @user.id
           ArgoSubmission.delete(submission)
           `rm #{RAILS_ROOT}/public/#{submission.location}`
           flash[:notice] = "Deleted file #{submission.filename}"
         end
       rescue ActiveRecord::RecordNotFound
       end
     end
     @files = file_user_ids_to_strs(ArgoSubmission.find(:all, :conditions => ['user = ?', session[:user]]))
   end

   protected
   
   def file_user_ids_to_strs(files)
     begin
       files.each {|file| file.user = User.find(file.user).username } unless files.blank?
     rescue ActiveRecord::RecordNotFound
       
     end
   end
end
