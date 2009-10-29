/* Grat; adapted from www.bdcc.co.uk Bill Chadwick 2006 Free for any use */
function Grat() {
  this.latitudes = [];
  this.meridians = [];
  this.labels = [];
  this.last_maptype = null;
  this.last_zoom = -1;
  this.last_size = new google.maps.Size(0, 0);
  this.MINLAT = -90;
  this.MAXLAT = 90;
  this.MINLNG = -180;
  this.MAXLNG = 180;
  this.weight = 0.5;
  this.zoom_lim = 6;
}

Grat.prototype = new google.maps.Overlay();
Grat.prototype.initialize = function(map) { this.map = map; }
Grat.prototype.get_color = function() { return this.map.getCurrentMapType().getTextColor(); };
Grat.prototype.make_label = function(x, y, text) {
  var d = document.createElement('div');
  var s = d.style;
  s.position = 'absolute';
  s.left = x+'px';
  s.top = y+'px';
  s.color = this.get_color();
  s.fontSize = 'x-small';
  d.innerHTML = text;
  return d;
};
Grat.prototype.remove_lines = function() {
  try {
    while (this.latitudes.length > 0) { this.map.removeOverlay(this.latitudes.pop()); }
    while (this.meridians.length > 0) { this.map.removeOverlay(this.meridians.pop()); }
  } catch(e) {
    google.maps.Log.write('An error occured during graticule removal: '+e);
  }
};
Grat.prototype.remove_labels = function() {
  var p = this.map.getPane(G_MAP_MAP_PANE);
  while (this.labels.length > 0) { p.removeChild(this.labels.pop()); }
};
Grat.prototype.remove = function() {
  if (this.map.getZoom() != this.last_zoom) {  }
  this.remove_labels();
};
Grat.prototype.gridint = function(d) {
  var num_lines = 10;
  d = Math.ceil(d / num_lines * 6000) / 100;
  return ((d <= 0.06) ? 0.06 :
          (d <= 0.12) ? 0.12 :
          (d <= 0.3) ? 0.3 :
          (d <= 0.6) ? 0.6 :
          (d <= 1.2) ? 1.2 :
          (d <= 3) ? 3 :
          (d <= 6) ? 6 :
          (d <= 12) ? 12 :
          (d <= 30) ? 30 :
          (d <= 60) ? 60 :
          (d <= 120) ? 120 :
          (d <= 300) ? 300 :
          (d <= 600) ? 600 :
          (d <= 1200) ? 1200 :
          (d <= 1800) ? 1800 :
          2700)/60;
};
Grat.prototype.precisify = function(l, d) {
  return l.toFixed(
  (d >= 1) ? 0 :
  (d >= 0.1) ? 1 :
  (d >= 0.001) ? 2 :
  3);
};
Grat.prototype.redraw = function(force) {
  var G = google.maps;
  var maptype = this.map.getCurrentMapType();
  var zoom = this.map.getZoom();
  var size = this.map.getSize();
  var pane = this.map.getPane(G_MAP_MAP_PANE);
  var bounds = this.map.getBounds();
  var color = this.get_color();

  /* Find grid interval */
  var sw = bounds.getSouthWest();
  var ne = bounds.getNorthEast();
  var dlng = this.gridint((ne.lng() > sw.lng()) ? ne.lng() - sw.lng(): 360-sw.lng()+ne.lng());
  var dlat = this.gridint(ne.lat()-sw.lat());

  var llat = this.MINLAT;
  var ulat = this.MAXLAT;
  var llng = this.MINLNG;
  var ulng = this.MAXLNG;
  while (llat < sw.lat()+dlat) { llat += dlat; }
  while (ulat > ne.lat()) { ulat -= dlat; }
  while (llng < sw.lng()) { llng += dlng; }
  while (ulng > ne.lng()) { ulng -= dlng; }
  if (llng > ulng) { ulng += 360; }

  this.remove_labels();

  for (var lng = llng-dlng; lng < ulng+dlng; lng += dlng) {
    var px = this.map.fromLatLngToDivPixel(new G.LatLng(llat, lng));
    if (lng == llng) { px.x += 10; } /* offset where latlngs cross */
    var l = this.make_label(px.x+6, px.y, this.precisify((lng > 180) ? lng - 360 : lng, dlng));
    pane.appendChild(l);
    this.labels.push(l);
  }

  for (var lat = llat-dlat; lat < ulat+dlat; lat += dlat) {
    var px = this.map.fromLatLngToDivPixel(new G.LatLng(lat, llng));
    if (lat == llat) { px.y += 10; } /* offset where latlngs cross */
    var l = this.make_label(px.x+6, px.y, this.precisify(lat, dlat));
    pane.appendChild(l);
    this.labels.push(l);
  }

  var crit_zoom = zoom >= this.zoom_lim; /* point where drawing vast numbers of overlays is slow. */
  if (zoom != this.last_zoom || maptype != this.last_maptype || size.width != this.last_size.width || size.height != this.last_size.height || crit_zoom) {
    this.remove_lines();
    for (var lng = (crit_zoom ? llng : this.MINLNG); lng < (crit_zoom ? ulng : this.MAXLNG); lng += dlng) {
      var meridian = new G.Polyline([new G.LatLng(this.MINLAT, lng), new G.LatLng(this.MAXLAT, lng)], color, this.weight, 1);
      this.meridians.push(meridian);
      this.map.addOverlay(meridian);
    }

    for (var lat = (crit_zoom ? llat : this.MINLAT); lat < (crit_zoom ? ulat : this.MAXLAT); lat += dlat) {
      /* Need to draw both ways in order for it to go around the world */
      var latitude = new G.Polyline([new G.LatLng(lat, this.MINLNG), new G.LatLng(lat, 0)], color, this.weight, 1);
      this.latitudes.push(latitude);
      this.map.addOverlay(latitude);
      var latitude = new G.Polyline([new G.LatLng(lat, 0), new G.LatLng(lat, this.MINLNG)], color, this.weight, 1);
      this.latitudes.push(latitude);
      this.map.addOverlay(latitude);
    }
    this.last_maptype = maptype;
    this.last_size = size;
    this.last_zoom = zoom;
  }
}
