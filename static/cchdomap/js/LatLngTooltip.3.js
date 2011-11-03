function LatLngTooltip(map) {
  this.setMap(map);
}
LatLngTooltip.prototype = new google.maps.OverlayView();
LatLngTooltip.prototype.onAdd = function () {
  var self = this;

  var div = document.createElement('DIV');
  div.style.border = '1px solid #000000';
  div.style.background = '#ffffdd';
  div.style.padding = '0.2em';
  div.style.position = 'absolute';
  div.style.whiteSpace = 'nowrap';
  div.style.fontFamily = 'Helvetica, sans-serif';
  div.style.fontSize = '0.8em';
  div.style.visibility = 'hidden';

  this.getPanes().floatPane.appendChild(div);

  var lastLatLng = null;
  var inMap = false;

  var map = this.getMap();

  this._moveear = google.maps.event.addListener(map, 'mousemove', mousemoved);
  function mousemoved(mouseevent) {
    var latlng = mouseevent.latLng;
    lastLatLng = latlng;
    div.innerHTML = [latlng.lat().toFixed(6), latlng.lng().toFixed(6)].join(', ');
    position(latlng);
  }
  this._inear = google.maps.event.addListener(map, 'mouseover', function () {
    inMap = true;
  });
  this._outear = google.maps.event.addListener(map, 'mouseout', function () {
    inMap = false;
  });

  document.onkeydown = function (e) {
    var evt = e || window.event;
    if (evt.keyCode == 16 && inMap) {
      div.style.visibility = 'visible';
      if (lastLatLng) {
        position(lastLatLng);
      }
    }
    if ((evt.metaKey || evt.ctrlKey) && evt.keyCode == 67) {
      // Copy to clipboard?
    }
  };
  document.onkeyup = function (e) {
    var evt = e || window.event;
    if (evt.keyCode == 16) {
      div.style.visibility = 'hidden';
    }
  };
  function position(latlng) {
    //console.log('repositioning tip to latlng', latlng.lat(), latlng.lng());
    var px = self.getProjection().fromLatLngToDivPixel(latlng);
    window.overlay = self;
    //console.log('px=', px.y, px.x);
    var mapdiv = self.getMap().getDiv();
    var top = px.y - div.offsetHeight;
    var left = px.x;
    var map_width = mapdiv.offsetWidth;
    //console.log(px.x, div.offsetWidth, map_width);
    if (px.x + div.offsetWidth > map_width) {
      left = px.x - div.offsetWidth;
      //console.log(px.x, div.offsetWidth);
    }
    //console.log('ie.', top, left);
    div.style.top = top + 'px';
    div.style.left = left + 'px';
  }
};
LatLngTooltip.prototype.draw = function () {};
LatLngTooltip.prototype.onRemove = function () {
  google.maps.event.removeListener(this._inear);
  google.maps.event.removeListener(this._moveear);
  google.maps.event.removeListener(this._outear);
};
