require 'vpim/vcard'

class Staff::VcardController < ApplicationController

  def index
  end

  def decode
    # Rails uploads can give either StringIOs or UploadedTempFiles
    # Turn StringIOs into tempfile and give the path to the tempfile
    def get_tempfile(uploaded_file)
      if uploaded_file.kind_of? ActionController::UploadedStringIO
        temp = Tempfile.new 'vcard_upload'
        uploaded_file.each_line {|line| temp.write line }
        temp.flush
        uploaded_file = temp
      end
      return uploaded_file
    end
    file = get_tempfile(params[:vcard]).open.read
    file.gsub! 'EMAIL; INTERNET', 'EMAIL;INTERNET' # Fix UCSD invalid syntax
    file.gsub! 'TEL; WORK', 'TEL;WORK' # Fix UCSD invalid syntax
    file.gsub! 'TEL; FAX', 'TEL;FAX' # Fix UCSD invalid syntax
    @cards = Vpim::Vcard.decode(file).collect do |card|
      addr = card.address('work')
      tel = (card.telephone('work') or '').strip
      if tel =~ /\((\d{3})\)\s?(\d{3})-(\d{4})/
        tel = "+1-#{$1}-#{$2}-#{$3}"
      end
      fax = (card.telephone('fax') or '').strip
      if fax =~ /\((\d{3})\)\s?(\d{3})-(\d{4})/
        fax = "+1-#{$1}-#{$2}-#{$3}"
      end
      {:last => (card.name.family or '').strip,
       :first => (card.name.given or '').strip,
       :inst => (card.org or ['', '']).join('/').strip,
       :addrs => (addr.street or '').strip,
       :addrl => (addr.locality or '').strip+', '+(addr.region or '').strip+' '+(addr.country or '').strip+' '+(addr.postalcode or '').strip,
       :tel => tel,
       :fax => fax,
       :email => (card.email('work') or card.email('internet') or '').strip,
       :title => (card.name.prefix or '').strip
      }
    end
  end

  def import
    @contacts = params[:contacts].values
    @contacts.each do |contact|
      Contact.create(:LastName => contact[:last], 
                     :FirstName => contact[:first],
                     :Institute => contact[:inst],
                     :Address => contact[:addrs]+"\n"+contact[:addrl],
                     :telephone => contact[:tel],
                     :fax => contact[:fax],
                     :email => contact[:email],
                     :title => contact[:title])
    end
  end

end
