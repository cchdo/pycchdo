class CreateAssignments < ActiveRecord::Migration
  def self.up
    unless table_exists? :assignments
      create_table :assignments do |t|
         t.column :ExpoCode, :text
         t.column :project,  :text
         t.column :current_status, :text
         t.column :cchdo_contact, :text
         t.column :data_contact, :text
         t.column :action, :text
         t.column :parameter, :text
         t.column :history, :text
         t.column :changed, :date
         t.column :notes, :text
         t.column :priority, :integer
         t.column :deadline, :date
         t.column :manager, :string
      end
    end
  end

  def self.down
  end
end
