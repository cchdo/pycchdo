# Uninstall hook code here
def symlinkDir(x)
  dirname = 'cchdomap'
  File.unlink(Rails.root.join('public', x, dirname))
end

unlinkDir('images')
unlinkDir('javascripts')
unlinkDir('stylesheets')
rootdir = Rails.root
File.unlink(rootdir.join('app', 'controllers', 'search_maps_controller.rb'))
File.unlink(rootdir.join('app', 'views', 'search_maps', 'index.html.erb'))
