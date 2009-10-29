class CreateDocuments < ActiveRecord::Migration
  def self.up
    unless table_exists :documents
      create_table :documents do |t|
        # t.column :name, :string
        t.column :Size, :text 
        t.column :FileType, :text 
        t.column :FileName, :text 
        t.column :ExpoCode, :text 
        t.column :Files, :text 
        t.column :LastModified, :datetime
        t.column :Modified, :text
        t.column :Stamp, :text
      end
    end
  end

  def self.down
  end
end
