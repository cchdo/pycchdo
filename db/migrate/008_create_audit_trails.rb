class CreateAuditTrails < ActiveRecord::Migration
  def self.up
    unless table_exists? :audit_trails
      create_table :audit_trails do |t|
         t.column :record_id, :integer
         t.column :record_type, :string
         t.column :event, :string
         t.column :user_id, :integer
         t.column :time, :date
      end
    end
  end

  def self.down
  end
end
