class GroupsController < ApplicationController
   def index
      if params[:id]
        query = "\"#{params[:id]}\""
      else
        query = '"Atlantic Onetime"'
      end
      redirect_to :controller => 'search', :query => query
   end
end
