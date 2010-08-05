require 'net/http'

class Tempfile
    attr_accessor :original_filename
end

class VisualController < ApplicationController
    layout 'standard'

    def index
    end

    # if autoload = params[:autoload]
    #     file = Tempfile.new('visual_autoopen')
    #     file.write(Net::HTTP.get('cchdo.ucsd.edu', autoopen))
    #     file.original_filename = autoopen
    #     file.flush
    # end

    def any_to_google_wire
        file = params[:file]
        filename = file.original_filename || 'data'
        begin
            tmpfilepath = get_tempfile_path(file)
            render _any_to_google_wire(tmpfilepath)
        rescue => e
            return {:text => "<textarea>{\"error\": \"#{e.to_s}\"}</textarea>",
                    :status => 500}
        end
    end

    private

    def _any_to_google_wire(filepath)
        begin
            logger.debug(filepath)
            wire = `#{LIBCCHDOBIN}/any_to_google_wire_json.py #{filepath}`
            if wire.include?('Database error') or wire.empty?
                return {:text => "<textarea>null</textarea>", :status => 500}
            else
                return {:text => "<textarea>#{wire}</textarea>"}
            end
        rescue => e
            return {:text => "<textarea>{\"error\": \"#{e.to_s}\"}</textarea>",
                    :status => 500}
        end
    end
end
