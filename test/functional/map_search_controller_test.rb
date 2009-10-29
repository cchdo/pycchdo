require File.dirname(__FILE__) + '/../test_helper'
require 'map_search_controller'

# Re-raise errors caught by the controller.
class MapSearchController; def rescue_action(e) raise e end; end

class MapSearchControllerTest < Test::Unit::TestCase
  def setup
    @controller = MapSearchController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
