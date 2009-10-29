# This file is auto-generated from the current state of the database. Instead of editing this file, 
# please use the migrations feature of Active Record to incrementally modify your database, and
# then regenerate this schema definition.
#
# Note that this schema.rb definition is the authoritative source for your database schema. If you need
# to create the application database on another system, you should be using db:schema:load, not running
# all the migrations from scratch. The latter is a flawed and unsustainable approach (the more migrations
# you'll amass, the slower it'll run and the greater likelihood for issues).
#
# It's strongly recommended to check this file into your version control system.

ActiveRecord::Schema.define(:version => 20) do

  create_table "bottle_dbs", :force => true do |t|
    t.text    "ExpoCode"
    t.text    "Parameters"
    t.text    "Parameter_Persistance"
    t.text    "Bottle_Code"
    t.text    "Location"
    t.integer "Entries",               :limit => 11
    t.integer "Stations",              :limit => 11
  end

  create_table "codes", :id => false, :force => true do |t|
    t.integer "Code",   :limit => 11
    t.text    "Status"
  end

  create_table "contacts", :primary_key => "ID", :force => true do |t|
    t.text "LastName",  :null => false
    t.text "FirstName", :null => false
    t.text "Institute", :null => false
    t.text "Address",   :null => false
    t.text "telephone", :null => false
    t.text "fax",       :null => false
    t.text "email",     :null => false
  end

  create_table "cruises", :force => true do |t|
    t.text "ExpoCode"
    t.text "Line"
    t.text "Country"
    t.text "Chief_Scientist"
    t.date "Begin_Date"
    t.date "EndDate"
    t.text "Ship_Name"
    t.text "Alias"
    t.text "Group"
  end

  create_table "documents", :force => true do |t|
    t.text     "Size"
    t.text     "FileType"
    t.text     "FileName"
    t.text     "ExpoCode"
    t.text     "Files"
    t.datetime "LastModified"
    t.text     "Modified"
    t.text     "Stamp",        :null => false
  end

  create_table "events", :primary_key => "ID", :force => true do |t|
    t.text "ExpoCode"
    t.text "First_Name"
    t.text "LastName"
    t.text "Data_Type"
    t.text "Action"
    t.date "Date_Entered"
    t.text "Summary"
    t.text "Note"
  end

  create_table "file_box_files", :force => true do |t|
    t.text    "submitted_by"
    t.text    "name"
    t.text    "location"
    t.text    "user"
    t.text    "group"
    t.text    "description"
    t.date    "submitted_on"
    t.integer "size",         :limit => 11
  end

  create_table "file_box_groups", :force => true do |t|
    t.text "groups"
  end

  create_table "file_box_sections", :force => true do |t|
    t.text    "name"
    t.integer "files",    :limit => 11
    t.text    "cruise"
    t.text    "ExpoCode"
  end

  create_table "file_box_users", :force => true do |t|
    t.text    "user"
    t.text    "group"
    t.boolean "admin"
    t.string  "password_salt"
    t.string  "password_hash"
  end

  create_table "internal", :id => false, :force => true do |t|
    t.text "Line"
    t.text "File"
    t.text "ExpoCode"
    t.text "Basin"
  end

  create_table "iptocs", :force => true do |t|
    t.integer "ip_from",       :limit => 11, :null => false
    t.integer "ip_to",         :limit => 11, :null => false
    t.string  "country_code2",               :null => false
    t.string  "country_code3",               :null => false
    t.string  "country_name",                :null => false
  end

  add_index "iptocs", ["ip_from", "ip_to"], :name => "index_iptocs_on_ip_from_and_ip_to", :unique => true

  create_table "parameter_descriptions", :force => true do |t|
    t.string "Parameter"
    t.string "FullName"
    t.string "Description"
    t.string "Units"
    t.string "Range"
    t.string "Alias"
    t.string "Group"
    t.string "Unit_mnemonic", :default => ""
    t.string "Precision",     :default => ""
  end

  create_table "parameter_descriptions_copy", :force => true do |t|
    t.string "Parameter"
    t.string "FullName"
    t.string "Description"
    t.string "Units"
    t.string "Range"
    t.string "Alias"
    t.string "Group"
    t.string "Unit_mnemonic", :default => ""
  end

  create_table "parameter_groups", :force => true do |t|
    t.text "group"
    t.text "parameters"
  end

  create_table "parameters", :force => true do |t|
    t.text "ExpoCode"
    t.text "THETA"
    t.text "THETA_PI"
    t.date "THETA_Date"
    t.text "SILCAT"
    t.text "SILCAT_PI"
    t.date "SILCAT_Date"
    t.text "SALNTY"
    t.text "SALNTY_PI"
    t.date "SALNTY_Date"
    t.text "PHSPHT"
    t.text "PHSPHT_PI"
    t.date "PHSPHT_Date"
    t.text "OXYGEN"
    t.text "OXYGEN_PI"
    t.date "OXYGEN_Date"
    t.text "NO2+NO3"
    t.text "NO2+NO3_PI"
    t.date "NO2+NO3_Date"
    t.text "HELIUM"
    t.text "HELIUM_PI"
    t.date "HELIUM_Date"
    t.text "DELC14"
    t.text "DELC14_PI"
    t.date "DELC14_Date"
    t.text "CTDTMP"
    t.text "CTDTMP_PI"
    t.date "CTDTMP_Date"
    t.text "CTDSAL"
    t.text "CTDSAL_PI"
    t.date "CTDSAL_Date"
    t.text "CTDPRS"
    t.text "CTDPRS_PI"
    t.date "CTDPRS_Date"
    t.text "CFC113"
    t.text "CFC113_PI"
    t.date "CFC113_Date"
    t.text "CFC-12"
    t.text "CFC-12_PI"
    t.date "CFC-12_Date"
    t.text "CFC-11"
    t.text "CFC-11_PI"
    t.date "CFC-11_Date"
    t.text "CCL4"
    t.text "CCL4_PI"
    t.date "CCL4_Date"
    t.text "TCARBN"
    t.text "TCARBN_PI"
    t.date "TCARBN_Date"
    t.text "REVTMP"
    t.text "REVTMP_PI"
    t.date "REVTMP_Date"
    t.text "PCO2"
    t.text "PCO2_PI"
    t.date "PCO2_Date"
    t.text "NITRIT"
    t.text "NITRIT_PI"
    t.date "NITRIT_Date"
    t.text "NITRAT"
    t.text "NITRAT_PI"
    t.date "NITRAT_Date"
    t.text "CTDRAW"
    t.text "CTDRAW_PI"
    t.date "CTDRAW_Date"
    t.text "ALKALI"
    t.text "ALKALI_PI"
    t.date "ALKALI_Date"
    t.text "O18O16"
    t.text "O18O16_PI"
    t.date "O18O16_Date"
    t.text "MCHFRM"
    t.text "MCHFRM_PI"
    t.date "MCHFRM_Date"
    t.text "DELHE3"
    t.text "DELHE3_PI"
    t.date "DELHE3_Date"
    t.text "CTDOXY"
    t.text "CTDOXY_PI"
    t.date "CTDOXY_Date"
    t.text "REVPRS"
    t.text "REVPRS_PI"
    t.date "REVPRS_Date"
    t.text "PH"
    t.text "PH_PI"
    t.date "PH_Date"
    t.text "DELC13"
    t.text "DELC13_PI"
    t.date "DELC13_Date"
    t.text "PPHYTN"
    t.text "PPHYTN_PI"
    t.date "PPHYTN_Date"
    t.text "CHLORA"
    t.text "CHLORA_PI"
    t.date "CHLORA_Date"
    t.text "CH4"
    t.text "CH4_PI"
    t.date "CH4_Date"
    t.text "AZOTE"
    t.text "AZOTE_PI"
    t.date "AZOTE_Date"
    t.text "ARGON"
    t.text "ARGON_PI"
    t.date "ARGON_Date"
    t.text "NEON"
    t.text "NEON_PI"
    t.date "NEON_Date"
    t.text "PCO2TMP"
    t.text "PCO2TMP_PI"
    t.date "PCO2TMP_Date"
    t.text "IODIDE"
    t.text "IODIDE_PI"
    t.date "IODIDE_Date"
    t.text "IODATE"
    t.text "IODATE_PI"
    t.date "IODATE_Date"
    t.text "NH4"
    t.text "NH4_PI"
    t.date "NH4_Date"
    t.text "RA-228"
    t.text "RA-228_PI"
    t.date "RA-228_Date"
    t.text "RA-226"
    t.text "RA-226_PI"
    t.date "RA-226_Date"
    t.text "KR-85"
    t.text "KR-85_PI"
    t.date "KR-85_Date"
    t.text "POC"
    t.text "POC_PI"
    t.date "POC_Date"
    t.text "PON"
    t.text "PON_PI"
    t.date "PON_Date"
    t.text "TDN"
    t.text "TDN_PI"
    t.date "TDN_Date"
    t.text "DOC"
    t.text "DOC_PI"
    t.date "DOC_Date"
    t.text "AR-39"
    t.text "AR-39_PI"
    t.date "AR-39_Date"
    t.text "BACT"
    t.text "BACT_PI"
    t.date "BACT_Date"
    t.text "ARAB"
    t.text "ARAB_PI"
    t.date "ARAB_Date"
    t.text "MAN"
    t.text "MAN_PI"
    t.date "MAN_Date"
    t.text "BRDU"
    t.text "BRDU_PI"
    t.date "BRDU_Date"
    t.text "RHAM"
    t.text "RHAM_PI"
    t.date "RHAM_Date"
    t.text "GLU"
    t.text "GLU_PI"
    t.date "GLU_Date"
    t.text "DCNS"
    t.text "DCNS_PI"
    t.date "DCNS_Date"
    t.text "FUC"
    t.text "FUC_PI"
    t.date "FUC_Date"
    t.text "PRO"
    t.text "PRO_PI"
    t.date "PRO_Date"
    t.text "PEUK"
    t.text "PEUK_PI"
    t.date "PEUK_Date"
    t.text "SYN"
    t.text "SYN_PI"
    t.date "SYN_Date"
    t.text "BTLNBR"
    t.text "BTLNBR_PI"
    t.date "BTLNBR_Date"
    t.text "AOU"
    t.text "AOU_PI"
    t.date "AOU_Date"
    t.text "TOC"
    t.text "TOC_PI"
    t.date "TOC_Date"
    t.text "CASTNO"
    t.text "CASTNO_PI"
    t.date "CASTNO_Date"
    t.text "DEPTH"
    t.text "DEPTH_PI"
    t.date "DEPTH_Date"
    t.text "Halocarbons"
    t.text "Halocarbons_PI"
    t.date "Halocarbons_Date"
    t.text "I-129"
    t.text "I-129_PI"
    t.date "I-129_Date"
    t.text "BARIUM"
    t.text "BARIUM_PI"
    t.date "BARIUM_Date"
    t.text "DON"
    t.text "DON_PI"
    t.date "DON_Date"
    t.text "SF6"
    t.text "SF6_PI"
    t.date "SF6_Date"
    t.text "NI"
    t.text "NI_PI"
    t.date "NI_Date"
    t.text "CU"
    t.text "CU_PI"
    t.date "CU_Date"
    t.text "CALCIUM"
    t.text "CALCIUM_PI"
    t.date "CALCIUM_Date"
    t.text "PHSPER"
    t.text "PHSPER_PI"
    t.date "PHSPER_Date"
    t.text "NTRIER"
    t.text "NTRIER_PI"
    t.date "NTRIER_Date"
    t.text "NTRAER"
    t.text "NTRAER_PI"
    t.date "NTRAER_Date"
    t.text "DELHE4"
    t.text "DELHE4_PI"
    t.date "DELHE4_Date"
    t.text "N2O"
    t.text "N2O_PI"
    t.date "N2O_Date"
    t.text "DMS"
    t.text "DMS_PI"
    t.date "DMS_Date"
    t.text "TRITUM"
    t.text "TRITUM_PI"
    t.date "TRITUM_Date"
    t.text "PHTEMP"
    t.text "PHTEMP_PI"
    t.date "PHTEMP_Date"
  end

  create_table "rail_stats", :force => true do |t|
    t.string   "remote_ip"
    t.string   "country"
    t.string   "language"
    t.string   "domain"
    t.string   "subdomain"
    t.string   "referer"
    t.string   "resource"
    t.string   "user_agent"
    t.string   "platform"
    t.string   "browser"
    t.string   "version"
    t.datetime "created_at"
    t.date     "created_on"
    t.string   "screen_size"
    t.string   "colors"
    t.string   "java"
    t.string   "java_enabled"
    t.string   "flash"
  end

  add_index "rail_stats", ["subdomain"], :name => "index_rail_stats_on_subdomain"

  create_table "search_terms", :force => true do |t|
    t.string  "subdomain",                 :default => ""
    t.string  "searchterms",               :default => "", :null => false
    t.integer "count",       :limit => 11, :default => 0,  :null => false
    t.string  "domain"
  end

  add_index "search_terms", ["subdomain"], :name => "index_search_terms_on_subdomain"

  create_table "sessions", :force => true do |t|
    t.string   "session_id"
    t.text     "data"
    t.datetime "updated_at"
  end

  add_index "sessions", ["session_id"], :name => "index_sessions_on_session_id"
  add_index "sessions", ["updated_at"], :name => "index_sessions_on_updated_at"

  create_table "tracks", :force => true do |t|
    t.string "ExpoCode"
    t.string "FileName"
    t.string "Basin"
    t.text   "Track"
  end

  create_table "users", :force => true do |t|
    t.text "username"
    t.text "password_salt"
    t.text "password_hash"
  end

end
