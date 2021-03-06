function defaultTo(x, d) { return x ? x : d; }
function getStyle(x,styleProp) {
  if (x.currentStyle) {
    return x.currentStyle[styleProp];
  } else if (window.getComputedStyle) {
    return document.defaultView.getComputedStyle(x,null).getPropertyValue(styleProp);
  }
}
function newSVG(elem, attrs) { return document.createElementNS(CCHDO.vis.ns.svg, elem).attr(attrs); }
Element.prototype.empty = function() { while (this.childNodes.length > 0) { this.removeChild(this.childNodes[0]); } return this; };
Element.prototype.append = function(dom) { this.appendChild(dom); return this; };
Element.prototype.appendTo = function(dom) { dom.appendChild(this); return this; };
Element.prototype.css = function(key, val) { return this.attr(key, val, true); };
Element.prototype.text = function(text) { return this.append(document.createTextNode(text)); };
Element.prototype.attr = function(name, value, css) {
  var options = name;
  if (typeof name === 'string') {
    if (value === undefined) { return this.getAttribute(name); }
    else { options = {}; options[name] = value; }
  }
  for (var name in options) {
    if (css) {
      this.style[name] = options[name];
    } else {
      this.setAttribute(name, options[name]);
    }
  }
  return this;
};

var CCHDO = defaultTo(CCHDO, {});

/* CCHDO.vis
 * CCHDO visualizations
 */
CCHDO.vis = {};

/* CCHDO.vis.ns
 * Aliases for some W3C XML namespaces.
 */
CCHDO.vis.ns = {
  xhtml: 'http://www.w3.org/1999/xhtml',
  svg: 'http://www.w3.org/2000/svg',
  xlink: 'http://www.w3.org/1999/xlink',
};

/* CCHDO.vis.Gradient
 * A representation of a gradient that is specified by giving colors and the
 * values for which the colorbar takes on that color.
 *
 * Gradient(colorpts, defaultColor?)
 *  - colorpts is an object that associates values with colors
 *  - defaultColor (optional) is the color that the gradient defaults to when
 *      it cannot interpolate a color for a value
 * Gradient.getColorFor(value)
 *  - value is the numeric value for which to interpolate a color.
 */
CCHDO.vis.Gradient = function(valuecolors, defaultColor) {
  this.valuecolors = valuecolors;
  this.values = [];
  for (var i in this.valuecolors) {
    this.values.push(i);
    this.valuecolors[i] = this.htmlCodeToColor(this.valuecolors[i]);
  }
  this.values = this.values.sort();
  this.defaultColor = defaultTo(defaultColor, '#000');
};
CCHDO.vis.Gradient.prototype.htmlCodeToColor = function(htmlcode) {
  if (htmlcode.length == 4) {
    htmlcode = "#"+htmlcode[1]+htmlcode[1]+htmlcode[2]+htmlcode[2]+htmlcode[3]+htmlcode[3];
  }
  return {r: parseInt(htmlcode.substring(1,3), 16),
          g: parseInt(htmlcode.substring(3,5), 16),
          b: parseInt(htmlcode.substring(5,7), 16)};
};
CCHDO.vis.Gradient.prototype.colorToHtmlCode = function(color) {
  function padZero(x, l) {
    if (x.length >= l) { return x; }
    return '0'+padZero(x, l-1);
  }
  var r = padZero(color.r.toString(16), 2);
  var g = padZero(color.g.toString(16), 2);
  var b = padZero(color.b.toString(16), 2);
  return '#'+r+g+b;
};
CCHDO.vis.Gradient.prototype.interpolateColor = function(valuel, value, valuer) {
  var ratio = 1.0 * (value-valuel) / (valuer - valuel);
  var colorl = this.valuecolors[valuel];
  var colorr = this.valuecolors[valuer];
  var dr = Math.round((colorr.r - colorl.r)*ratio);
  var dg = Math.round((colorr.g - colorl.g)*ratio);
  var db = Math.round((colorr.b - colorl.b)*ratio);
  return {r: colorl.r+dr, g: colorl.g+dg, b: colorl.b+db};
};
CCHDO.vis.Gradient.prototype.getColorFor = function(value) {
  if (this.values[0] > value || this.values[this.values.length-1] < value) {
    return this.defaultColor;
  }
  for (var i in this.values) {
    i = Number(i);
    if (this.values[i] == value) { return this.colorToHtmlCode(this.valuecolors[value]); }
    if (this.values[i] < value) {
      if (this.values[i+1] > value) {
        return this.colorToHtmlCode(this.interpolateColor(this.values[i], value, this.values[i+1]));
      }
    }
  }
};

