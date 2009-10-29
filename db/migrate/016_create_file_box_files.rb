class CreateFileBoxFiles < ActiveRecord::Migration
  def self.up
    unless table_exists? :file_box_files
      create_table :file_box_files do |t|
        t.column :submitted_by, :text
        t.column :name, :text
        t.column :location, :text
        t.column :user, :text
        t.column :group, :text
        t.column  :description, :text
        t.column  :submitted_on, :date
        t.column :size, :int
      end
    end
  end

  def self.down
    drop_table :file_box_files
  end
end
