class SeaHuntController < ApplicationController
  def index
    @cruises = SeaHunt.all
  end
end
