require File.dirname(__FILE__) + '/../test_helper'

class SubmissionTest < Test::Unit::TestCase
  fixtures :submissions

  # Replace this with your real tests.
  def test_truth
    assert true
  end
  def test_invalid_with_empty_attributes
    submission = Submission.new
    assert !submission.valid?
    assert submission.errors.invalid?(:name)
    assert submission.errors.invalid?(:institute)
    assert submission.errors.invalid?(:Country)
    assert submission.errors.invalid?(:email)
    assert submission.errors.invalid?(:public)
    #assert submission.errors.invalid?(:ExpoCode)
    #assert submission.errors.invalid?(:Ship_Name)
    #assert submission.errors.invalid?(:Line)
    #assert submission.errors.invalid?(:cruise_date)
    #assert submission.errors.invalid?(:action)
    #assert submission.errors.invalid?(:notes )
    assert submission.errors.invalid?(:file)
    assert submission.errors.invalid?(:file_name)
    #assert submission.errors.invalid?(:assigned)
    #assert submission.errors.invalid?(:assimilated)
    #assert submission.errors.invalid?(:submission_date)
  end
  
  def test_email
    ok = %w{ person.NAME2@place.us.gov 3name@place.com  }
    bad = %w{ name.com @org @com person@ }
    ok.each do |email|
      submission = Submission.new(:name => 'test', :institute => "yyy" , :Country => 'US', :public => "no", :file => "filename", :file_name => "file",:email => email)
      assert submission.valid?, submission.errors.full_messages
    end
    bad.each do |email|
      submission = Submission.new(:name => "test" , :institute => "yyy" ,:Country => 'US', :public => "no", :file => "filename", :file_name => "file", :email => email)
      assert !submission.valid?, "saving #{email}"
    end
  end
  
end
