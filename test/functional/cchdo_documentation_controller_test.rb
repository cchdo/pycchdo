require File.dirname(__FILE__) + '/../test_helper'
require 'cchdo_documentation_controller'

# Re-raise errors caught by the controller.
class CchdoDocumentationController; def rescue_action(e) raise e end; end

class CchdoDocumentationControllerTest < Test::Unit::TestCase
  def setup
    @controller = CchdoDocumentationController.new
    @request    = ActionController::TestRequest.new
    @response   = ActionController::TestResponse.new
  end

  # Replace this with your real tests.
  def test_truth
    assert true
  end
end
