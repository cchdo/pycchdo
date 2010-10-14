class Tempfile
  attr_accessor :original_filename
end

class Tools::ToolsController < ApplicationController
  def any_to_google_wire
    begin
      unless file = params[:file]
        render :text => "<textarea>{\"error\": \"No file.\"}</textarea>",
               :status => 500
        return
      end
      filename = file.original_filename || 'data'
      tmpfilepath = get_tempfile_path(file)
      _any_to_google_wire(tmpfilepath)
    rescue Exception => e
      render :text => "<textarea>{\"error\": \"#{e.to_s}\"}</textarea>",
             :status => 500
    end
  end

  protected

  LIBCCHDOBIN = '/Users/myshen/Documents/libcchdo/bin'

  private

  def _any_to_google_wire(filepath)
    begin
      wire = `#{LIBCCHDOBIN}/any_to_google_wire.py --json #{filepath}`
      if wire.include?('Database error') or wire.empty?
        render :text => "<textarea>null</textarea>", :status => 500
      else
        render :text => "<textarea>#{wire}</textarea>"
      end
    rescue Exception => e
      render :text => "<textarea>{\"error\": \"#{e.to_s}\"}</textarea>",
             :status => 500
    end
  end


  # Modify make_tmpname to maintain file extensions.
  class UploadedTempfile < Tempfile
    def make_tmpname(basename, n)
      sprintf('%d-%d%s', $$, n, basename)
    end
  end

  # Rails uploads can give either StringIOs or UploadedTempFiles
  # Turn StringIOs into tempfile and give the path to the tempfile
  def get_tempfile(uploaded_file)
    unless uploaded_file
      return nil
    end
    filename = uploaded_file.original_filename || 'data'
    basename = File.basename(filename)
    temp = UploadedTempfile.new(basename)
    temp.write(uploaded_file.read())
    temp.flush()
    uploaded_file.close()
    temp
  end

  def get_tempfile_path(uploaded_file)
    get_tempfile(uploaded_file).path
  end
end
