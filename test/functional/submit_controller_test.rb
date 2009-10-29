require File.dirname(__FILE__) + '/../test_helper'
require 'submit_controller'

# Re-raise errors caught by the controller.
class SubmitController; def rescue_action(e) raise e end; end

class SubmitControllerTest < Test::Unit::TestCase
  def setup
    @controller = SubmitController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
  
  def test_index
    get :index
    assert_response :success
  end
  
end
