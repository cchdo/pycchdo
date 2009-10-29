class Document < ActiveRecord::Base

   def self.first_directory_of(expocode)
      return Document.find(:first, :conditions => {:ExpoCode => expocode, :FileType => 'Directory'})
   end

   def self.directories_of(expocode)
      return Document.find(:all, :conditions => {:ExpoCode => expocode, :FileType => 'Directory'})
   end

   def self.files_in(directory)
      # Return array of files in directory
      if directory
         files = directory.Files.split /\s/
         files.each do |file|
            if file =~ /\*$/
               file.chop!
            end
         end
         return files
      end
   end

   def self.file_hash_for(expocode)
      # Get the files and return a hash
      # { <file type> => <file path> }
      file_results = Hash.new
      if dir = Document.first_directory_of(expocode)
         if files = Document.files_in(dir)
            files.each do |file|
               filepath = "#{dir.FileName}/#{file}"
               filetype = ''
               case file
                  when /su.txt$/ then filetype = 'woce_sum'
                  when /ct.zip/  then filetype = 'woce_ctd'
                  when /hy.txt/  then filetype = 'woce_bot'
                  when /hy1.csv/ then filetype = 'exchange_bot'
                  when /ct1.zip/ then filetype = 'exchange_ctd'
                  when /ctd.zip/ then filetype = 'netcdf_ctd'
                  when /hyd.zip/ then filetype = 'netcdf_bot'
                  when /do.txt/  then filetype = 'text_doc'
                  when /do.pdf/  then filetype = 'pdf_doc'
                  when /.gif/    then filetype = 'big_pic'
                  when /.jpg/    then filetype = 'small_pic'
                  when /lv.txt/  then filetype = 'large_volume'
                  when /lvs.txt/ then filetype = 'large_volume'
               end
               file_results[filetype] = filepath
            end
         end
      end
      return file_results
   end
   
   def self.files_for_cruises(cruises)
      # Take a list of cruise records and return a hash:
      # { <expocode> => { <filetype> => <file path>, ... }, ...}
      cruise_files = Hash.new{|hash, key| hash[key] = Hash.new}
      cruises.each do |cruise|
         file_hash = Document.file_hash_for(cruise.ExpoCode)
         cruise_files[cruise.ExpoCode] = file_hash
      end
      return cruise_files
   end
end
