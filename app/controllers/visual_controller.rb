class VisualController < ApplicationController
  layout 'standard'

  def index
  end

  def any_to_google_wire
      file = params[:file]
      filename = file.original_filename || 'data'
      begin
          tmpfilepath = get_tempfile_path(file)
          logger.debug(tmpfilepath)
          wire = `#{LIBCCHDOBIN}/any_to_google_wire_json.py #{tmpfilepath}`
          if wire.include?('Database error') or wire.empty?
              render :text => "<textarea>null</textarea>", :status => 500
          else
              render :text => "<textarea>#{wire}</textarea>"
          end
      rescue => e
          render :text => "<textarea>{\"error\": \"#{e.to_s}\"}</textarea>", :status => 500
      end
  end

end
