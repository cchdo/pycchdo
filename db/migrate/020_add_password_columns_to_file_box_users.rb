class AddPasswordColumnsToFileBoxUsers < ActiveRecord::Migration
  def self.up
    add_column :file_box_users, :password_salt, :string
    add_column :file_box_users, :password_hash, :string
  end

  def self.down
    remove_column :file_box_users, :password_salt
    remove_column :file_box_users, :password_hash
  end
end
