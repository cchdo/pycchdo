class CreateParameterGroups < ActiveRecord::Migration
  def self.up
    unless table_exists? :parameter_groups
      create_table :parameter_groups do |t|
         t.column :group, :text
         t.column :parameters, :text
      end
    end
  end

  def self.down
  end
end
