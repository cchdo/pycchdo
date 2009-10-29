class CruiseNewsController < ApplicationController
  layout false

  def recent_changes
    headers["Content-Type"] = "application/rss+xml"

    @date_list = Hash.new{|@date_list,key| @date_list[key]={}}

    if @recent_changes = Document.find(:all, :conditions => ["FileType != 'Directory'"], :order => "LastModified DESC", :limit => 150)
      @expo_list = @recent_changes.collect {|change| change.ExpoCode}.uniq
      @recent_changes.each do |change|
        date_list = @date_list[change.ExpoCode]
        date_list["Files"] ||= String.new
        if change.LastModified and change.LastModified !~ /\//
          unless change.FileType =~ /unrecognized/i
            if change.Stamp =~ /\w/
              date_list["Files"] << " #{change.FileType} (#{change.Stamp}),"
            else
              date_list["Files"] << " #{change.FileType},"
            end
          end
          if cruise = Cruise.find(:first, :conditions => {:ExpoCode => change.ExpoCode})
            date_list["Line"] = cruise.Line
          end
          date_list["Date"] = change.LastModified
        else
          date_list["Date"] = Time.now
        end
      end
    end
  end
end
