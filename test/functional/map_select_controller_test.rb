require File.dirname(__FILE__) + '/../test_helper'
require 'map_select_controller'

# Re-raise errors caught by the controller.
class MapSelectController; def rescue_action(e) raise e end; end

class MapSelectControllerTest < Test::Unit::TestCase
  def setup
    @controller = MapSelectController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