/* CCHDO.vis.Plot
 *
 * Plot(container)
 *  - container is the HTML DOM element that will contain the plot visualization.
 * Plot.draw(data, options)
 *  - data is a Google Visualization DataView or DataTable.
 *  - options (object)
 *    - width: the width of the chart. (Any valid HTML width) Defaults to the
 *        container width.
 *    - height: the height of the chart. (Any valid HTML width) Defaults to the
 *        container height.
 *    - invertY: whether to invert the Y axis. (boolean) Defaults to false.
 *    - pointColor: the color scheme for points along the Y axis. (HTML color
 *        code or CCHDO.vis.Gradient) Defaults to #05f.
 */
CCHDO.vis.Plot = function(container) {
  this.container = container;
  this.opts = {};
  this.points = [];
  this.selection = [];
  this.g_tips = null;
};
/* This getColumnRange guards against -Infinity being chosen as the range min */
CCHDO.vis.Plot.prototype.getColumnRange = function(data, col) {
  var range = data.getColumnRange(col);
  if (range.min == -Infinity) {
    var val = range.min = range.max;
    for (var i=0; i<data.getNumberOfRows(); i++) {
      val = data.getValue(i, col);
      if (val != -Infinity && val < range.min) { range.min = val; }
    }
  }
  return range;
};
CCHDO.vis.Plot.prototype.draw = function(data, options) {
  var self = this;
  var html = document.body.parentNode;
  html.attr({'xmlns': CCHDO.vis.ns.xhtml, 
             'xmlns:svg': CCHDO.vis.ns.svg,
             'xmlns:xlink': CCHDO.vis.ns.xlink});

  var width = defaultTo(options.width, getStyle(this.container, 'width'));
  var height = defaultTo(options.height, getStyle(this.container, 'height'));
  var invertY = defaultTo(options.invertY, false);
  var pointSize = defaultTo(options.pointSize, 2);
  var pointColor = defaultTo(options.pointColor, '#05f');
  var depthGraph = defaultTo(options.depthGraph, false);
  var gridColor = defaultTo(options.gridColor, '#ccc');

  var padding = 3;
  var labelFont = this.opts.labelFont = 'Helvetica';
  var labelSize = this.opts.labelSize = 12;
  var borderColor = this.opts.borderColor = '#05f';
  var borderWidth = this.opts.borderWidth = '0.2';

  /* Clear the container before drawing */
  this.container.empty();

  var svg = newSVG('svg', {'width': width, 'height': height}).appendTo(this.container);
  svg.style.border = '1px solid #eee'; //TODO remove (this is for development to show boundaries)

  width = parseInt(width.slice(0, -2), 10);
  height = parseInt(height.slice(0, -2), 10);

  // TODO maybe have a loading sign?

  /* Draw the axis labels */

  function makeLabel(x, y, label, vertical) {
    var attrs = {'text-anchor': 'middle', 'fill': 'black',
      'font-family': labelFont, 'font-size': labelSize, 'x': x, 'y': y};
    if (vertical) {
      attrs.transform = 'rotate(270 '+vertical.x+' '+vertical.y+')';
    }
    return newSVG('text', attrs).append(document.createTextNode(label));
  }
  var g_label = newSVG('g').appendTo(svg)
    .append(makeLabel(width/2, height-padding, data.getColumnLabel(0)))
    .append(makeLabel(padding+height/2, height-padding+labelSize,
      data.getColumnLabel(1), {x: padding, y: height-padding}));

  var plotoffsetx = 2*padding+labelSize;
  var plotoffsety = padding;
  var plotwidth = width-padding-plotoffsetx;
  var plotheight = height-3*padding-labelSize;
  var ticksX = 12;
  var ticksY = 5;
  var gridThickness = '0.5';
  var axisFontSize = 10;
  var stublength = 2;

  var labelwidthy = 3*axisFontSize+padding;
  var gridoffsetx = plotoffsetx + labelwidthy;
  var gridoffsety = plotoffsety;
  var gridwidth = plotwidth - labelwidthy;
  var gridheight = plotheight - axisFontSize - padding;

  var rangeX = this.getColumnRange(data, 0);
  var rangeY = this.getColumnRange(data, 1);

  /* Draw the grid */

  function ptToGridX(x) {
    if (rangeX.max == rangeX.min) { return 0; }
    var ratio = (x-rangeX.min)/(rangeX.max-rangeX.min);
    return ratio * gridwidth;
  }
  function ptToGridY(y) {
    if (rangeY.max == rangeY.min) { return 0; }
    var ratio = (y-rangeY.min)/(rangeY.max-rangeY.min);
    if (invertY) { return ratio * gridheight;
    } else { return gridheight - ratio * gridheight; }
  }
  function gridToPtX(x) {
    var ratio = (x)/gridwidth;
    return rangeX.min + ratio * (rangeX.max-rangeX.min);
  }
  function gridToPtY(y) {
    var ratio = (y)/gridheight;
    if (invertY) { return rangeY.min + ratio * (rangeY.max-rangeY.min);
    } else { return rangeY.max - ratio * (rangeY.max-rangeY.min); }
  }

  function makeLine(xs, ys) {
    return newSVG('line', {'stroke': gridColor, 'stroke-width': gridThickness,
      'x1': xs[0], 'y1': ys[0], 'x2': xs[1]+'', 'y2': ys[1]});
  }
  function makeTickLabel(text, x, y, anchor) {
    return newSVG('text', {'text-anchor': anchor, 'font-family': labelFont,
      'font-size': axisFontSize, 'x': x, 'y': y}).append(document.createTextNode(text));
  }

  var g_grid = newSVG('g', {'transform': 'translate('+gridoffsetx+', '+gridoffsety+')'}).appendTo(svg);
  for (var r=0; r<=gridwidth+1; r+=gridwidth/(ticksX-1)) {
    g_grid.append(makeLine([r, r], [gridheight+stublength, 0]))
      .append(makeTickLabel(gridToPtX(r).toPrecision(5), r, plotoffsety+plotheight-padding, 'middle'));
  }
  for (var c=0; c<=gridheight; c+=gridheight/(ticksY-1)) {
    g_grid.append(makeLine([-stublength, gridwidth], [c, c]))
      .append(makeTickLabel(gridToPtY(c).toPrecision(5), -stublength, c+axisFontSize/2, 'end'));
  }

  /* Draw the plot */
  var g_depthGraph = newSVG('g');// higher up so painted first
  var g_points = this.points = newSVG('g');
  this.g_tips = newSVG('g');
  var g_plot = newSVG('g').appendTo(g_grid)
    .append(g_depthGraph).append(g_points).append(this.g_tips);

  var depths = {};
  for (var i=0; i<data.getNumberOfRows(); i++) {
    var x = data.getValue(i, 0);
    var y = data.getValue(i, 1);
    var color = pointColor;
    if (color instanceof CCHDO.vis.Gradient) {
      color = pointColor.getColorFor(y);
    }
    var pt = newSVG('circle', {'cx': ptToGridX(x), 'cy': ptToGridY(y),
      'r': pointSize, 'fill': color,
      'stroke': borderColor, 'stroke-width': borderWidth,
      'ox': x, 'oy': y, 'row': i}).appendTo(g_points);
    pt.onclick = function() {
      self.setSelection([{row: parseInt(this.attr('row'), 10), col: null}]);
      google.visualization.events.trigger(self, 'select', {});
    };
    pt.onmouseover = function() { self.showTip(this.attr('row')); };
    pt.onmouseout = function() { self.clearTip(this.attr('row')); };
    depths[x] = Math.max(y, defaultTo(depths[x], 0));
  }
  if (depthGraph) {
    var d = 'M0 '+gridheight;
    for (var i in depths) {
      d += ' L'+ptToGridX(i)+' '+ptToGridY(depths[i])+' ';
    }
    d += 'L'+gridwidth+' '+gridheight+' Z';
    newSVG('path', {'d': d, 'fill': '#000', 'opacity': '0.9'})
      .appendTo(g_depthGraph);
  }
};
CCHDO.vis.Plot.prototype.getPoint = function(row) { return this.points.childNodes[row]; };
CCHDO.vis.Plot.prototype.showTip = function(row) {
  var pt = this.getPoint(row);
  var size = this.opts.labelSize;
  var font = this.opts.labelFont;
  var text = pt.attr('ox')+', '+pt.attr('oy');
  var textlen = text.length+2;
  pt.attr('stroke', '#f00');
  this.g_tips
    .append(newSVG('rect', {'x': -(textlen*size/2)/2, 'y': -size,
      'width': textlen*size/2, 'height': 2*size, fill: '#ddd'}))
    .append(newSVG('text', {'text-anchor': 'middle', 'dominant-baseline': 'mathematical',
      'font-family': font, 'font-size': size, 'fill': 'black'})
      .append(document.createTextNode(text)))
    .attr('transform', 'translate('+(pt.cx.baseVal.value+(textlen*size/2)/2+parseFloat(pt.r.baseVal.value))+
      ','+(pt.cy.baseVal.value+size+parseFloat(pt.r.baseVal.value))+')');
};
CCHDO.vis.Plot.prototype.clearTip = function(row) { 
  var pt = this.getPoint(row);
  var borderColor = this.opts.borderColor;
  pt.attr('stroke', borderColor);
  this.g_tips.empty();
};
CCHDO.vis.Plot.prototype.grep = function(row) {
  for (var i in this.selection) {
    if (this.selection[i].row == row) { return i; }
  }
  return -1;
};
CCHDO.vis.Plot.prototype.select = function(row) {
  if (this.grep(row) < 0) {
    this.getPoint(row).attr({'stroke-width': '2'});
    this.selection.push({row: row, column: null});
  }
};
CCHDO.vis.Plot.prototype.deselect = function(row) {
  var i = this.grep(row);
  if (i > -1) {
    this.getPoint(row).attr({'stroke-width': this.opts.borderWidth});
    this.selection.splice(i, 1);
  }
};
CCHDO.vis.Plot.prototype.getSelection = function() { return this.selection; };
/* CCHDO.vis.Plot.setSelection
 * As prescribed by the API except only rows may be selected and only one row may be selected at a time.
 */
