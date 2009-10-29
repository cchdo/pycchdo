require File.dirname(__FILE__) + '/../test_helper'
require 'argo_controller'

# Re-raise errors caught by the controller.
class ArgoController; def rescue_action(e) raise e end; end

class ArgoControllerTest < Test::Unit::TestCase
  def setup
    @controller = ArgoController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
