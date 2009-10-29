class CreateContacts < ActiveRecord::Migration
  def self.up
    unless table_exists? :contacts
      create_table :contacts do |t|
        t.column :LastName,  :text
        t.column :FirstName, :text
        t.column :Institute, :text
        t.column :Address,   :text
        t.column :telephone, :text
        t.column :fax,       :text
        t.column :email,     :text
      end
    end
  end

  def self.down
  end
end
