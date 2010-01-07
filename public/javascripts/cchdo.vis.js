function defaultTo(x, d) { return x ? x : d; }
function getStyle(x,styleProp) {
  if (x.currentStyle) {
    return x.currentStyle[styleProp];
  } else if (window.getComputedStyle) {
    return document.defaultView.getComputedStyle(x,null).getPropertyValue(styleProp);
  }
}
function createSVG(elem, attrs) { return document.createElementNS(CCHDO.vis.ns.svg, elem).attr(attrs); }
Element.prototype.append = function(dom) { this.appendChild(dom); return this; };
Element.prototype.appendTo = function(dom) { dom.appendChild(this); return this; };
Element.prototype.attr = function(name, value) {
  var options = name;
  if (typeof name === 'string') {
    if (value === undefined) { return this.getAttribute(name); }
    else { options = {}; options[name] = value; }
  }
  for (var name in options) { this.setAttribute(name, options[name]); }
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
 *    - TODO
 */
CCHDO.vis.Plot = function(container) {
  this.container = container;
  this.opts = {};
  this.points = [];
  this.selection = [];
  this.g_tips = null;
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
  var pointColor = defaultTo(options.pointColor, '#05f');
  var depthGraph = defaultTo(options.depthGraph, false);
  var gridColor = defaultTo(options.gridColor, '#ccc');

  var padding = 3;
  var labelFont = this.opts.labelFont = 'Helvetica';
  var labelSize = this.opts.labelSize = 12;
  var pointSize = 3;
  var borderColor = this.opts.borderColor = '#05f';
  var borderWidth = '0.5';


  /* Clear the container before drawing */
  while (this.container.childNodes.length > 0) { this.container.removeChild(this.container.childNodes[0]); }

  var svg = createSVG('svg', {'width': width, 'height': height}).appendTo(this.container);
  svg.style.border = '1px solid #eee'; //TODO remove (this is for development to show boundaries)

  width = parseInt(width.slice(0, -2), 10);
  height = parseInt(height.slice(0, -2), 10);

  // TODO maybe have a loading sign?

  /* Draw the axis labels */
  var g_label = createSVG('g').appendTo(svg);

  function makeLabel(x, y, label, vertical) {
    var attrs = {'text-anchor': 'middle', 'fill': 'black',
      'font-family': labelFont, 'font-size': labelSize,
      'x': x, 'y': y};
    if (vertical) {
      attrs.transform = 'rotate(270 '+vertical.x+' '+vertical.y+')';
    }
    return createSVG('text', attrs).append(document.createTextNode(label));
  }
  makeLabel(width/2, height-padding, data.getColumnLabel(0)).appendTo(g_label);
  makeLabel(padding+height/2, height-padding+labelSize,
    data.getColumnLabel(1), {x: padding, y: height-padding}).appendTo(g_label);

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

  var rangeX = data.getColumnRange(0);
  var rangeY = data.getColumnRange(1);

  /* Draw the grid */
  var g_grid = createSVG('g', {'transform': 'translate('+gridoffsetx+', '+gridoffsety+')'}).appendTo(svg);

  function ptToGridX(x) {
    if (rangeX.max == rangeX.min) { return 0; }
    var ratio = (x-rangeX.min)/(rangeX.max-rangeX.min);
    return ratio * gridwidth;
  }
  function ptToGridY(y) {
    if (rangeY.max == rangeY.min) { return 0; }
    var ratio = (y-rangeY.min)/(rangeY.max-rangeY.min);
    if (invertY) {
      return ratio * gridheight;
    } else {
      return gridheight - ratio * gridheight;
    }
  }
  function gridToPtX(x) {
    var ratio = (x)/gridwidth;
    return rangeX.min + ratio * (rangeX.max-rangeX.min);
  }
  function gridToPtY(y) {
    var ratio = (y)/gridheight;
    if (invertY) {
      return rangeY.min + ratio * (rangeY.max-rangeY.min);
    } else {
      return rangeY.max - ratio * (rangeY.max-rangeY.min);
    }
  }

  function makeLine(xs, ys) {
    return createSVG('line', {'stroke': gridColor, 'stroke-width': gridThickness,
      'x1': xs[0], 'y1': ys[0], 'x2': xs[1]+'', 'y2': ys[1]});
  }

  for (var r=0; r<=gridwidth+1; r+=gridwidth/(ticksX-1)) {
    makeLine([r, r], [gridheight+stublength, 0]).appendTo(g_grid);
    var label = createSVG('text', {'text-anchor': 'middle', 'font-family': labelFont,
      'font-size': axisFontSize, 'x': r, 'y': plotoffsety+plotheight-padding})
      .append(document.createTextNode(gridToPtX(r).toPrecision(5))).appendTo(g_grid);
  }

  for (var c=0; c<=gridheight; c+=gridheight/(ticksY-1)) {
    g_grid.appendChild(makeLine([-stublength, gridwidth], [c, c]));
    var label = createSVG('text', {'text-anchor': 'end', 'font-family': labelFont,
      'font-size': axisFontSize, 'x': -stublength, 'y': c+axisFontSize/2})
      .append(document.createTextNode(gridToPtY(c).toPrecision(5))).appendTo(g_grid);
  }

  /* Draw the plot */
  var g_plot = createSVG('g').appendTo(g_grid);

  var g_depthGraph = createSVG('g').appendTo(g_plot);
  var g_points = createSVG('g').appendTo(g_plot);
  this.g_tips = createSVG('g').appendTo(g_plot);

  this.points = g_points;

  var depths = {};

  for (var i=0; i<data.getNumberOfRows(); i++) {
    var x = data.getValue(i, 0);
    var y = data.getValue(i, 1);
    var color = pointColor;
    if (color instanceof CCHDO.vis.Gradient) {
      color = pointColor.getColorFor(y);
    }
    var pt = createSVG('circle', {'cx': ptToGridX(x), 'cy': ptToGridY(y),
      'r': pointSize, 'fill': color,
      'stroke': borderColor, 'stroke-width': borderWidth,
      'ox': x, 'oy': y, 'row': i}).appendTo(g_points);
    pt.onclick = function() {
      google.visualization.events.trigger(self, 'select', {});
    };
    pt.onmouseover = function() { self.showTip(this); };
    pt.onmouseout = function() {
      for (var i in this.selection) { if (this.selection[i] === this) { return; } }
      self.clearTip(this);
    };

    depths[x] = depths[x] ? Math.max(y, depths[x]) : Math.max(y, 0);
  }
  if (depthGraph) {
    var d = 'M0 '+gridheight;
    for (var i in depths) {
      d += ' L'+ptToGridX(i)+' '+ptToGridY(depths[i])+' ';
    }
    d += 'L'+gridwidth+' '+gridheight+' Z';
    createSVG('path', {'d': d, 'fill': '#000', 'opacity': '0.9'}).appendTo(g_depthGraph);
  }
};
CCHDO.vis.Plot.prototype.getPoint = function(row) {
  for (var i in this.points.childNodes) {
    var pt = this.points.childNodes[i];
    if (pt.row == row) { return pt; }
  }
  return null;
};
CCHDO.vis.Plot.prototype.clearTip = function(pt) { 
  if (pt == null) {return;}
  var borderColor = this.opts.borderColor;
  pt.attr('stroke', borderColor);
  for (var i in this.g_tips.childNodes) {
    var child = this.g_tips.childNodes[i];
    if (child === pt) {
      this.g_tips.removeChild(this.g_tips.childNodes[0]);
    }
  }
};
CCHDO.vis.Plot.prototype.showTip = function(pt) {
  if (pt == null) {return;}
  var labelSize = this.opts.labelSize;
  var labelFont = this.opts.labelFont;
  var text = pt.attr('ox')+', '+pt.attr('oy');
  var textlen = text.length+2;
  pt.attr('stroke', '#f00');
  this.g_tips
    .append(createSVG('rect', {'x': -(textlen*labelSize/2)/2, 'y': -labelSize,
      'width': textlen* labelSize/2, 'height': 2*labelSize, fill: '#ddd'}))
    .append(createSVG('text', {'text-anchor': 'middle', 'dominant-baseline': 'mathematical',
      'font-family': labelFont, 'font-size': labelSize, 'fill': 'black'})
      .append(document.createTextNode(text)))
    .attr('transform', 'translate('+(pt.cx.baseVal.value+(textlen*labelSize/2)/2+parseFloat(pt.r.baseVal.value))+
      ','+(pt.cy.baseVal.value+labelSize+parseFloat(pt.r.baseVal.value))+')');
};
CCHDO.vis.Plot.prototype.getSelection = function() { return this.selection; };
/* CCHDO.vis.Plot.setSelection
 * As prescribed by the API except only rows may be selected and only one row may be selected at a time.
 */
CCHDO.vis.Plot.prototype.setSelection = function(selection_array) {
  for (var i in this.selection) {
    var selection = this.selection[i];
    this.clearTip(this.getPoint(selection.row));
  }
  for (var i in selection_array) {
    var selection = selection_array[i];
    this.showTip(this.getPoint(selection.row));
    this.selection.push(selection);
  }
};