CCHDO.vis.Plot.prototype.setSelection = function(selection_array) {
  var rows = [];
  for (var i in this.selection) { rows.push(this.selection[i].row); }
  for (var i in rows) { this.deselect(rows[i]); }
  for (var i in selection_array) { this.select(selection_array[i].row); }
};

/*
 * This does something weird with setSelection. Only row may be specified and
 * it should be the actual value that the legend should show.
 */
CCHDO.vis.Legend = function(container) {
  this.container = container;
  this.range = {min: 0, max: 0};
  this.numGradations = 15;
  this.pointer = document.createElement('div').text('>').appendTo(this.container)
    .css({'position': 'absolute', 'top': 0, 'line-height': '1em',
      'margin-top': '-0.5em', 'margin-left': '-0.6em'});
};
CCHDO.vis.Legend.prototype.draw = function(data, options) {
  this.container.css({'height': '400px', 'position': 'relative'});
  this.range = data.getColumnRange(0);
  this.numGradations = defaultTo(options.numGradations, 15);
  var width = defaultTo(options.colorWidth, '20px');
  var gradient = defaultTo(options.gradient, new CCHDO.vis.Gradient({0: "#f00", 6000: "#00f"}, '#fff'));

  var height = parseInt(getStyle(this.container, 'height').slice(0, -2),
                        10)/this.numGradations;

  var table = document.createElement('table').appendTo(this.container)
    .css({'height': this.container.style.height, 'border-collapse': 'collapse'});
  for (var i = this.range.min;
       i < this.range.max;
       i += (this.range.max-this.range.min)/this.numGradations) {
    var color = gradient.getColorFor(i);
    document.createElement('tr').appendTo(table)
      .css('height', height+'px')
      .append(document.createElement('td').css('padding', 0))
      .append(document.createElement('td').css({'padding': 0, 'width': width, 'background-color': color}))
      .append(document.createElement('td').css({'padding': '0 0 0 0.2em', 'vertical-align': 'top',
                                                'font-size': (height-4)+'px',
                                                'border-top': '1px solid '+color}).text(i.toPrecision(4)));
  }
  this.setSelection([{row: this.range.max}]);
};
/* Legend doesn't have a true data table to select on so we won't give the
 * false impression it actually has a selection. */
