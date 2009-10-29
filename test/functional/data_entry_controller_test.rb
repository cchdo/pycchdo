require File.dirname(__FILE__) + '/../test_helper'
require 'data_entry_controller'

# Re-raise errors caught by the controller.
class DataEntryController; def rescue_action(e) raise e end; end

class DataEntryControllerTest < Test::Unit::TestCase
  def setup
    @controller = DataEntryController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
