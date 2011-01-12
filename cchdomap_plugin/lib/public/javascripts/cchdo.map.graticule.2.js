/*Graticule; adapted from www.bdcc.co.uk Bill Chadwick 2006 Free for any use*/
function Graticule(sexagesimal) {
    this.sex_ = sexagesimal || false;//default is decimal intervals
}
Graticule.prototype = new GOverlay();
Graticule.prototype.initialize = function(map) {
  this.map_ = map;
  this.divs_ = []; //array for line and label divs
  this.mapPane = this.map_.getPane(G_MAP_MARKER_SHADOW_PANE);
}
Graticule.prototype.copy = function() { return new Graticule(this.sex_); }
Graticule.prototype.remove = function() {
  try{for(var i=0; i<this.divs_.length; i++) this.mapPane.removeChild(this.divs_[i]);} catch(e){}
}
Graticule.prototype.latLngToPixel = function(lat, lng) { return this.map_.fromLatLngToDivPixel(new GLatLng(lat,lng)); }
Graticule.prototype.addDiv = function(div) { this.mapPane.insertBefore(div,null); this.divs_.push(div); }
Graticule.prototype.decToSex = function(d) {
  var degs = Math.floor(d); 
  var mins = ((Math.abs(d)-degs)*60.0).toFixed(2);
  if(mins == "60.00"){ degs += 1.0; mins = "0.00"; }
  return degs + ":" + mins; 
}
Graticule.prototype.makeLabel = function(x, y, text) {
  var d = document.createElement("DIV");
  var s = d.style;
  s.position = "absolute";
  s.left = x.toString() + "px";
  s.top = y.toString() + "px";
  s.color = this.color_;
  s.width = '3em';
  s.fontSize = 'x-small';
  d.innerHTML = text;
  return d;
};
// Redraw the graticule based on the current projection and zoom level
Graticule.prototype.redraw = function(force) {
  this.remove(); //clear old
  this.color_ = this.map_.getCurrentMapType().getTextColor(); //best color for writing on the map

  var bnds = this.map_.getBounds(); //determine graticule interval
  var sw = bnds.getSouthWest(); var ne = bnds.getNorthEast();
  var l = sw.lng(); var b = sw.lat();
  var r = ne.lng(); var t = ne.lat();

  //sanity
  if(b < -90.0) b = -90.0;
  if(t > 90.0) t = 90.0;
  if(l < -180.0) l = -180.0;  
  if(r > 180.0) r = 180.0;
  if(l == r){ l = -180.0; r = 180.0; }
  if(t == b){ b = -90.0; t = 90.0; }

  //grid interval in degrees
  var dLat = this.gridIntervalMins(t-b)/60;
  var dLng = 1/60; 
  if(r>l) dLng *= this.gridIntervalMins(r-l);
  else dLng *= this.gridIntervalMins((180-l)+(r+180));

  //round iteration limits to the computed grid interval
  l = Math.floor(l/dLng)*dLng;
  b = Math.floor(b/dLat)*dLat;
  t = Math.ceil(t/dLat)*dLat;
  r = Math.ceil(r/dLng)*dLng;

  //Sanity
  if(b < -90.0) b = -90;
  if(t > 90.0) t = 90;
  if(l < -180.0) l = -180.0;  
  if(r > 180.0) r = 180.0;
  
  // digits after DP for decimal labels
  var latDecs = this.gridPrecision(dLat);
  var lonDecs = this.gridPrecision(dLng);
  
  this.divs_ = new Array();

  //min and max x and y pixel values for graticule lines
  var pbl = this.latLngToPixel(b,l);
  var ptr = this.latLngToPixel(t,r);
  this.maxX = ptr.x; this.maxY = pbl.y;
  this.minX = pbl.x; this.minY = ptr.y;

  //labels on second column to avoid peripheral controls
  var y = this.latLngToPixel(b+dLat+dLat,l).y + 2;//coord for label
  var lo = l;//copy to save original
  if(r<lo) r += 360.0;

  //lngs
  var crosslng = lo+2*dLng;
  for(; lo<r; lo+=dLng){//lo<r to skip printing 180/-180
    if (lo > 180.0){ r -= 360.0; lo -= 360.0; }	
    var px = this.latLngToPixel(b,lo).x;
    this.addDiv(this.createVLine(px));
    
    var text;
    if(this.sex_) text = this.decToSex(lo);
    else text = lo.toFixed(lonDecs);//only significant digits
    if(lo != crosslng) {
      this.addDiv(this.makeLabel(px+3, y, text));
    } else {
      this.addDiv(this.makeLabel(px+17, y-3, text));
    }
  }
      
  //labels on second row; avoid controls
  var x = this.latLngToPixel(b,l+dLng+dLng).x + 3;
  
  //lats
  var crosslat = b+2*dLat;
  for(; b<=t; b+=dLat){
    var py = this.latLngToPixel(b,l).y;
    if(r <= l) {
      this.addDiv(this.createHLine3(b)); //draw lines across the dateline or world scale zooms
      //console.log('hl#######');
    } else {
      this.addDiv(this.createHLine3(b)); //draw lines across the dateline or world scale zooms
      //this.addDiv(this.createHLine(py));
      //console.log('hl');
    }
    		
    var text;
    if(this.sex_) text = this.decToSex(b);
    else text = b.toFixed(latDecs);//only significant digits
    if(b != crosslat){ 
      this.addDiv(this.makeLabel(x, py+2, text));
    } else {
      this.addDiv(this.makeLabel(x, py+7, text));
    }
  }
}

