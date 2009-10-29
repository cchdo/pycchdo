/* Dependencies: google.maps */

var CCHDO = CCHDO ? CCHDO : {};
CCHDO.Util = {};
CCHDO.Util.get_abs_mouse_position = function(e) {
  var posX = 0;
  var posY = 0;
  if (!e) { e = window.event; }
  if (e.pageX || e.pageY) {
    posX = e.pageX;
    posY = e.pageY;
  } else if (e.clientX || e.clientY){
    var dE = document.documentElement;
    posX = e.clientX + (dE.scrollLeft ? dE.scrollLeft : document.body.scrollLeft);
    posY = e.clientY + (dE.scrollTop ? dE.scrollTop : document.body.scrollTop);
  }	
  return new google.maps.Point(posX, posY);  
};
CCHDO.Util.get_dom_pos = function(element) {
  var leftPos = element.offsetLeft;        // initialize var to store calculations
  var topPos = element.offsetTop;          // initialize var to store calculations
  var parElement = element.offsetParent;   // identify first offset parent element  
  while (parElement !== null ) {           // move up through element hierarchy
    leftPos += parElement.offsetLeft;      // appending left offset of each parent
    topPos += parElement.offsetTop;  
    parElement = parElement.offsetParent;  // until no more offset parents exist
  }
  return new google.maps.Point(leftPos, topPos);
};
CCHDO.Util.apply_styles = function(domelem, styles) {
  for (var s in styles) { domelem.style[s] = styles[s]; }
};
CCHDO.Util.get_radius_coord = function(center, radius) {
  if (radius <= 0) { return center; }
  var EARTH_RADIUS = 6378.137; //km
  var arclen = radius / EARTH_RADIUS;
  var deltalng = Math.acos((Math.cos(arclen) - Math.pow(Math.sin(center.latRadians()), 2)) /
                           Math.pow(Math.cos(center.latRadians()), 2));
  return new google.maps.LatLng(center.lat(), (center.lngRadians() + deltalng) * 180 / Math.PI);
};
CCHDO.Util.get_circle_on_map_from_pts = function(map, center, outer, color) {
  var radius = Math.sqrt(Math.pow(center.x - outer.x, 2) + Math.pow(center.y - outer.y, 2));
  var NUMSIDES = 20;
  var SIDELENGTH = 18;
  var sideLengthRad = SIDELENGTH * Math.PI/180;
  var maxRad = (NUMSIDES+1) * sideLengthRad;
  var pts = [];
  for (var aRad=0; aRad < maxRad; aRad+=sideLengthRad) {
    var pixelX = center.x + radius*Math.cos(aRad);
    var pixelY = center.y + radius*Math.sin(aRad);
    pts.push(map.fromContainerPixelToLatLng(new google.maps.Point(pixelX, pixelY)));
  }
  
  return new google.maps.Polygon(pts, color, 2, 0.5, color, 0.5);
};
CCHDO.Util.get_circle_on_map_from_latlngs = function(map, centerlatlng, outerlatlng, color) {
  var center = map.fromLatLngToContainerPixel(centerlatlng);
  var outer = map.fromLatLngToContainerPixel(outerlatlng);
  return CCHDO.Util.get_circle_on_map_from_pts(map, center, outer, color);
};

function DragTool() {}

DragTool.prototype.initialize = function() {
  var G = this.globals;
  G.ear = document.createElement('div');
  G.ear.id = 'dragtool-ear';
  G.ear.onselectstart = function() {return false;}; /* disable text selection for IE on ear */
  CCHDO.Util.apply_styles(G.ear, {position: 'absolute', display: 'none',
                               overflow: 'hidden', cursor: 'crosshair',
                               zIndex: 200, opacity: G.style.opacity,
                               background: G.style.listenColor});
  var mapDiv = G.map.getContainer();
  G.mapPosition = CCHDO.Util.get_dom_pos(mapDiv);
  mapDiv.appendChild(G.ear);
  
  var me = this;
  var GMEaD = google.maps.Event.addDomListener;
  GMEaD(G.ear, 'mousedown', function(e) { me.mousedown_(e); });
  GMEaD(G.ear, 'mousemove', function(e) {
    if (G.dragging) { me.drag_(e);
    } else { me.mousemove_(e); }
  });
  GMEaD(G.ear, 'mouseup', function(e) { me.mouseup_(e); });
};

