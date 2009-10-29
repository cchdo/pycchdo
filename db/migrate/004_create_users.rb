class CreateUsers < ActiveRecord::Migration
  def self.up
    unless table_exists? :users
      create_table :users do |t|
         t.column "username", :string
         t.column "password_salt", :string
         t.column "password_hash", :string
      end
    end
  end

  def self.down
  end
end
