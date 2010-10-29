# CchdoWebtools
require "cchdo_webtools/routing"

directory = File.dirname(__FILE__)
%w{controllers}.each do |dir|
  path = File.join(directory, 'app', dir)
  $stderr.puts path
  $LOAD_PATH << path
  ActiveSupport::Dependencies.load_paths << path
  # TODO remove when not developing
  ActiveSupport::Dependencies.load_once_paths.delete(path)
end

ActionController::Base.view_paths.unshift(File.join(directory, 'app', 'views'))
