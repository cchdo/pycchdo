class Staff::SoftwareController < ApplicationController
   layout "staff"
   before_filter :check_authentication

   def index

   end

end
