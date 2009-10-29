require File.dirname(__FILE__) + '/../test_helper'
require 'parameter_test_controller'

# Re-raise errors caught by the controller.
class ParameterTestController; def rescue_action(e) raise e end; end

class ParameterTestControllerTest < Test::Unit::TestCase
  def setup
    @controller = ParameterTestController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
