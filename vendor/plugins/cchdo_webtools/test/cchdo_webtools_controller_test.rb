require 'test_helper'
require 'cchdo_webtools_controller'
require 'action_controller/test_process'

class CchdoWebtoolsController
  def rescue_action(e)
    raise e
  end
end

class CchdoWebtoolsTest < ActiveSupport::TestCase
  def setup
    @controller = CchdoWebtoolsController.new
    @request = ActionController::TestRequest.new
    @response = ActionController::TestResponse.new

    ActionController::Routing::Routes.draw do |map|
      map.resources :cchdo_webtools
    end
  end

  def test_btlcmp
    get :btlcmp
    assert_response :success
  end
end
