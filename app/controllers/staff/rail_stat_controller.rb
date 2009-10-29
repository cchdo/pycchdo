class Staff::RailStatController < ApplicationController
   unloadable
   layout 'staff'

   include PathTracker

   before_filter :extract_subdomain, :check_authentication, :except => [:track]

   def index
      redirect_to :controller => '/rail_stat', :action => 'pages'
   end

   def pages
      @number_visits = (params['visits'].nil?) ? 50 : params['visits'].to_i

      @ordered_resources, @orarr = RailStat.get_ordered40resources(@subdomain)
      @count_totals = RailStat.resource_count_totals
      @paths = RailStat.find_all_by_flag(@include_search_engines == 0, @number_visits, @subdomain)
      # Experiments:
      @total_visits = RailStat.count_visits(:subdomain => @subdomain)
      @unique_visits = RailStat.count_visits(:unique, :subdomain => @subdomain)
   end

   def visits
      @lastweek = RailStat.find_by_days(:subdomain=>@subdomain, :days => 7)
      @first_visit = RailStat.find_first_visit(:subdomain=>@subdomain)
      @total_visits = RailStat.count_visits(:subdomain => @subdomain)
      @unique_visits = RailStat.count_visits(:unique, :subdomain => @subdomain)
      n = Time.now
      d = Date.new(n.year, n.month, n.day)
      @today_total = RailStat.count_visits(:subdomain => @subdomain, :date => d)
      @today_unique = RailStat.count_visits(:unique, :subdomain => @subdomain, :date => d)
      @past_7_total = RailStat.count_visits(:subdomain => @subdomain, :past_days => 7)
      @past_7_unique = RailStat.count_visits(:unique, :subdomain => @subdomain,  :past_days => 7)
   end

   def platform
      @total_visits = RailStat.count_visits(:subdomain => @subdomain)

      @platforms = RailStat.find_by_platform(:subdomain => @subdomain)
      browsers = RailStat.find_by_browser(:subdomain => @subdomain)
      @browsers = Hash.new {|browser, name| browser[name] = Hash.new {|version, count| version[count] = Hash.new}}
      browsers.each do |b|
         unless b.browser.empty?
            @browsers[b.browser][b.version] = b.total.to_i
         end
      end

      @flash_clients = RailStat.count(:select => "1", :conditions => {:flash => 0, :subdomain => @subdomain}).to_f
      @java_clients = RailStat.count(:select => "1", :conditions => {:java_enabled => 1, :subdomain => @subdomain}).to_f
      @javascript_clients = RailStat.count(:select => "1", :conditions => {:java => 1, :subdomain => @subdomain}).to_f
      widths = RailStat.all(:select => "screen_size", :conditions => {:subdomain => @subdomain})
      @width_of_clients = Hash.new
      widths.each do |client|
        if @width_of_clients[client.screen_size]
          @width_of_clients[client.screen_size] += 1
        else
          @width_of_clients[client.screen_size] = 1.0
        end
      end
      colors = RailStat.all(:select => "colors", :conditions => {:subdomain => @subdomain})
      @colors_of_clients = Hash.new
      colors.each do |client|
        if @colors_of_clients[client.colors]
          @colors_of_clients[client.colors] += 1
        else
          @colors_of_clients[client.colors] = 1.0
        end
      end
   end

   def locations
      @total_visits = RailStat.count_visits(:subdomain => @subdomain)
      @languages = RailStat.find_by_language(:subdomain => @subdomain)
      @countries = RailStat.find_by_country(:subdomain => @subdomain)

      # do with iptocs

      iprecords = RailStat.find(:all, :select => "remote_ip", :order => "remote_ip ASC")
      ips = []
      iprecords.each {|record| ips << record.remote_ip}
      @countries = []
      ips.uniq.each do |ip|
         total = 0
         ips.each do |count_ip|
            if ip == count_ip
               total += 1
            end
         end

         padded_ip = pad_ip(ip)
         country = Iptoc.find(:first, :select => ["country_name"], :conditions => ["ip_from <= ? AND ip_to >= ?", padded_ip, padded_ip])
         if country
            @countries << { "country" => country.country_name, "ip" => ip, "total" => total}
         else
            @countries << { "country" => "Unknown", "ip" => ip, "total" => total }
         end
      end
   end

   def apps
      # Applications and parameters
      applications = RailStat.find(:all,
                                   :select => "parameters, resource",
                                   :conditions => "resource != '/index.html'",
                                   :order => "resource ASC")
      @applications = apps = Hash.new {|resource, parameters| resource[parameters] = Hash.new}
      applications.each do |app| 
         resource = app.resource || ""
         parameters = app.parameters || ""
         if apps[resource][parameters].blank?
            apps[resource][parameters] = 1
         else
            apps[resource][parameters] += 1
         end
      end

      # Referrer
      referers = RailStat.find(:all,
                               :select => ["referer, resource, parameters"],
                               :order => "referer ASC")
      @refs = Hash.new {|resource, referrer| resource[referrer] = Hash.new {|ref, params| ref[params] = Hash.new}}

      referers.each do |ref|
         referer = ref.referer || ""
         resource = ref.resource || ""
         parameters = ref.parameters || ""
         if @refs[resource][referer][parameters]
            @refs[resource][referer][parameters] += 1
         else
            @refs[resource][referer][parameters] = 1
         end
      end
   end

   def track
     render :file => '../../public/images/banners/transparent_menu_bg.png'
     track_path
   end

   private
   def extract_subdomain
      @subdomain = ((request.subdomains and request.subdomains.first) ? request.subdomains.first : nil)
   end

   def pad_ip (ip)
      blocks = ip.split('.')
      padded_ip = ''
      blocks.each do |block|
         while block.length < 3
            block = '0' + block
         end
         padded_ip += block
      end
      while padded_ip[0] == '0'
         padded_ip = padded_ip[1..-1]
      end
      return padded_ip
   end
end

