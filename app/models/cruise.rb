class Cruise < ActiveRecord::Base
   #set_primary_key :Entry

   validates_presence_of :ExpoCode

   #validates_uniqueness_of :ExpoCode,
   #                        :message => "is not unique"

   validates_format_of :ExpoCode,
     :with => /^\w+$/,
     :message => "is missing or invalid"

   validates_format_of :Chief_Scientist,
     :with => /^[\w:\/\\\s\'\(\)]+$/,
     :message => "is missing or invalid"

   validates_format_of :Ship_Name,
     :with => /^[\w\'\.\s\(\)]+$/,
     :message => "is missing or invalid"

   validates_format_of :Line,
     :with => /^\w+$/,
     :message => "is missing or invalid"

   validates_format_of :Country,
     :with => /^\w+$/,
     :message => "is missing or invalid"

end
