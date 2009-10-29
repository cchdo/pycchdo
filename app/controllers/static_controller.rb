class StaticController < ApplicationController
  NO_CACHE = [
    'static/about/website',
  ]
  
  def index
    unless params[:path].blank?
      if template_exists? path = 'static/' + params[:path].join('/') or template_exists? path += 'index.rhtml'
        render_cached path
      else
        flash[:notice] = "<strong>404 Not found</strong> &mdash; The page you were looking for (#{params[:path]}) does not exist. Please try the search feature of this website instead!"
        #raise ::ActionController::RoutingError,
        #      "Recognition failed for #{request.path.inspect}"
      end
    end
  end
  
  private

  # Define template_exists? for Rails 2.3 (cause it's deprecated)
  unless ActionController::Base.private_instance_methods.include? 'template_exists?'
    def template_exists?(path)
      self.view_paths.find_template(path, response.template.template_format)
    rescue ActionView::MissingTemplate
      false
    end
  end

  def render_cached(path)
    if NO_CACHE.include? path
      render :template => path
    else
      key = path.gsub('/', '-')
      #unless content = read_fragment(key)
      #   content = render_to_string :template => path, :layout => false
      #   write_fragment(key, content)
      #end
      #render :text => content, :layout => true

      #content = nil
      #when_fragment_expired key, 15.minutes.from_now do 
      #  content = render_to_string :template => path, :layout => false
      #end
      content = render_to_string :template => path, :layout => false
      if content
        render :text => content, :layout => true
      else
        render :nothing => true, :status => 304
      end
    end
  end
end
