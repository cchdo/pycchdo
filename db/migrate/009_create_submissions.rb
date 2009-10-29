class CreateSubmissions < ActiveRecord::Migration
  def self.up
    unless table_exists? :submissions
      create_table :submissions do |t|
         t.column :name, :text
         t.column :institute, :text
         t.column :Country, :text
         t.column :email, :text
         t.column :public, :text
         t.column :ExpoCode, :text
         t.column :Ship_Name, :text
         t.column :Line, :text
         t.column :cruise_date, :date
         t.column :action, :text
         t.column :notes, :text
         t.column :file, :text
         t.column :assigned, :boolean
         t.column :assimilated, :boolean
      end
    end
  end

  def self.down
  end
end
