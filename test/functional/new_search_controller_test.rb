require File.dirname(__FILE__) + '/../test_helper'
require 'new_search_controller'

# Re-raise errors caught by the controller.
class NewSearchController; def rescue_action(e) raise e end; end

class NewSearchControllerTest < Test::Unit::TestCase
  def setup
    @controller = NewSearchController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
