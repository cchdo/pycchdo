class CreateCodes < ActiveRecord::Migration
  def self.up
    unless table_exists? :codes
      create_table :codes do |t|
         t.column :Code,   :integer
         t.column :Status, :text
      end
    end
  end

  def self.down
  end
end