Graticule.prototype.hide = Graticule.prototype.remove;
Graticule.prototype.show = Graticule.prototype.redraw;

Graticule.prototype.gridIntervalMins = function(dDeg) {
  if(this.sex_) return this.gridIntervalSexMins(dDeg)
  return this.gridIntervalDecMins(dDeg)
}

//calculate rounded graticule interval in decimals of degrees for supplied lat/lon span
//return is in minutes
Graticule.prototype.gridIntervalDecMins = function(dDeg) {
  var numLines = 10;
  dDeg = Math.ceil(dDeg/numLines*6000)/100;
	if(dDeg <= 0.06) return 0.06;//0.001 degrees
	else if(dDeg <= 0.12) return 0.12;//0.002 degrees
	else if(dDeg <= 0.3) return 0.3;//0.005 degrees
	else if(dDeg <= 0.6) return 0.6;//0.01 degrees
	else if(dDeg <= 1.2) return 1.2;//0.02 degrees
	else if(dDeg <= 3) return 3;//0.05 degrees
	else if(dDeg <= 6) return 6;//0.1 degrees
	else if(dDeg <= 12) return 12;//0.2 degrees
	else if(dDeg <= 30) return 30;//0.5
	else if(dDeg <= 60) return 60;//1
	else if(dDeg <= (60*2)) return 60*2;
	else if(dDeg <= (60*5)) return 60*5;
	else if(dDeg <= (60*10)) return 60*10;
	else if(dDeg <= (60*20)) return 60*20;
	else if(dDeg <= (60*30)) return 60*30;
	else return 60*45;
}

//calculate rounded graticule interval in Minutes for supplied lat/lon span
//return is in minutes
Graticule.prototype.gridIntervalSexMins = function(dDeg) {
  var numLines = 10;
  dDeg = Math.ceil(dDeg/numLines*6000)/100;
  if(dDeg <= 0.01) return 0.01;//minutes 
  else if(dDeg <= 0.02) return 0.02;
  else if(dDeg <= 0.05) return 0.05;
  else if(dDeg <= 0.1) return 0.1;
  else if(dDeg <= 0.2) return 0.2;
  else if(dDeg <= 0.5) return 0.5;
  else if(dDeg <= 1.0) return 1.0;
  else if(dDeg <= 3) return 3;//0.05 degrees
  else if(dDeg <= 6) return 6;//0.1 degrees
  else if(dDeg <= 12) return 12;//0.2 degrees
  else if(dDeg <= 30) return 30;//0.5
  else if(dDeg <= 60) return 60;//1
  else if(dDeg <= (60*2)) return 60*2;
  else if(dDeg <= (60*5)) return 60*5;
  else if(dDeg <= (60*10)) return 60*10;
  else if(dDeg <= (60*20)) return 60*20;
  else if(dDeg <= (60*30)) return 60*30;
  else return 60*45;
}

Graticule.prototype.gridPrecision = function(dDeg) {
	if(dDeg < 0.01) return 3;
	else if(dDeg < 0.1) return 2;
	else if(dDeg < 1) return 1;
  return 0;
}
  
Graticule.prototype.createLine = function(x,y,w,h) {
	var d = document.createElement("DIV");
  var s = d.style;
	s.position = "absolute";
	s.overflow = "hidden";
	s.backgroundColor = this.color_;
	s.left = x+"px";
	s.top = y+"px";
	s.width = w+"px";
	s.height = h+"px";
  s.opacity = 0.3;
  return d;
}
Graticule.prototype.createVLine = function(x) { return this.createLine(x,this.minY,"1",(this.maxY-this.minY)); }
Graticule.prototype.createHLine = function(y) { return this.createLine(0,y,this.map_.getSize().width,"1"); }

//returns a div that is a horizontal single pixel line, across the dateline  
//we find the start and width of a 180 degree line and draw the same amount to its left and right	  
Graticule.prototype.createHLine3 = function(lat) {
	var f = this.latLngToPixel(lat,0);
	var t = this.latLngToPixel(lat,180);		
	var div = document.createElement("DIV");
	div.style.position = "absolute";
	div.style.overflow = "hidden";
	div.style.backgroundColor = this.color_;
	var x1 = f.x;
	var x2 = t.x;
	if(x2 < x1){
		x2 = f.x;
		x1 = t.x;
	}
	div.style.left = (x1-(x2-x1)) + "px";
	div.style.top = f.y + "px";
	div.style.width = ((x2-x1)*3) + "px";
	div.style.height = "1px";
	return div;
}  
