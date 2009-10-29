class ContactController < ApplicationController

   def index
      if params[:contact]
         show_contact
         render :action => 'show_contact'
      else
         redirect_to '/'
      end
   end

   def show_contact
      if params[:contact]
         if @contact = Contact.find(:first, :conditions => ["LastName REGEXP ?", params[:contact]])
            @contact.Address.gsub!(/\n/, '<br />')
         end
         @cruises = Cruise.find(:all, :conditions => ["Chief_Scientist REGEXP ?", params[:contact]])
      end
   end

end
