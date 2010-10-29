# CchdoWebtools
require "cchdo_webtools/routing"

directory = File.dirname(__FILE__)

if Rails::VERSION::MAJOR == 2
  %w{controllers}.each do |dir|
    path = File.join(directory, 'app', dir)
    $stderr.puts path
    $LOAD_PATH << path
    ActiveSupport::Dependencies.load_paths << path
    # TODO remove when not developing
    ActiveSupport::Dependencies.load_once_paths.delete(path)
  end

  ActionController::Base.view_paths.unshift(File.join(directory, 'app', 'views'))
else

  module Webtools
    class Application < Rails::Application
      directory = File.dirname(__FILE__)
      %w{controllers helpers}.each do |dir|
        path = File.join(directory, 'app', dir)
        Dir.new(path).each do |file|
          next if file[0].chr == '.'
          ActiveSupport::Dependencies.load_file(File.join(path, file))
        end
      end
      ActionController::Base.prepend_view_path(File.join(directory, 'app', 'views'))
    end
  end

end
