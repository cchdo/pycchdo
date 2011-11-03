//http://earth-api-samples.googlecode.com/svn/trunk/demos/draw/index.html
var KMLMap = {
  cruises: {},
  Cruise: function() {
    this.track = null;
    this.start = null;
    this.stations = [];
  },
  hlrow: null,
  hlcruise: null
};

KMLMap.importKML = function(kml) {
  CCHDO.map_search.clearMarkers();
  var geoxml = new GGeoXml(kml);
  GEvent.addListener(map, 'addoverlay', function(overlay) { 
    //console.log(overlay); Do more for these
    if (overlay.name != null && overlay.name != 'Search Selection') {
      var ids = overlay.name.split(' ');
      var expo = ids[0], type = ids[1];
      if (KMLMap.cruises[expo] == null) { KMLMap.cruises[expo] = new KMLMap.Cruise(); }
      var cruise = KMLMap.cruises[expo];
      if (type == 'track') {
        cruise.track = overlay;
      } else if (type == 'start') {
        cruise.start = overlay;
      } else if (type == 'station') {
        cruise.stations.push(overlay);
      }
    }
  });
  GEvent.addListener(geoxml, 'load', function() {
    $('cruise_table_div').innerHTML = '<table id="cruise_table"><tr><th>(Line) Expocode</th><th>Ship</th><th>Country</th><th>PI</th><th>Begin Date</th></tr></table>';
    var table = $('cruise_table');
    var toggle = false;
    for (expo in KMLMap.cruises) {
      var cruise = KMLMap.cruises[expo];
      var row = table.insertRow(-1);
      var info = cruise.start.description.split(',');
      var link = document.createElement('a');
      link.href='/search?ExpoCode="'+expo+'"'
      link.appendChild(document.createTextNode(expo));
      row.insertCell(-1).appendChild(link);
      row.insertCell(-1).appendChild(document.createTextNode(info[0]));
      row.insertCell(-1).appendChild(document.createTextNode(info[1]));
      row.insertCell(-1).innerHTML = cruise.track.description;
      row.insertCell(-1).appendChild(document.createTextNode(info[2]));
      row.setAttribute('id', expo);
      (toggle) ? row.className = '_odd' : row.className = '_even';
      toggle = !toggle;
      KMLMap.installListeners(row, cruise);
    }
  });
  map.addOverlay(geoxml);
}

KMLMap.installListeners = function(row, cruise) {
  cruise.tableListener = GEvent.addDomListener(row, 'click', function() { KMLMap.hl(row, cruise); });
  cruise.startListener = GEvent.addListener(cruise.start, 'click', function() { KMLMap.hl(row, cruise); });
}

KMLMap.hl = function(row, cruise) {
  if (this.hlrow) { 
    if (this.hlrow == row) { return; }
    this.unhl(this.hlrow, this.hlcruise);
  }
  cruise.track.color = '#f6ff00';
  cruise.track.weight = 4;
  cruise.track.redraw(true);
  row.className = row.className.replace(ACTIVE_STR, '') + ACTIVE_STR;
  this.hlrow = row;
  this.hlcruise = cruise;
}

KMLMap.unhl = function(row, cruise) {
  cruise.track.color = '#06ff00';
  cruise.track.weight = 2;
  cruise.track.redraw(true);
  row.className = row.className.replace(ACTIVE_STR, '');
}

/* ge screen overlay */
function gescreenoverlay_rectcontrol() {
	var screenOverlay = ge.createScreenOverlay('');
	screenOverlay.setIcon(ge.createIcon(''));
	screenOverlay.getIcon().
		  setHref("http://www.google.com/intl/en_ALL/images/logo.gif");

	// Set screen position in pixels
	screenOverlay.getOverlayXY().setXUnits(ge.UNITS_PIXELS);
	screenOverlay.getOverlayXY().setYUnits(ge.UNITS_PIXELS);
	screenOverlay.getOverlayXY().setX(400);
	screenOverlay.getOverlayXY().setY(200);
	
	// Rotate around object's center point
	screenOverlay.getRotationXY().setXUnits(ge.UNITS_FRACTION);
	screenOverlay.getRotationXY().setYUnits(ge.UNITS_FRACTION);
	screenOverlay.getRotationXY().setX(0.5);
	screenOverlay.getRotationXY().setY(0.5);
	
	// Set object's size in pixels
	screenOverlay.getSize().setXUnits(ge.UNITS_PIXELS);
	screenOverlay.getSize().setYUnits(ge.UNITS_PIXELS);
	screenOverlay.getSize().setX(300);
	screenOverlay.getSize().setY(75);
	
	// Rotate 45 degrees
	screenOverlay.setRotation(45);
	
	ge.getFeatures().appendChild(screenOverlay);

	var overlay = ge.createScreenOverlay('');
	overlay.setIcon(ge.createIcon(''));
	overlay.getIcon().setHref('http://ushydro.ucsd.edu:3000/images/select_button_off.gif');
	overlay.getOverlayXY().setXUnits(ge.UNITS_PIXELS);
	overlay.getOverlayXY().setYUnits(ge.UNITS_PIXELS);
	overlay.getOverlayXY().setX(300);
	overlay.getOverlayXY().setY(300);
	overlay.getSize().setXUnits(ge.UNITS_PIXELS);
	overlay.getSize().setYUnits(ge.UNITS_PIXELS);
	overlay.getSize().setX(20);
	overlay.getSize().setY(20);
	ge.getFeatures().appendChild(overlay);
}
