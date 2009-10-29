require File.dirname(__FILE__) + '/../test_helper'
require 'parameter_descriptions_controller'

# Re-raise errors caught by the controller.
class ParameterDescriptionsController; def rescue_action(e) raise e end; end

class ParameterDescriptionsControllerTest < Test::Unit::TestCase
  def setup
    @controller = ParameterDescriptionsController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
