Number.prototype.mod = function (n) {
  // http://javascript.about.com/od/problemsolving/a/modulobug.htm
  // Corrects Javascript modulo expectations for negative numbers.
  return ((this % n) + n) % n;
}

function ETOPOMapType() {}

ETOPOMapType.prototype.name = "ETOPO";
ETOPOMapType.prototype.alt = "ETOPO base map";
ETOPOMapType.prototype.tileSize = new google.maps.Size(256, 256);
ETOPOMapType.prototype.maxZoom = 5;
ETOPOMapType.prototype.baseURI = 'http://terra.ucsd.edu/gmaps_tiles/cchdo/';

ETOPOMapType.prototype.getTile = function(coord, zoom, ownerDocument) {
  var div = ownerDocument.createElement('DIV');
  var s = div.style;
  s.width = this.tileSize.width + 'px';
  s.height = this.tileSize.height + 'px';

  var n = Math.pow(2, zoom);
  var x = coord.x.mod(n);
  var y = coord.y;

  if (y < 0 || y > n - 1) {
    s.background = "#000000";
  } else {
    s.background = ["url('", this.baseURI,
                    "cchdo_z", zoom, "x", x, "y", y, ".png')"].join('');
  }
  return div;
};
