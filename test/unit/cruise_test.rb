require File.dirname(__FILE__) + '/../test_helper'

class CruiseTest < Test::Unit::TestCase
  fixtures :cruises

  # Replace this with your real tests.
  def test_truth
    assert true
  end
  
  def test_invalid_with_empty_expocode
    puts cruises(:bad_expo).Line
    cruise = Cruise.new(:ExpoCode => nil,:Line => "h11")
    assert !cruise.valid?
    assert_equal "is missing or invalid" ,cruise.errors.on(:ExpoCode)
  end
end
