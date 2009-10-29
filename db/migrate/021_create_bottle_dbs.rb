class CreateBottleDBs < ActiveRecord::Migration
  def self.up
    unless table_exists :bottle_dbs
      create_table :bottle_dbs do |t|
        t.timestamps
      end
    end
  end

  def self.down
  end
end