CCHDO.vis.Legend.prototype.getSelection = function() { return null; };
CCHDO.vis.Legend.prototype.setSelection = function(selection_array) {
  var val = selection_array[0].row;
  var percent = 1.0*val/(this.range.max-this.range.min);
  var px = percent * parseInt(getStyle(this.container, 'height').slice(0, -2), 10);
  this.pointer.style.top = px+'px';
};

/* CCHDO.vis.Map
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
CCHDO.vis.Map = function(container) {
  var self = this;
  if (!google.maps) {
    alert('CCHDO.vis.Map needs the google.maps API v2 to be loaded.');
    return;
  }
  var GM = google.maps;
  if (!GM.BrowserIsCompatible()) {
    alert('CCHDO.vis.Map needs a browser compatible with google.maps v2.');
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
CCHDO.vis.Map.prototype.draw = function(data, options) {
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
CCHDO.vis.Map.prototype.select = function(row) {
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
CCHDO.vis.Map.prototype.deselect = function(row) {
  var marker = this.markers[row];
  marker.setImage(this.markerStyle.icon.image);
  marker.closeInfoWindow();
};
CCHDO.vis.Map.prototype.getSelection = function() {
  return this.selection;
};
CCHDO.vis.Map.prototype.setSelection = function(selection_array) {
  for (var i=0; i<this.selection.length; i++) {
    this.deselect(this.selection[i].row);
  }
  for (var i=0; i<selection_array.length; i++) {
    this.select(selection_array[i].row);
  }
  this.selection = selection_array;
};
