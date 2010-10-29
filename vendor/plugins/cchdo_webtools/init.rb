require 'cchdo_webtools'

dir = File.dirname(__FILE__)
public_dir = File.join(dir, 'lib', 'public')

FileUtils.ln_sf(File.join(public_dir, 'javascripts', 'cchdo.vis.js'), Rails.root.join('public', 'javascripts'))
FileUtils.ln_sf(File.join(public_dir, 'javascripts', 'jquery.form.js'), Rails.root.join('public', 'javascripts'))
FileUtils.ln_sf(File.join(public_dir, 'javascripts', 'map_search'), Rails.root.join('public', 'javascripts'))
FileUtils.ln_sf(File.join(public_dir, 'javascripts', 'vis.js'), Rails.root.join('public', 'javascripts'))
FileUtils.ln_sf(File.join(public_dir, 'stylesheets', 'overcast'), Rails.root.join('public', 'stylesheets'))
