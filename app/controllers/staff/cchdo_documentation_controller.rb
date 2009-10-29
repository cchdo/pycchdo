class Staff::CchdoDocumentationController < ApplicationController
   layout "staff"
   before_filter :check_authentication

   def index
   end

   def toggle
      @toggle_div = params[:id]
      @toggle_arrow_up = "#{@toggle_div}_arrow_up"
      @toggle_arrow_down = "#{@toggle_div}_arrow_down"
   end
end
