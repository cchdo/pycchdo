require File.dirname(__FILE__) + '/../test_helper'
require 'dpo_tasks_controller'

# Re-raise errors caught by the controller.
class DpoTasksController; def rescue_action(e) raise e end; end

class DpoTasksControllerTest < Test::Unit::TestCase
  def setup
    @controller = DpoTasksController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
