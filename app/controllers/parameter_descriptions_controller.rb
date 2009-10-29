class ParameterDescriptionsController < ApplicationController
   def index
      @parameters = ParameterDescriptions.find(:all)
   end
end
