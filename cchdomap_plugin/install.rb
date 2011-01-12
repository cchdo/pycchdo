# Install hook code here

rootdir = Rails.root
vendordir = rootdir.join('vendor', 'plugins', 'cchdomap', 'lib')
vendorpubdir = vendordir.join('public')

def symlinkDir(x)
  dirname = 'cchdomap'
  File.symlink(x, Rails.root.join('public', x, dirname))
end

def mkdirp(dir)
  begin
    Dir.mkdir(dir)
  rescue SystemCallError
  end
end

def ln_s(a, b)
  begin
    File.symlink(a, b)
  rescue Errno::EEXIST
  end
end

controllerdir = rootdir.join('app', 'controllers')
viewdir = rootdir.join('app', 'views', 'search_maps')

mkdirp(controllerdir)
mkdirp(viewdir)

ln_s(vendordir.join('app', 'views', 'cchdo_map', 'index.html.erb'),
     viewdir.join('index.html.erb'))
ln_s(vendordir.join('app', 'controllers', 'cchdo_map_controller.rb'),
     controllerdir.join('search_maps_controller.rb'))

symlinkDir(vendorpubdir.join('stylesheets'))
symlinkDir(vendorpubdir.join('javascripts'))
symlinkDir(vendorpubdir.join('images'))
