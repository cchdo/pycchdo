function defaultTo(x, d) { return x ? x : d; }
function getStyle(x,styleProp) {
  if (x.currentStyle) {
    return x.currentStyle[styleProp];
  } else if (window.getComputedStyle) {
    return document.defaultView.getComputedStyle(x,null).getPropertyValue(styleProp);
  }
}
function setAttrs(element, attrs) {
  for (var attr in attrs) { element.setAttribute(attr, attrs[attr]); }
}
function createSVG(elem, attrs) {
  var e = document.createElementNS(CCHDO.vis.ns.svg, elem);
  setAttrs(e, attrs);
  return e;
}

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
 *        containter height.
 *    - invertY: whether to invert the Y axis. (boolean) Defaults to false.
 *    - pointColor: the color scheme for points along the Y axis. (HTML color
 *        code or CCHDO.vis.Gradient) Defaults to #05f.
 *    - TODO
 */
CCHDO.vis.Plot = function(container) {
  this.container = container;
};
CCHDO.vis.Plot.prototype.draw = function(data, options) {
  var self = this;
  var html = document.body.parentNode;
  setAttrs(html, {'xmlns': CCHDO.vis.ns.xhtml, 
                  'xmlns:svg': CCHDO.vis.ns.svg,
                  'xmlns:xlink': CCHDO.vis.ns.xlink});

  var width = defaultTo(options.width, getStyle(this.container, 'width'));
  var height = defaultTo(options.height, getStyle(this.container, 'height'));
  var invertY = defaultTo(options.invertY, false);
  var pointColor = defaultTo(options.pointColor, '#05f');
  var depthGraph = defaultTo(options.depthGraph, false);

  var padding = 3;
  var labelFont = 'Helvetica';
  var labelSize = 12;
  var pointSize = 3;
  var borderColor = '#05f';
  var borderWidth = '0.5';

  var svg = createSVG('svg', {'width': width, 'height': height});
  svg.style.border = '1px solid #eee'; //TODO remove
  this.container.appendChild(svg);

  width = parseInt(width.slice(0, -2), 10);
  height = parseInt(height.slice(0, -2), 10);

  // TODO maybe have a loading sign?

  /* Draw the axis labels */
  var g_label = createSVG('g');
  svg.appendChild(g_label);

  function makeLabel(x, y, label, vertical) {
    var attrs = {'text-anchor': 'middle', 'fill': 'black',
      'font-family': labelFont, 'font-size': labelSize,
      'x': x, 'y': y};
    if (vertical) {
      attrs.transform = 'rotate(270 '+vertical.x+' '+vertical.y+')';
    }
    var l = createSVG('text', attrs);
    l.appendChild(document.createTextNode(label));
    return l;
  }

  g_label.appendChild(makeLabel(width/2, height-padding, data.getColumnLabel(0)));
  g_label.appendChild(makeLabel(padding+height/2, height-padding+labelSize,
    data.getColumnLabel(1), {x: padding, y: height-padding}));

  var plotoffsetx = 2*padding+labelSize;
  var plotoffsety = padding;
  var plotwidth = width-padding-plotoffsetx;
  var plotheight = height-3*padding-labelSize;
  var ticksX = 12;
  var ticksY = 5;
  var gridThickness = '0.5';
  var gridColor = '#ccc';
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
  var g_grid = createSVG('g', {'transform': 'translate('+gridoffsetx+', '+gridoffsety+')'});
  svg.appendChild(g_grid);

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
    g_grid.appendChild(makeLine([r, r], [gridheight+stublength, 0]));
    var label = createSVG('text', {'text-anchor': 'middle', 'font-family': labelFont,
      'font-size': axisFontSize, 'x': r, 'y': plotoffsety+plotheight-padding});
    label.appendChild(document.createTextNode(gridToPtX(r).toPrecision(5)))
    g_grid.appendChild(label);
  }

  for (var c=0; c<=gridheight; c+=gridheight/(ticksY-1)) {
    g_grid.appendChild(makeLine([-stublength, gridwidth], [c, c]));
    var label = createSVG('text', {'text-anchor': 'end', 'font-family': labelFont,
      'font-size': axisFontSize, 'x': -stublength, 'y': c+axisFontSize/2});
    label.appendChild(document.createTextNode(gridToPtY(c).toPrecision(5)));
    g_grid.appendChild(label);
  }

  /* Draw the plot */
  var g_plot = createSVG('g');
  g_grid.appendChild(g_plot);

  var g_depthGraph = createSVG('g');
  g_plot.appendChild(g_depthGraph);
  var g_points = createSVG('g');
  g_plot.appendChild(g_points);
  var g_labels = createSVG('g');
  g_plot.appendChild(g_labels);

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
      'ox': x, 'oy': y, 'row': i});
    pt.onclick = function() {
      google.visualization.events.trigger(self, 'select', {});
    };
    pt.onmouseover = function() {
      this.setAttribute('stroke', "#f00");
      var label = this.getAttribute('ox')+', '+this.getAttribute('oy');

      var rect = createSVG('rect', {'x': -((label.length+2)*labelSize/2)/2, 'y': -labelSize,
        'width': (label.length+2)* labelSize/2, 'height': 2*labelSize, fill: '#ddd'});
      g_labels.appendChild(rect);
      var text = createSVG('text', {'text-anchor': 'middle', 'dominant-baseline': 'mathematical', 'font-family': labelFont, 'font-size': labelSize, 'fill': 'black'});
      text.appendChild(document.createTextNode(label));
      g_labels.appendChild(text);
      g_labels.setAttribute('transform', 'translate('+(this.cx.baseVal.value+((label.length+2)*labelSize/2)/2+parseFloat(this.r.baseVal.value))+','+(this.cy.baseVal.value+labelSize+parseFloat(this.r.baseVal.value))+')');
    };
    pt.onmouseout = function() {
      this.setAttribute('stroke', borderColor);
      while (g_labels.childNodes.length > 0) {
        g_labels.removeChild(g_labels.childNodes[0]);
      }
    };
    g_points.appendChild(pt);

    depths[x] = depths[x] ? Math.max(y, depths[x]) : Math.max(y, 0);
  }
  if (depthGraph) {
    var d = 'M0 '+gridheight;
    for (var i in depths) {
      d += ' L'+ptToGridX(i)+' '+ptToGridY(depths[i])+' ';
    }
    d += 'L'+gridwidth+' '+gridheight+' Z';
    g_depthGraph.appendChild(createSVG('path', {'d': d, 'fill': '#000', 'opacity': '0.9'}));
  }
};
CCHDO.vis.Plot.prototype.getSelection = function() {
  return [{row: null, column: null}];
};
CCHDO.vis.Plot.prototype.setSelection = function(selection_array) {
};
