class FileBoxController < ApplicationController
   before_filter :check_authentication

   def index
      @user = FileBoxUser.find(session[:user])
      @sections = FileBoxSection.find(:all)
   end

   def admin_page
      @users = FileBoxUser.find(:all)
      group_list = FileBoxGroup.find(:first)
      @groups = group_list.groups.split(',')
      @sections = FileBoxSection.find(:all)
      render :partial => "admin_page"
   end

   def new_user
      @users = FileBoxUser.find(:all)
      @new = 1
      @file_box_user = FileBoxUser.new
      render :partial => "users_menu"
   end

   def create_user
      @new = nil
      if params[:commit]
         @new_user = FileBoxUser.new(params[:file_box_user])
         @new_user.save!
      end
      @users = FileBoxUser.find(:all)
      render :partial => "users_menu"
   end

   def new_section
      @sections = FileBoxSection.find(:all)
      @new = 1
      @file_box_section = FileBoxSection.new
      render :partial => "sections_menu"
   end

   def create_section
      @new = nil
      if params[:commit]
         @new_section = FileBoxSection.new(params[:file_box_section])
         @new_section.save!
      end
      @sections = FileBoxSection.find(:all)
      render :partial => "sections_menu"
   end
   
   def draw_usage_graph

#
#     g = Gruff::Line.new
#     g.title = "My Graph"
#
#
#     g.data("Apples", [1, 2, 3, 4, 4, 3])
#     g.data("Oranges", [4, 8, 7, 9, 8, 9])
#     g.data("Watermelon", [2, 3, 1, 5, 6, 8])
#     g.data("Peaches", [9, 9, 10, 8, 7, 9])
#
#
#     g.labels = {0 => '2003', 2 => '2004', 4 => '2005'}
#
#
#     filename = '/Users/Shared/cchdo_watershed/public/my_fruity_graph.png'
#
#
#     # this writes the file to the hard drive for caching
#     # and then writes it to the screen.
#     #
#
#
#     g.write(filename)

     #send_data(g.to_blob, 
     #         :disposition => 'inline', 
     #           :type => 'image/png', 
     #          :filename => "#{filename}")
     render :text => "Some text"
   end
   
   def show_section
      if params[:group]
         @group = params[:group]
         @files = FileBoxFile.find(:all)
      else
         @group = "No Section - Error"
      end
      render :partial => "section_files"
   end

   def save_file
      $save_dir = "/Users/Shared/cchdo_watershed/public/file_box"
      #$save_dir = "/Library/WebServer/Documents/cchdo/public/submissions"
      #$save_dir = "/Users/jfields/Job/cchdo_waterbowl/public/file_box"
      #/Users/Shared/cchdo_watershed/public/submissions
      #unless(params[:file] =~ /\w/ or params[:saved])
      # render :action => 'index'
      #end
      if params[:group]
         @group = params[:group]
      else
         @group = "No Section - Error"
      end
      if(params[:incoming_file])
         @file_box_file = "GOT something"
         saved = nil
         @file = params[:incoming_file]
         @file_class = @file.class.to_s
         @file_stuff = @file_class
         #@file_info_name = @file.original_filename
         #unless @file.class.to_s.eql?("String") #=~ /\w/
         @file_name = @file.original_filename
         @file_name.gsub!(/[^\w\.\-]/,'_')
         @file_name.gsub!(/\s/,'_')
         @file_size = @file.size
         
         if @file_name !~ /\w/
            render :action => :index
         end
         file_type = @file.content_type
         @file_info = $save_dir
         File.open("#{$save_dir}/#{@file_name}", "wb") do |f|
            f.write(params[:incoming_file].read)
         end
         #end
      end
      if(params[:incoming_file] or params[:saved])
         unless @file_name
            @file_name = params[:saved]
         end
         @submission = FileBoxFile.new
         @submission.size = @file_size
         @submission.name = @file_name
         @submission.location = "#{$save_dir}/#{@file_name}"
         @submission.submitted_on = Time.now
         @submission.group = @group
         @submission.save
      end
      @files = FileBoxFile.find(:all)
      responds_to_parent do
         render :update do |page|
            page.replace_html 'file_box_view', :partial => "section_files"
         end
      end
      #  render :partial => "section_files"
   end
end