DragTool.prototype.mousedown_ = function(e){
  var G = this.globals;
  G.dragging = true;
  this.erase();

  /* update start position */
  G.coords[0] = G.coords[1] = this.get_mouse_rel_pos_(e);

  this.redraw();

  if (G.hooks.dragstart) { G.hooks.dragstart(this.get_bounds()); }
};

DragTool.prototype.mousemove_ = function(e) {
  var G = this.globals;
  if (G.hooks.moving) { G.hooks.moving(this.get_mouse_rel_pos_(e)); }
};

DragTool.prototype.drag_ = function(e){
  var G = this.globals;
  G.coords[1] = this.get_mouse_rel_pos_(e);
  this.redraw();

  if (G.hooks.dragging) { G.hooks.dragging(this.get_bounds()); }
};

DragTool.prototype.mouseup_ = function(e) {
  var G = this.globals;
  G.dragging = false;

  G.coords[1] = this.get_mouse_rel_pos_(e);
  this.redraw();

  this.close_ear();

  if (G.hooks.dragend) { G.hooks.dragend(this.get_bounds()); }
};

DragTool.prototype.erase = function() {
	var G = this.globals;
	if (G.marker) {
		G.map.removeOverlay(G.marker);
		G.marker = null;
	}
};

DragTool.prototype.redraw = function() {
  var G = this.globals;
  /* Save calculation before the erase (it clobbers G.marker) to prevent flashing. */
  var marker = this.get_polygon();
  this.erase();
  G.marker = marker;
  G.map.addOverlay(G.marker);
};

DragTool.prototype.map_width = function() { return this.globals.map.getSize().width; };
DragTool.prototype.map_height = function() { return this.globals.map.getSize().height; };

DragTool.prototype.sync_ear = function() {
  CCHDO.Util.apply_styles(this.globals.ear,
    {top: '0', left: '0', width: this.map_width()+'px', height: this.map_height()+'px'});
};

DragTool.prototype.open_ear = function(){
  var G = this.globals;
  G.mapPosition = CCHDO.Util.get_dom_pos(G.map.getContainer());
  this.sync_ear();
  CCHDO.Util.apply_styles(G.ear, {display: 'block'});
};

DragTool.prototype.close_ear = function() {
  CCHDO.Util.apply_styles(this.globals.ear, {display: 'none'});
};

DragTool.prototype.get_mouse_rel_pos_ = function(e) {
  var G = this.globals;
  var pos = CCHDO.Util.get_abs_mouse_position(e);
  var mapPos = G.mapPosition;
  return G.map.fromContainerPixelToLatLng(new google.maps.Point(pos.x - mapPos.x, pos.y - mapPos.y));
};

/* DragRectangle */
function DragRectangle(map, hooks) {
  var G = this.globals = {
    dragging: false,
    mapPosition: null,
    map: map,
    ear: null,
    marker: null,
    coords: [new google.maps.LatLng(0, 0), new google.maps.LatLng(0, 0)]
  };
  G.style = {
    opacity: 0.2,
    listenColor: '#888888',
    markerColor: '#ff0000',
    markerWidth: 2
  };
  G.hooks = hooks ? hooks : {};
  this.initialize();
}
DragRectangle.prototype = new DragTool();
DragRectangle.prototype.constructor = DragRectangle;

/* hooks:
 *   listening
 *   moving(google.maps.Point)
 *   dragstart(google.maps.LatLngBounds)
 *   dragging(google.maps.LatLngBounds)
 *   dragend(google.maps.LatLngBounds)
 *   ignoring */
