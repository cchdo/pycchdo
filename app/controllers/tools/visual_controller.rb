require 'net/http'

class Tools::VisualController < ApplicationController
    layout 'standard'

    def index
    end

    # if autoload = params[:autoload]
    #     file = Tempfile.new('visual_autoopen')
    #     file.write(Net::HTTP.get('cchdo.ucsd.edu', autoopen))
    #     file.original_filename = autoopen
    #     file.flush
    # end
end
