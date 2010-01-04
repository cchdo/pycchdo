class VisualController < ApplicationController
  layout 'standard'

  def index
    file = params[:file]
    @filename = nil
    @wire = nil
    if file.blank?
      flash[:notice] = 'Please give me a file to read.'
    else
      @filename = file.original_filename || 'data'
      begin
        tmpfilepath = get_tempfile_path(file)
        result = `#{LIBCCHDOBIN}/bottle_exchange_to_google_wire.py #{tmpfilepath} 2>&1`.split(/$/)
        if result.last !~ /^\{.*\}$/
          flash[:notice] = result.join('\n')
          @wire = '{cols:[{type:"string"}],rows:[{c:[{v:"Parse Failed"}]}]}'
        else
          @wire = result.last
        end
      rescue
        flash[:notice] = "Error parsing file: #{$!}"
      end
    end
  end
end