DragRectangle.prototype.set_bounds = function(glatlngbounds) {
  var G = this.globals;
  G.coords[0] = glatlngbounds.getSouthWest();
  G.coords[1] = glatlngbounds.getNorthEast();
};

DragRectangle.prototype.get_bounds = function() {
  var G = this.globals;

  /* Normalize the 4 start and end point cases to the case where it is sw and ne. */
  var st = G.map.fromLatLngToContainerPixel(G.coords[0]);
  var en = G.map.fromLatLngToContainerPixel(G.coords[1]);
  var swpt = G.map.fromLatLngToContainerPixel(G.coords[0]);
  var nept = G.map.fromLatLngToContainerPixel(G.coords[1]);
  if (st.x > en.x) { /* went left */
	  if (st.y < en.y) { /* went down (picture coord-sys) */
	    swpt = en;
	    nept = st;
	  } else {
	    swpt = new google.maps.Point(en.x, st.y);
	    nept = new google.maps.Point(st.x, en.y);
	  }
  } else {
	  if (st.y < en.y) {
	    swpt = new google.maps.Point(st.x, en.y);
	    nept = new google.maps.Point(en.x, st.y);
	  } else { /* Already normal */ }
  }

  /* Get LatLng of start and end pts */
	var sw = G.map.fromContainerPixelToLatLng(swpt);
	var ne = G.map.fromContainerPixelToLatLng(nept);

  return new google.maps.LatLngBounds(sw, ne);
};

/* Provides a polygon with padding vertices at points in between the four
 * corners to prevent snapping the wrong way around the world. */
DragRectangle.prototype.get_polygon = function(bounds) {
  bounds = this.get_bounds();
  var G = this.globals;
  var GML = google.maps.LatLng
  var center = bounds.getCenter();
  var interlng = center.lng();
  var interlat = center.lat();
  
  var ne = bounds.getNorthEast();
  var sw = bounds.getSouthWest();
  var nw = new GML(ne.lat(), sw.lng());
  var se = new GML(sw.lat(), ne.lng());

  var n = new GML(nw.lat(), interlng);
  var s = new GML(sw.lat(), interlng);
  var e = new GML(interlat, se.lng());
  var w = new GML(interlat, sw.lng());
  return new google.maps.Polygon([nw, n, ne, e, se, s, sw, w, nw],
                                 G.style.markerColor, G.style.markerWidth, 0.6);
};

/* DragCircle */
function DragCircle(map, hooks) {
  var G = this.globals = {
    dragging: false,
    mapPosition: null,
    map: map,
    ear: null,
    marker: null,
    coords: [new google.maps.LatLng(0, 0), new google.maps.LatLng(0, 0)]
  };
  G.style = {
    opacity: 0.2,
    listenColor: '#888888',
    markerColor: '#0088ff',
    markerWidth: 2
  };
  G.hooks = hooks ? hooks : {};
  this.initialize();
}
DragCircle.prototype = new DragTool();
DragCircle.prototype.constructor = DragCircle;

/* hooks:
 *   listening
 *   moving(google.maps.Point)
 *   dragstart({google.maps.LatLng, Number})
 *   dragging({google.maps.LatLng, Number})
 *   dragend({google.maps.LatLng, Number})
 *   ignoring */
/* The circle defined by the two coords has the radius specified in the horizontal axis toward the east */
DragCircle.prototype.set_bounds = function(center, radius) {
  var G = this.globals;
  G.coords[0] = center;
  G.coords[1] = CCHDO.Util.get_radius_coord(center, radius);
};

DragCircle.prototype.get_bounds = function() {
  var G = this.globals;
  return {latlng: G.coords[0], radius: this.radius()};
};

DragCircle.prototype.radius = function() {
  var G = this.globals;
  var center = G.coords[0];
  var outer = G.coords[1];
  return center.distanceFrom(outer)/1000;
};

DragCircle.prototype.get_polygon = function() {
  var G = this.globals;
  return CCHDO.Util.get_circle_on_map_from_latlngs(G.map, G.coords[0], G.coords[1], G.style.markerColor);
};
