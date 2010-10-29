function defaultTo(x, d) { return x ? x : d; }
Element.prototype.empty = function() {
  while (this.childNodes.length > 0) {
    this.removeChild(this.childNodes[0]);
  }
  return this;
};

var Vis = defaultTo(Vis, {});

/* Vis: Map
 *
 * Dependencies:
 *   google.maps (v2)
 *   google.visualization (v1)
 *
 * Map(container)
 *  - container is the HTML DOM element that will contain the map
 *    Vis.
 * Map.draw(data, options)
 *  Draws markers for each row and initially centers viewport to center on and
 *  contain all markers. 
 *  - data (Vis.{DataView, DataTable})
 *  - options (object)
 *    - mapOpts: options for maps.Map2 ({}) Defaults to none.
 *    - polyline: options for a maps.Polyline connecting the markers
 *      If defined, a polyline will be drawn connecting markers. ({}) Defaults
 *      to none.
 *    - markerStyle: options for the google.maps.Marker that are not selected.
 *      ({}) Defaults to {icon: G_DEFAULT_ICON, zIndexProcess: (function that
 *      bumps the selected markers to the top) and tries to order southern
 *      markers higher)}
 *    - markerStyleSelectedImage: a URL to the image to use when the marker is 
 *      selected (URL) Defaults to
 *      http://www.google.com/uds/samples/places/temp_marker.png
 *    - infoWindowHook: HTML string to put in info window
 *      (function(row, marker, data)) Defaults to null.
 *    - setupMap: a hook function called with the drawn map
 *      (function(maps.Map2)) Defaults to none.
 */
Vis.Map = function(container) {
  var self = this;
  if (!google.maps) {
    alert('Vis.Map needs the google.maps API v2 to be loaded.');
    return;
  }
  var GM = google.maps;
  if (!GM.BrowserIsCompatible()) {
    alert('Vis.Map needs a browser compatible with google.maps v2.');
    return;
  }
  window.onunload = GM.Unload;
  this.container = container;
  this.selection = [];
  this.map = null;
  this.data = null;
  this.geocoder = null;
  this.markers = [];
  function zIndexProcess(marker) {
    var scale = 1000; // Scaling for more sigfigs
    if (self.selection.length > 0 && marker.dataRow == self.selection[0].row) {
      return 181*scale;
    }
    return Math.round(90-marker.getLatLng().lat()*scale);
  };
  this.defaultMarkerStyle = {icon: new GM.Icon(G_DEFAULT_ICON),
                             zIndexProcess: zIndexProcess};
  this.defaultMarkerStyleSelectedImage =
    'http://www.google.com/uds/samples/places/temp_marker.png';
  this.markerStyle = this.defaultMarkerStyle;
  this.markerStyleSelectedImage = this.defaultMarkerStyleSelectedImage;
};
Vis.Map.prototype.draw = function(data, options) {
  var self = this;
  var GM = google.maps;
  this.data = data;
  
  /* Clear everything first */
  this.container.empty();

  /* Build point markers and bounds */
  var latlngs = [];
  var bounds = new GM.LatLngBounds();
  var geocoder = null;
  if (data.getColumnType(0) == 'string') {
    this.geocoder = defaultTo(this.geocoder, new GM.ClientGeocoder());
  }
  for (var i=0; i<data.getNumberOfRows(); i++) {
    var latlng = null;
    if (geocoder) {
      var sync = true;
      function callback(glatlng) {
        latlng = glatlng;
        sync = false;
      }
      geocoder.getLatLng(data.getValue(i, 0), callback);
      while (sync) {}
    } else {
      latlng = new GM.LatLng(data.getValue(i, 0), data.getValue(i, 1));
    }
    latlngs.push(latlng);
    bounds.extend(latlng);
    var marker = new GM.Marker(latlng, defaultTo(options.defaultMarkerStyle,
                                                 this.markerStyle));
    marker.dataRow = i;
    this.markers.push(marker);
  }
  this.markerStyleSelectedImage = defaultTo(options.markerStyleSelectedImage,
                                            this.defaultMarkerStyleSelectedImage);

  this.infoWindowHook = defaultTo(options.infoWindowHook, null);
  
  /* Set up map */
  var m = this.map = new GM.Map2(this.container, options.mapOpts || null);
  m.setCenter(bounds.getCenter(),
              m.getCurrentMapType().getBoundsZoomLevel(bounds, m.getSize()));
  m.setMapType(defaultTo(options.mapType, G_SATELLITE_MAP));
  if (options.setupMap) { options.setupMap(m); }

  /* Add the markers */
  for (var i=0; i<this.markers.length; i++) { m.addOverlay(this.markers[i]); }

  /* Add the polyline */
  if (options.polyline) {
    var opts = options.polyline;
    this.polyline = new GM.Polyline(latlngs, opts.color, opts.weight,
                                    opts.opacity, opts.opts);
    m.addOverlay(this.polyline);
  }

  /* Listen for clicks on markers */
  GM.Event.addListener(m, 'click', function(overlay, latlng, overlaylatlng) {
    if (overlay != null && overlay instanceof GM.Marker) {
      if (window.event.shiftKey) {
        var selection = self.getSelection();
        selection.push({row: overlay.dataRow});
        self.setSelection(selection);
      } else {
        self.setSelection([{row: overlay.dataRow}]);
      }
      google.visualization.events.trigger(self, 'select', {});
    }
  });
};
Vis.Map.prototype.select = function(row) {
  var marker = this.markers[row];
  marker.setImage(this.markerStyleSelectedImage);
  if (this.infoWindowHook) {
    marker.openInfoWindowHtml(this.infoWindowHook(row, marker, this.data));
  } else {
    var str = '<ul>';
    str += '<li><strong>Lat, Lng</strong> '+marker.getLatLng().toString()+'</li>';
    for (var i = this.geocoder ? 0 : 2; i<this.data.getNumberOfColumns(); i++) {
      str += '<li><strong>'+this.data.getColumnLabel(i)+'</strong> '+
             this.data.getValue(row, i)+'</li>';
    }
    str += '</ul>';
    marker.openInfoWindowHtml(str);
  }
};
Vis.Map.prototype.deselect = function(row) {
  var marker = this.markers[row];
  marker.setImage(this.markerStyle.icon.image);
  marker.closeInfoWindow();
};
Vis.Map.prototype.getSelection = function() {
  return this.selection;
};
Vis.Map.prototype.setSelection = function(selection_array) {
  for (var i=0; i<this.selection.length; i++) {
    this.deselect(this.selection[i].row);
  }
  for (var i=0; i<selection_array.length; i++) {
    this.select(selection_array[i].row);
  }
  this.selection = selection_array;
};
