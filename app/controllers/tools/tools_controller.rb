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
end
