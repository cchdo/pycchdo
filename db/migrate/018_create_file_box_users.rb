class CreateFileBoxUsers < ActiveRecord::Migration
  def self.up
    unless table_exists? :file_box_users
      create_table :file_box_users do |t|
        t.column :username, :text
        t.column :group, :text
        t.column :admin, :boolean
      end
    end
  end

  def self.down
    drop_table :file_box_users
  end
end
