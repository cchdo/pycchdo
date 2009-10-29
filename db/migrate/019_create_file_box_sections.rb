class CreateFileBoxSections < ActiveRecord::Migration
  def self.up
    unless table_exists? :file_box_sections
      create_table :file_box_sections do |t|
        t.column :name, :text
        t.column :files, :integer
        t.column :cruise, :text
        t.column :ExpoCode, :text
      end
    end
  end

  def self.down
    drop_table :file_box_sections
  end
end
