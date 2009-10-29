class CreateFileBoxGroups < ActiveRecord::Migration
  def self.up
    unless table_exists? :file_box_groups
      create_table :file_box_groups do |t|
        t.column  :groups, :text
      end
    end
  end

  def self.down
    drop_table :file_box_groups
  end
end
