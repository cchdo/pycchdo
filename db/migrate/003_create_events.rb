class CreateEvents < ActiveRecord::Migration
  def self.up
    unless table_exists? :events
      create_table :events do |t|
        # t.column :name, :string
        t.column :ExpoCode, :text 
        t.column :First_Name, :text 
        t.column :LastName, :text
        t.column :Data_Type, :text 
        t.column :Date_Entered, :date 
        t.column :Summary, :text 
        t.column :Note, :text
      end
    end
  end

  def self.down
  end
end
