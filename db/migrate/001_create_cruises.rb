class CreateCruises < ActiveRecord::Migration
  def self.up
    unless table_exists? :cruises
      create_table :cruises do |t|
        t.column :ExpoCode,		:text
        t.column :Line,			:text
        t.column :Country,		:text
        t.column :Chief_Scientist,	:text
        t.column :Begin_Date,		:date
        t.column :EndDate,		:date
        t.column :Ship_Name,		:text
        t.column :Alias,		:text
        t.column :Group,		:text 
      end
    end
  end

  def self.down
  end
end
