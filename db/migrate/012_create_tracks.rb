class CreateTracks < ActiveRecord::Migration
  def self.up
    unless table_exists? :tracks
      create_table :tracks do |t|
         t.column "ExpoCode", :string
         t.column "FileName", :string
         t.column "Basin", :string
         t.column "Track", :text
      end
    end
  end

  def self.down
  end
end
