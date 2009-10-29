class DataHistoryController < ApplicationController
  def index
    if params[:ExpoCode]
      @note = params[:Note]
      @entry = params[:Entry]
      @cur_sort = params[:Sort]

      @updated = 'New'
      if date = Event.find(:first, :order => ['Date_Entered DESC'])
         @updated = "Last updated: #{date.Date_Entered}"
      end

      if @expo = params[:ExpoCode]
         order_by = 'Date_Entered DESC'
         if order_by =~ /(LastName|Data_Type)/
           order_by = @cur_sort
         end
         @events = Event.find(:all, :conditions => {:ExpoCode => @expo}, :order => [order_by])
         @cruise = Cruise.find(:first, :conditions => {:ExpoCode => @expo})
      end
      if @note
         if @note_entry = Event.find(:first, :conditions => {:ID => @entry})
           @note_entry[:Note].gsub!(/[\n\r\f]/,"<br />")
           @note_entry[:Note].gsub!(/[\t]/, '&nbsp;&nbsp;&nbsp;&nbsp;')
         end
      end
    else
      redirect_to :controller => 'search'
    end
  end
end
