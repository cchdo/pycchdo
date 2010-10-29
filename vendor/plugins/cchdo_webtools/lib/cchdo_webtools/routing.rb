if Rails::VERSION::MAJOR == 2
  module CchdoWebtools #:nodoc:
    module Routing #:nodoc:
      module MapperExtensions
        def cchdo_webtools(options = {})
          options[:name_prefix] ||= ''
          options[:namespace] ||= ''
          named_route(options[:name_prefix] + :btlcmp.to_s, options[:namespace][0..-2] + '/btlcmp', :controller => :cchdo_webtools, :action => :btlcmp)
          named_route(options[:name_prefix] + :visual.to_s, options[:namespace][0..-2] + '/visual', :controller => :cchdo_webtools, :action => :visual)
          named_route(options[:name_prefix] + :xss.to_s, options[:namespace][0..-2] + '/xss/:file', :controller => :cchdo_webtools, :action => :xss)
          named_route(options[:name_prefix] + :convert.to_s, options[:namespace][0..-2] + '/convert', :controller => :cchdo_webtools, :action => :convert)
          named_route(options[:name_prefix] + :converter.to_s, options[:namespace][0..-2] + '/convert/:action', :controller => :cchdo_webtools, :method => :post)
        end
      end
    end
  end
  
  ActionController::Routing::RouteSet::Mapper.send :include, CchdoWebtools::Routing::MapperExtensions
else
  module CchdoWebtools #:nodoc:
    module Routing #:nodoc:
      module MapperExtensions
        def cchdo_webtools(options = {})
          match('/btlcmp' => 'cchdo_webtools#btlcmp')
          match('/visual' => 'cchdo_webtools#visual')
          match('/xss/:file' => 'cchdo_webtools#xss', :as => :xss)
          match('/convert' => 'cchdo_webtools#convert', :as => :convert)
          match('/convert/:action' => 'cchdo_webtools', :as => :converter)
        end
      end
    end
  end
  
  ActionDispatch::Routing::Mapper.send :include, CchdoWebtools::Routing::MapperExtensions
end
