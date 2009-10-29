require File.dirname(__FILE__) + '/../test_helper'
require 'cruise_status_controller'

# Re-raise errors caught by the controller.
class CruiseStatusController; def rescue_action(e) raise e end; end

class CruiseStatusControllerTest < Test::Unit::TestCase
  def setup
    @controller = CruiseStatusController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
