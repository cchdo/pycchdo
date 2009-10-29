class CreateParameterDescriptions < ActiveRecord::Migration
  def self.up
    unless table_exists? :parameter_descriptions
      create_table :parameter_descriptions do |t|
         t.column "Parameter", :string
         t.column "FullName", :string
         t.column "Description", :string
         t.column "Units", :string
         t.column "Range", :string
         t.column "Alias", :string
         t.column "Group", :string
      end
    end
  end

  def self.down
  end
end
