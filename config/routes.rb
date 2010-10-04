ActionController::Routing::Routes.draw do |map|
  # The priority is based upon order of creation: first created -> highest priority.
  
  # Sample of regular route:
  # map.connect 'products/:id', :controller => 'catalog', :action => 'view'
  # Keep in mind you can assign values other than :controller and :action

  # Sample of named route:
  # map.purchase 'products/:id/purchase', :controller => 'catalog', :action => 'purchase'
  # This route can be invoked with purchase_url(:id => product.id)

  # You can have the root of your site routed by hooking up '' 
  # -- just remember to delete public/index.html.
  # map.connect '', :controller => "welcome"

  map.connect '/staff/:controller/:action/:id'
  map.connect '/staff', :controller => '/staff/staff'

  map.namespace :tools do |tools|
    tools.btlcmp 'btlcmp', :controller => :btlcmp, :action => :index
    tools.convert 'convert', :controller => :convert, :action => :index
    tools.visual 'visual', :controller => :visual, :action => :index
    tools.connect ':controller/:action/:id'
  end

  # Allow downloading Web Service WSDL as a file with an extension
  # instead of a file named 'wsdl'
  map.connect ':controller/service.wsdl', :action => 'wsdl'

  # Install the default route as the lowest priority.
  map.connect ':controller/:action/:id'
  
  # Map for static pages to Static controller see http://snafu.diarrhea.ch/blog/article/4-serving-static-content-with-rails
  map.connect '*path', :controller => 'static'
end
