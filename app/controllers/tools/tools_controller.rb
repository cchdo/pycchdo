class Tempfile
  attr_accessor :original_filename
end

class Tools::ToolsController < ApplicationController
  def any_to_google_wire
    begin
      file = params[:file]
      unless file and (file.kind_of?(String) or file.kind_of?(Tempfile))
        render_json_error("No file.")
        return
      end
      filename = file.original_filename || 'data'
      tmpfilepath = get_tempfile_path(file)
      wire = `#{LIBCCHDOBIN}/any_to_google_wire.py --json #{tmpfilepath}`
      if wire.empty?
        render_json_error("Failed to parse.")
      else
        render_json(wire)
      end
    rescue Exception => e
      render_json_error(e.to_s)
    end
  end

  protected

  LIBCCHDOBIN = '/Users/myshen/Documents/libcchdo/bin'

  private

  def render_json(json, status=200)
    render :text => "<textarea>#{json}</textarea>", :status => status
  end

  def render_json_error(error)
    render_json("{\"error\": \"#{error}\"}", 500)
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
