require File.dirname(__FILE__) + '/../test_helper'
require 'task_manager_controller'

# Re-raise errors caught by the controller.
class TaskManagerController; def rescue_action(e) raise e end; end

class TaskManagerControllerTest < Test::Unit::TestCase
  def setup
    @controller = TaskManagerController.new
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
