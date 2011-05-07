function ImportKML() {
}

ImportKML.prototype.importURL = function (url, map_callback, earth_callback) {
  var self = this;
  var layer = new google.maps.KmlLayer(CM.host + '/' + url);
  google.maps.event.addListenerOnce(layer, 'earth_kml_ready', function (kmlobj) {
    self._getTour(kmlobj, function (tour) {
      earth_callback(kmlobj, tour);
    });
  });
  map_callback(layer);
};

ImportKML.prototype._getTour = function (kmlroot, callback) {
  CM.earth._withEarth(function (ge) {
    var found = false;
    new GEarthExtensions(ge).dom.walk({
      rootObject: kmlroot,
      features: true,
      geometries: false,
      visitCallback: function (context) {
        if (this.getType() == 'KmlTour') {
          found = true;
          callback(this);
          // Stop walking
          return false;
        }
      }
    });
    if (!found) {
      callback(null);
    }
  });
};
