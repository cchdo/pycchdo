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
  div.style.display = 'none';

  this.getPanes().floatPane.appendChild(div);

  var lastLatLng = null;
  var inMap = false;

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

  window.onkeydown = function (e) {
    var evt = e || window.event;
    if (evt.keyCode == 16 && inMap) {
      div.style.display = 'block';
      if (lastLatLng) {
        position(lastLatLng);
      }
    }
    if ((evt.metaKey || evt.ctrlKey) && evt.keyCode == 67) {
      // Copy to clipboard?
    }
  };
  window.onkeyup = function (e) {
    var evt = e || window.event;
    if (evt.keyCode == 16) {
      div.style.display = 'none';
    }
  };
  function position(latlng) {
    var px = self.getProjection().fromLatLngToDivPixel(latlng);
    div.style.top = px.y - div.offsetHeight + 'px';
    div.style.left = px.x + 'px';
    var map_width = self.getMap().getDiv().offsetWidth;
    if (px.y - div.offsetHeight < 0) {
      div.style.top = 0 + 'px';
    }
    if (px.x + div.offsetWidth > map_width) {
      div.style.left = px.x - div.offsetWidth + 'px';
    }
  }
};
LatLngTooltip.prototype.draw = function () {};
LatLngTooltip.prototype.onRemove = function () {
  google.maps.event.removeListener(this._inear);
  google.maps.event.removeListener(this._moveear);
  google.maps.event.removeListener(this._outear);
};
