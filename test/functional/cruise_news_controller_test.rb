require File.dirname(__FILE__) + '/../test_helper'
require 'cruise_news_controller'

# Re-raise errors caught by the controller.
class CruiseNewsController; def rescue_action(e) raise e end; end

class CruiseNewsControllerTest < Test::Unit::TestCase
  def setup
    @controller = CruiseNewsController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
