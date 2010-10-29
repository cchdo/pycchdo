require 'test_helper'

class RoutingTest < Test::Unit::TestCase

  def setup
    ActionController::Routing::Routes.draw do |map|
      map.cchdo_webtools
    end
  end

  def test_cchdo_webtools_route
    assert_recognition :get, "/btlcmp", :controller => :cchdo_webtools_controller, :action => :btlcmp
    assert_recognition :get, "/visual", :controller => :cchdo_webtools_controller, :action => :visual
    assert_recognition :get, "/convert", :controller => :cchdo_webtools_controller, :action => :convert

    assert_recognition :get, "/none", :controller => :cchdo_webtools_controller, :action => :none
  end

  private

    def assert_recognition(method, path, options)
      result = ActionController::Routing::Routes.recognize_path(path, :method => method)
      assert_equal(options, result)
    end

end
