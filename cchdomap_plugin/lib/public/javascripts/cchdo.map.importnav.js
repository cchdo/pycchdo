function ImportNAV() {
}

ImportNAV.prototype.importURL = function (url, callback) {
  $.ajax({
    type: 'GET',
    dataType: 'text',
    url: CM.host + '/' + url,
    success: function (nav) {
      var coords = $.map(nav.split('\n'), function (coordstr) {
        var coord = coordstr.replace(/^\s+/, '').split(/\s+/);
        if (coord.length < 2) {
          return null;
        }
        var lng = parseFloat(coord[0]);
        var lat = parseFloat(coord[1]);
        if (isNaN(lat) || isNaN(lng)) {
          return null;
        }
        return new google.maps.LatLng(lat, lng);
      });
      callback({mapsLayer: new google.maps.Polyline({path: coords})});
    },
    error: function () {
      callback({mapsLayer: null});
    }
  });
};
