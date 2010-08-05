require 'net/http'

class Tempfile
  attr_accessor :original_filename
end

class VisualController < ApplicationController
  layout 'standard'

  def index
    #file = params[:file]
    #if autoopen = params[:autoopen]
    #  file = Tempfile.new('visual_autoopen')
    #  file.write(Net::HTTP.get('cchdo.ucsd.edu', autoopen))
    #  file.original_filename = autoopen
    #  file.flush
    #end
    #@filename = nil
    #@wire = nil
    #if file.blank?
    #  flash[:notice] = 'Please give me a file to read.'
    #else
    #  @filename = file.original_filename || 'data'
    #  begin
    #    tmpfilepath = get_tempfile_path(file)
    #    result = `#{LIBCCHDOBIN}/bottle_exchange_to_google_wire.py #{tmpfilepath} 2>&1`.split(/$/)
    #    if result.last !~ /^\{.*\}$/
    #      flash[:notice] = result.join('\n')
    #      @wire = '{cols:[{type:"string"}],rows:[{c:[{v:"Parse Failed"}]}]}'
    #    else
    #      @wire = result.last
    #    end
    #  rescue
    #    flash[:notice] = "Error parsing file: #{$!}"
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
