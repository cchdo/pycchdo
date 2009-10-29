class SubmitController < ApplicationController
   upload_status_for :save_file

   def index

   end

   def save_file
      $save_dir = "#{RAILS_ROOT}/public/submissions"

      #unless(params[:file] =~ /\w/ or params[:saved])
      # render :action => 'index'
      #end
      SUBMITLOG.info "-------------------------------------- New Submission ---------------------------------------------"
      SUBMITLOG.info "#{Time.now}"
      if(params[:submission][:file])
         saved = nil
         @file_info = "early"
         @file = params[:submission][:file]
         @file_class = @file.class.to_s
         @file_stuff = params[:submission][:file]
         #@file_info_name = @file.original_filename
         SUBMITLOG.info "Submission file: \n\tFile: #{@file}\n\tClass: #{@file_class}"
         unless @file.class.to_s.eql?("String") #=~ /\w/
            @file_name = @file.original_filename
            @file_name.gsub!(/[^\w\.\-]/,'_')
            @file_name.gsub!(/\s/,'_') #@filename.tr!('\s', '_')
            if @file_name !~ /\w/
               render :action => :index
            end
            file_type = @file.content_type
            @file_info = $save_dir
            SUBMITLOG.info "\tFile name: #{@file.original_filename} => #{@file_name}\n\tFile type: #{file_type}\nAttempting to write to #{$save_dir}/#{@file_name}"
            File.open("#{$save_dir}/#{@file_name}", "wb") do |f|
               f.write(params[:submission][:file].read)
            end
            SUBMITLOG.info 'Write complete.'
         end
      end
      if(params[:submission][:file] or params[:saved])
         @file_name ||= params[:saved]
         SUBMITLOG.info "Submission file or saved. Filename: #{@filename}"
         @submission = Submission.new(params[:submission])
         @submission.file = @file_name
         if params[:actions][:one] =~ /[a-z]/
            @submission.action = params[:actions][:one]
         end
         if params[:actions][:two] =~ /[a-z]/
            if @submission.action =~ /[a-z]/
               @submission.action = "#{@submission.action}, #{params[:actions][:two]}"
            else
               @submission.action = params[:actions][:two]
            end
         end
         if params[:actions][:three] =~ /[a-z]/
            if @submission.action =~ /[a-z]/
               @submission.action = "#{@submission.action}, #{params[:actions][:three]}"
            else
               @submission.action = params[:actions][:three]
            end
         end
         @submission.action ||= " "
         SUBMITLOG.info "Submission action: #{@submission.action}"
         @submission.assigned = false
         @submission.assimilated = false
         @submission.submission_date = Time.now
         SUBMITLOG.info "Beginning submission save"
         begin
            Submission.transaction do
               @submission_status = "Tried"
               cleaned_name = @submission.name.gsub(/^\w\.\-/, '_')
               new_dir = Time.now.strftime("%Y%m%d_%I_%M") + "_#{cleaned_name}"
               #@directory_name = "/Users/Shared/cchdo_watershed/public/submissions/#{new_dir}"
               @directory_name = "/Library/Webserver/Documents/cchdo/public/submissions/#{new_dir}"
               @submission.file = "#{@directory_name}/#{@file_name}"
               @submission.institute.strip!
               @submission.Country.strip!
               SUBMITLOG.info "Saving in #{@directory_name} as #{@file_name}\n\tInstitute: #{@submission.institute}\n\tCountry: #{@submission.Country}"
               saved = @submission.save!
               SUBMITLOG.info "Save status: #{saved}"
            end
         rescue ActiveRecord::RecordInvalid => e
            render :action => :index
         end
         @date = "#{@submission.cruise_date}"
         if saved
            SUBMITLOG.info "Actually writing files"
            # directory_creation_result = File.makedirs @directory_name
            `mkdir #{@directory_name}`
            `mv #{$save_dir}/#{@file_name} #{@directory_name}/#{@file_name}`
            SUBMITLOG.info "done."
            FileSubmitted.deliver_confirm(@submission)
         end
      end # if(params[:submission][:file] or params[:saved])
   end

end
