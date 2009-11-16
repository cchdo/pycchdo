class VisualController < ApplicationController
  layout 'standard'

  def index
    file = params[:file]
    @filename = nil
    @wire = nil
    if file.blank?
      flash[:notice] = 'Please give me a file to read.'
    else
      # Rails uploads can give either StringIOs or UploadedTempFiles
      # Turn StringIOs into tempfile and give the path to the tempfile
      def get_tempfile_path(uploaded_file)
        if uploaded_file.kind_of? ActionController::UploadedStringIO
          temp = Tempfile.new 'visual_upload'
          uploaded_file.each_line {|line| temp.write line }
          temp.flush
          return temp.path
        else
          return uploaded_file.path
        end
      end
  
      @filename = file.original_filename || 'data'
      begin
        tmpfilepath = get_tempfile_path(file)
        @wire = `/Users/myshen/work/libcchdo/bin/bottle_exchange_to_google_wire.py #{tmpfilepath}`
        @wire = '{}' if @wire =~ /Database error/
      rescue
        flash[:notice] = "Error parsing file: #{$!}"
      end
    end
  end
end
