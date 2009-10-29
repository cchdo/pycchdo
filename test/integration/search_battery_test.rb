require "#{File.dirname(__FILE__)}/../test_helper"

class SearchBatteryTest < ActionController::IntegrationTest
   fixtures :cruises

  # Replace this with your real tests.
  def test_truth
    assert true
  end
  
  def test_searches
    good_searches = %w{swift talley tritum knorr germany ger }
    bad_searches = %w{jaila; ekjij tritumo gnorr}
    
    bad_searches.each do |search|
      get "/search", :query => search
      assert_response :success
      assert_template "index"
      assert_select "h3" , :count => 1, :text => /no results for/i
    end
    
    good_searches.each do |search|
      get "/search", :query => search
      assert_response :success
      assert_template "index"
      puts search
      assert_select "table" do
        assert_select "tr" do
          assert_select "td" do
            assert_select "table.new_cruise_info"
          end
        end
      end
      #assert_select "div.block"
      #assert_select "div#block"
    end
    

  end
  
end
