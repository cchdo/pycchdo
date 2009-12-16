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
        @wire = `#{LIBCCHDOBIN}/bottle_exchange_to_google_wire.py #{tmpfilepath}`
        @wire = '{cols:[],rows:[]}' if @wire =~ /Database error/
      rescue
        flash[:notice] = "Error parsing file: #{$!}"
      end
    end
  end
end
