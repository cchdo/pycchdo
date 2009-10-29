require File.dirname(__FILE__) + '/../test_helper'
require 'data_history_controller'

# Re-raise errors caught by the controller.
class DataHistoryController; def rescue_action(e) raise e end; end

class DataHistoryControllerTest < Test::Unit::TestCase
  def setup
    @controller = DataHistoryController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
