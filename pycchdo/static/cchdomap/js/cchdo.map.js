// Dependecies:
//   >=jQuery 1.4.0
//   jQuery UI
//   kmldomwalk
//   google.maps v3
//   google.visualization [table]

function csrf() {
  var data = {};
  data[$('meta[name=csrf-param]').attr('content')] =
    $('meta[name=csrf-token]').attr('content');
  return data;
}

function defaultTo(x, d) {
  return x ? x : d;
}

function getNumberOfProperties(obj) {
  var num = 0;
  for (var k in obj) {
    num += 1;
  }
  return num;
}

function loadScript(url, callback) {
  var s = document.createElement('SCRIPT');
  s.type = 'text/javascript';
  s.src = url;

  document.body.appendChild(s);
  if (callback) {
    s.onreadystatechange = callback;
    s.onload = callback;
  }
}

/* http://james.padolsey.com/javascript/special-scroll-events-for-jquery/ */
(function(){
  var special = jQuery.event.special,
      uid1 = 'D' + (+new Date()),
      uid2 = 'D' + (+new Date() + 1);
  special.scrollstop = {
    latency: 300,
    setup: function() {
      var timer,
          handler = function(evt) {
          var _self = this,
              _args = arguments;
 
          if (timer) {
            clearTimeout(timer);
          }
 
          timer = setTimeout(function(){
            timer = null;
            evt.type = 'scrollstop';
            jQuery.event.handle.apply(_self, _args);
          }, special.scrollstop.latency);
        };
      jQuery(this).bind('scroll', handler).data(uid2, handler);
    },
    teardown: function() {
      jQuery(this).unbind( 'scroll', jQuery(this).data(uid2) );
    }
  };
})();

var CCHDO = defaultTo(CCHDO, {});

(function (CCHDO) {
// TODO
//  importedCircles
//  autoload cruise ids
CCHDO.MAP = {
  map: null,
  earth: null,
  pane: null,
  host: (function () {
    var loc = window.location;
    return [loc.protocol, '//', loc.host].join('');
  })(),
  MIN_TIME: 1967,
  MAX_TIME: new Date().getFullYear(),
  APPNAME: '/search/map',
  // TODO This is a guess at the number of KMLs before the API url overflows
  MAPS_KML_LIMIT: 15,
  TIP_SPAM_TIME: 1000,
  LOADING_IMG: '<img src="/static/cchdomap/images/rotate.gif" />',
  Z: {
    'region': google.maps.Marker.MAX_ZINDEX + 1,
    'dark': google.maps.Marker.MAX_ZINDEX + 2,
    'hl': google.maps.Marker.MAX_ZINDEX + 3,
    'dim': google.maps.Marker.MAX_ZINDEX + 4,
    'dimhl': google.maps.Marker.MAX_ZINDEX + 5
  },
  NRESULT_WARN_THRESHOLD: 50
};

CCHDO.MAP.TIPS = {
  'loading': '<p>Loading...</p>',
  'earthPluginBlocked': 
    '<p>Unable to load the Google Earth plugin.</p>' + 
    '<p>You will not be able to use 3D earth functionality.</p>' +
    '<p>This may have been caused by plugin blocking.</p>',
  'searcherror': 'Encountered error while searching',
  'importing': 'Importing ' + CCHDO.MAP.LOADING_IMG,
  'startDraw': '<dl><dt>Preset shapes</dt><dd>Click and drag.</dd>' + 
               '<dt>Polygon</dt><dd>Single click.</dd>' + 
               '<dt>Cancel</dt><dd>Press <code>ESC</code>. The drawing will ' + 
               'be editable later.</dd></dl>',
  'presetChoose': '<p>Click the shape you want.</p>',
  'polyclose': ['Double click or click on starting vertex to close ',
                'the polygon.'].join(''),
  'polyedit': 'Drag the vertices to edit the polygon',
  'timeswap': ['Swapped min time with max time; ',
    'the values you entered were not min/max.'].join(''),
  'region': '<p>Find cruises that pass through a defined region.</p>',
  'kml': '<p>Load KML or KMZ files used by Google Earth into the map.</p>',
  'kml_failed': '<p>Unable to load KML or KMZ.</p>',
  'kml_too_many': '<p>Too many KMLs being shown simultaneously. Some may not appear.</p>',
  'nav': 
    '<p>Display NAV files as a line.</p><p>This may be useful for comparing ' +
    'tracks.</p>' +
    '<p>NAV files have the format (in decimal degrees):</p>' + 
    '<pre>lon &lt;whitespace&gt; lat\n' + 
    'lon &lt;whitespace&gt; lat\netc.</pre>',
  'search': "<p>You may search for specific parameters using the syntax " + 
            "'parameter:query' e.g.</p>" + 
            "<ul><li>ship:Knorr</li><li>line:p10</li>" + 
            "<li>chief_scientist:Swift</li></ul>" + 
            "<p>These parameters are valid:</p>" +
            // TODO these need to be updated
            "<ul><li>Group</li><li>Chief_Scientist</li><li>ExpoCode</li>" + 
            "<li>Alias</li><li>Ship</li><li>Line</li></ul>."
};

CCHDO.MAP.tip = (function () {
  var past = {};
  return function (s) {
    var lasttime = past[s];
    var now = new Date();
    if (lasttime && now - lasttime < CCHDO.MAP.TIP_SPAM_TIME) {
      return;
    }

    past[s] = now;
    $.jGrowl(s);

    // Clean up the cache
    for (var k in past) {
      if (now - past[k] >= CCHDO.MAP.TIP_SPAM_TIME) {
        delete past[k];
      }
    }
  };
})();

CCHDO.MAP.processCommands = function (commands) {
  for (var i = 0; i < commands.length; i += 1) {
    var command = commands[i];
    if (/^search\:(.+)/.test(command)) {
      var searchCreator = CCHDO.MAP.layerView.layerSectionSearch.creator._content;
      $(':text', searchCreator).val(command.substring('search:'.length));
      $('form', searchCreator).submit();
    } else if (/^kmllink\:(.+)/.test(command)) {
      var kmllinkCreator = CCHDO.MAP.layerView.layerSectionKML.creatorLink._content;
      $(':text', kmllinkCreator).val(command.substring('kmllink:'.length));
      $('form', kmllinkCreator).submit();
    } else if (/^graticules\:(.+)/.test(command)) {
      var on = true;
      var value = command.substring('graticules:'.length);
      if (value == 'off') {
        on = false;
      }
      CCHDO.MAP.layerView.layerSectionPermanent.gratlayer.setOn(on);
    } else if (/^atmosphere\:(.+)/.test(command)) {
      var on = true;
      var value = command.substring('atmosphere:'.length);
      if (value == 'off') {
        on = false;
      }
      CCHDO.MAP.layerView.layerSectionPermanent.atmolayer.setOn(on);
    } else if (/^map_type\:earth/.test(command)) {
      CCHDO.MAP.map.setMapTypeId('Earth');
    } else {
    }
  }
};

CCHDO.MAP.processHashCommands = function () {
  if (!CCHDO.MAP.layerView) {
    return;
  }
  var hash = location.hash;
  if (hash) {
    commands = hash.substring(1).split(',');
    CCHDO.MAP.processCommands(commands);
  }
};

CCHDO.MAP.processSessionCommands = function () {
  if (CCHDO.session_map_commands) {
    CCHDO.MAP.processCommands(CCHDO.session_map_commands.split(','));
  }
};

CCHDO.MAP.load = function () {
  CCHDO.MAP.tip(CCHDO.MAP.TIPS['loading']);
  var domroot = $('#map_space');
  var mapdiv = $('<div id="map" />').appendTo(domroot);

  var center = new google.maps.LatLng(0, 180);
  var opts = {
    zoom: 2,
    center: center,
    mapTypeId: google.maps.MapTypeId.TERRAIN,
    mapTypeControl: true,
    mapTypeControlOptions: {
      style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
      mapTypeIds: [google.maps.MapTypeId.TERRAIN, google.maps.MapTypeId.SATELLITE,
                   google.maps.MapTypeId.HYBRID, google.maps.MapTypeId.ROADMAP]
    }
  };
  CCHDO.MAP.map = new google.maps.Map(mapdiv[0], opts);
  var lltip = new LatLngTooltip(CCHDO.MAP.map);

  var etopo_map_type = 'ETOPO';
  var etopomt = new ETOPOMapType();
  CCHDO.MAP.map.get('mapTypes').set(etopo_map_type, etopomt);

  CCHDO.MAP.earth = new EarthMapType(CCHDO.MAP.map);

  // Add map types to menu
  var mapTypeControlOptions = CCHDO.MAP.map.get('mapTypeControlOptions');
  var ids = mapTypeControlOptions.mapTypeIds;
  if (!ids) {
    ids = [];
  }
  ids.push(CCHDO.MAP.earth.name);
  ids.push(etopo_map_type);
  mapTypeControlOptions.mapTypeIds = ids;
  CCHDO.MAP.map.set('mapTypeControlOptions', mapTypeControlOptions);;

  CCHDO.MAP.pane = new PanedMap(domroot[0], CCHDO.MAP.map);
  CCHDO.MAP.pane._on = true;
  CCHDO.MAP.pane._open = true;

  function completeInit() {
    // graticules needs to be loaded before layerview
    CCHDO.MAP.layerView = new CCHDO.MAP.Layers.DefaultLayerView(CCHDO.MAP.map);
    CCHDO.MAP.pane.setPaneContent(CCHDO.MAP.layerView._dom);

    // TODO figure out how to do this without opening security hole
    //CCHDO.MAP.earth._withEarth(function (ge) {
    //  google.earth.addEventListener(ge, 'balloonopening', function (event) {
    //    // Rewrite all placemark balloons to be unsafe.
    //    event.preventDefault();
    //    var placemark = event.getFeature();
    //    if (placemark.getType() == 'KmlPlacemark') {
    //      var content = placemark.getBalloonHtmlUnsafe();
    //      var balloon = ge.createHtmlStringBalloon('');
    //      balloon.setFeature(placemark);
    //      balloon.setContentString(content);
    //      ge.setBalloon(balloon);
    //    }
    //    return false;
    //  });
    //});

    $(window).resize(function () {
      domroot.height($(this).height() - 20);
      var previousFx = $.fx.off;
      $.fx.off = true;
      CCHDO.MAP.pane.redraw();
      $.fx.off = previousFx;
    }).resize();

    CCHDO.MAP.map.setCenter(center);

    CCHDO.MAP.processSessionCommands();
    CCHDO.MAP.processHashCommands();
  }

  google.maps.event.addListener(CCHDO.MAP.earth, 'initialized', completeInit);
  google.maps.event.addListener(CCHDO.MAP.earth, 'unableToLoadPlugin', function () {
    CCHDO.MAP.tip(CCHDO.MAP.TIPS['earthPluginBlocked']);
    completeInit();
  });

  // If the page is dropped inside a zone surrounding the top of the map,
  // scroll to the nicest viewing spot.
  var menu_offset = $('#cchdo_menu').offset().top;
  $('body').animate({'scrollTop': menu_offset}, 1000, function () {
    var toler_top = $('#picture').height();
    var toler_bot = $('#gfooter').height() + 8;
    $(document).bind('scrollstop', function () {
      var scrollTop = $(this).scrollTop();
      if (scrollTop - toler_bot <= menu_offset && 
          menu_offset <= scrollTop + toler_top) {
        $('body').animate({'scrollTop': menu_offset}, 'fast');
      }
    });
  });
};
})(CCHDO);

var PanedMap = (function () {
function PanedMap(dom, map) {
  this._on = false;
  this._open = false;

  this._root = dom;
  this._map = map;

  this._content = document.createElement('DIV');
  this._content.className = 'pane-content unselectable';
  this._root.appendChild(this._content);

  $(this._content).disableSelection();

  this._handle = document.createElement('DIV');
  this._handle.className = 'pane-handle unselectable clickable right';
  this._root.insertBefore(this._handle, this._root.firstChild);

  var self = this;
  $(this._handle).css('visibility', 'hidden').click(function () {
    self._open = !self._open;
    self.redraw();
  });

  var paneWidth;
  function checkPaneScrolling() {
    var newPaneWidth = self._paneWidth();
    if (newPaneWidth != paneWidth) {
      self.redraw();
    }
    paneWidth = newPaneWidth;
  }

  $(this._content).scroll(checkPaneScrolling);
}

PanedMap.prototype._paneWidth = function () {
  var contentChild = $(this._content).children()[0];
  var paneWidth = $(contentChild).outerWidth();

  if ($(contentChild).height() > $(this._content).height()) {
    // Account for scrollbar
    paneWidth += 15;
  }
  return paneWidth;
};

PanedMap.prototype.redraw = function () {
  var rootHeight = $(this._root).outerHeight();
  var rootWidth = $(this._root).outerWidth();
  var paneWidth = this._paneWidth();
  var mapWidth = rootWidth - paneWidth;

  var self = this;

  function resizedMap() {
    google.maps.event.trigger(self._map, 'resize');
  }

  function closePane() {
    $(self._content).animate({width: 0}, function () {
      $(this).css('visibility', 'hidden')
    });
    $(self._map.getDiv()).animate({'left': 0, width: rootWidth}, resizedMap);
    $(self._handle).animate({left: 0}).removeClass('left').addClass('right');
  }

  $(self._map.getDiv()).height(rootHeight);

  if (this._on) {
    $(this._handle).css({top: $(this._handle).height() / 4, visibility: 'visible'});

    if (this._open) {
      $(this._content).css('visibility', 'visible').animate({width: paneWidth});
      $(this._map.getDiv()).animate({'left': paneWidth, width: mapWidth}, resizedMap);
      $(this._handle).animate({left: paneWidth}).removeClass('right').addClass('left');
    } else {
      closePane();
    }
  } else {
    closePane();
    $(this._handle).css('visibility', 'hidden');
  }
};

PanedMap.prototype.setPaneContent = function (dom) {
  var previous = this._content.firstChild;
  if (previous) {
    this._content.removeChild(previous);
  }
  this._content.appendChild(dom);
  return previous;
};

PanedMap.prototype.setOn = function (on) {
  this._on = on;
  this.redraw();
  return this;
};

PanedMap.prototype.setOpen = function (open) {
  this._open = open;
  this.redraw();
  return this;
};


return PanedMap;
})();

(function () {
 var CM = CCHDO.MAP;

function ImportKML() {
}

ImportKML.prototype.importURL = function (url, map_callback, earth_callback,
                                          error_callback) {
  var self = this;
  var layer = new google.maps.KmlLayer(url, {preserveViewport: true});
  google.maps.event.addListenerOnce(layer, 'status_changed', function () {
    if (layer.getStatus() == google.maps.KmlLayerStatus.OK) {
      google.maps.event.addListenerOnce(layer, 'earth_kml_ready',
                                        function (kmlobj) {
        self._getTour(kmlobj, function (tour) {
          earth_callback(kmlobj, tour);
        });
        self._jcommopsArgoShow(kmlobj);
      });
    } else {
      CM.tip(CM.TIPS['kml_failed'] + ' ' + layer.getStatus());
      delete layer;
      error_callback();
    }
  });
  map_callback(layer);
};

ImportKML.prototype._getTour = function (kmlroot, callback) {
  CM.earth._withEarth(function (ge) {
    var found = false;
    new GEarthExtensions(ge).dom.walk({
      rootObject: kmlroot,
      features: true,
      geometries: false,
      visitCallback: function (context) {
        if (this.getType() == 'KmlTour') {
          found = true;
          callback(this);
          // Stop walking
          return false;
        }
      }
    });
    if (!found) {
      callback(null);
    }
  });
};

ImportKML.prototype._jcommopsArgoShow = function (kmlobj) {
  var href = 'http://www.jcommops.org/jcommops-kml/WebObjects/' +
             'jcommops-kml.woa/wa/createKml?masterProg=Argo';
  if (kmlobj.getType() == 'KmlNetworkLink' &&
      kmlobj.getLink().getHref() == href) {
    function operateOnArgoKml(linkedkml) {
      linkedkml.setOpen(true);
      linkedkml.setVisibility(true);
    }

    var retries = 10;
    (function () {
      var container = kmlobj.getFeatures();
      if (container.hasChildNodes()) {
        var linkedkml = container.getFirstChild();
        if (linkedkml) {
          operateOnArgoKml(linkedkml);
          return;
        }
      }
      retries -= 1;
      if (retries <= 0) {
        return;
      }
      setTimeout(arguments.callee, 1000);
    })();
  }
};


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


function ColorWheel() {}

ColorWheel.indexToHtml = function (i) {
  return ColorWheel.tupleToHtml(ColorWheel.degToTuple(
    ColorWheel.indexToDeg(i)));
};

ColorWheel.indexToDeg = function (i) {
  var ringIndex = Math.floor(Math.log((i - 1) / 1.5) / Math.log(2)) + 1;
  if (ringIndex < 1) {
    ringIndex = 1;
  }
  var numInRing = Math.floor(1.5 * Math.pow(2, ringIndex - 1));
  var ringStart = numInRing + 1;

  var interval = 360 / numInRing;
  var degStart = interval / 2;

  if (ringIndex == 1) {
    numInRing = 3;
    ringStart = 1;
    interval = 120;
    degStart = 0;
  }

  var indexInRing = i - ringStart;
  var degrees = degStart + indexInRing * interval;
  return degrees;
};

ColorWheel.degToTuple = function (deg) {
  return [ColorWheel.component(deg, 0),
          ColorWheel.component(deg, 120),
          ColorWheel.component(deg, 240)];
};

ColorWheel.component = function (deg, start) {
  // Triangle wave approximation with period 360 deg.
  // Squashed into range [0, 1]
  var w = Math.PI / 180;
  var x = deg - start - 90;
  return 0.5 - (4 * (Math.sin(w * x) - Math.sin(3 * w * x) / 9 +
                   Math.sin(5 * w * x) / 25 - Math.sin(7 * w * x) / 49) /
                  Math.pow(Math.PI, 2));
};

ColorWheel.magToHex = function (mag) { 
  var s = Math.round(255 * mag).toString(16);
  while (s.length < 2) {
    s = '0' + s;
  }
  return s;
};

ColorWheel.tupleToHtml = function (t) {
  return '#' + ColorWheel.magToHex(t[0]) +
               ColorWheel.magToHex(t[1]) +
               ColorWheel.magToHex(t[2]);
};

var nextColor = (function () {
  var i = 0;
  return function () {
    i += 1;
    return ColorWheel.indexToHtml(i);
  }
})();

function Set() {
  this._set = {};
  this._i = 0;

  this.add.apply(this, arguments);
}

Set.prototype.has = function () {
  if (arguments.length == 1) {
    var arg = arguments[0];
    if (arg instanceof Array) {
      return this.has.apply(this, arg);
    } else if (arg instanceof Set) {
      return this.has.apply(this, arg.toArray());
    }
  }
  for (var i = 0; i < arguments.length; i += 1) {
    var o = arguments[i];
    if (this._set[o] === undefined) {
      return false;
    }
  }
  return true;
};

Set.prototype.add = function () {
  if (arguments.length == 1) {
    var arg = arguments[0];
    if (arg instanceof Array) {
      return this.add.apply(this, arg);
    } else if (arg instanceof Set) {
      return this.add.apply(this, arg.toArray());
    }
  }
  var addedAll = true;
  for (var i = 0; i < arguments.length; i += 1) {
    var o = arguments[i];
    if (this.has(o)) {
      addedAll = false;
      continue;
    }
    this._set[o] = o;
    this._i += 1;
  }
  return addedAll;
};

Set.prototype.remove = function (o) {
  if (arguments.length == 1) {
    var arg = arguments[0];
    if (arg instanceof Array) {
      return this.remove.apply(this, arg);
    } else if (arg instanceof Set) {
      return this.remove.apply(this, arg.toArray());
    }
  }
  var removedAll = true;
  for (var i = 0; i < arguments.length; i += 1) {
    var o = arguments[i];
    if (this.has(o)) {
      delete this._set[o];
      this._i -= 1;
    } else {
      removedAll = false;
    }
  }
  return removedAll;
};

Set.prototype.intersection = function (o) {
  var inter = new Set();
  this.forEach(function (x) {
    if (o.has(x)) {
      inter.add(x);
    }
  });
  return inter;
};

Set.prototype.difference = function (o) {
  var diff = new Set();
  this.forEach(function (x) {
    if (!o.has(x)) {
      diff.add(x);
    }
  });
  return diff;
};

Set.prototype.forEach = function (callback) {
  for (var i in this._set) {
    callback.call(this, i);
  }
};

Set.prototype.isEmpty = function () {
  return this.getLength() == 0;
};

Set.prototype.isEqual = function (o) {
  if (this.getLength() != o.getLength()) {
    return false;
  }
  return this.has(o);
};

Set.prototype.toArray = function () {
  var a = [];
  this.forEach(function (x) {
    a.push(x);
  });
  return a;
};

Set.prototype.toString = function () {
  return ['[', this.toArray().join(', '), ']'].join('');
};

Set.prototype.getLength = function () {
  return this._i;
};


function Model(map, table) {
  this._map = map;
  this._table = table;
  this._table._model = this;

  this._next_lid = 0;

  this._id_ls = {};

  // id <-> t_id
  this._id_tid = {};
  this._tid_ids = {};

  // l_id -> Layer
  this._l = {};

  // t_id -> Track
  this._t = {};

  // i_id -> info
  this._infos = {};

  this._selected = new Set();
}

Model.prototype._getLayers = function (ids) {
  var self = this;
  var ls = [];
  for (var i = 0; i < ids.length; i += 1) {
    var id = ids[i];
    this._id_ls[id].forEach(function(x) {
      ls.push(self._l[x]);
    });
  }
  return ls;
};

Model.prototype._getIds = function (ts) {
  var ids = [];
  for (var i = 0; i < ts.length; i += 1) {
    var t = ts[i];
    this._tid_ids[t.id].forEach(function (x) {
      ids.push(x);
    });
  }
  return ids;
};

Model.prototype._getTs = function (ids) {
  var ts = [];
  for (var i = 0; i < ids.length; i += 1) {
    var id = ids[i];
    ts.push(this._t[this._id_tid[id]]);
  }
  return ts;
};

Model.prototype.eachT = function (ids, callback) {
  var ts = this._getTs(ids);
  for (var i = 0; i < ts.length; i += 1) {
    var t = ts[i];
    if (t) {
      callback.call(t, i);
    }
  }
};

Model.prototype.layerSelectedActions = function (
    layer, none_callback, some_callback, all_callback) {
  var selected = layer._ids.intersection(this._selected);
  if (selected.isEmpty()) {
    return none_callback.call(layer);
  } else if (selected.getLength() < layer._ids.getLength()) {
    return some_callback.call(layer);
  }
  return all_callback.call(layer);
};

Model.prototype.addSelected = function (x) {
  this._selected.add(x);
  if (this._table) {
    this._table.idsAdded(x);
  }
};

Model.prototype.removeSelected = function (x) {
  this._selected.remove(x);
  if (this._table) {
    this._table.idsRemoved(x);
  }
};

Model.prototype.over = function(layer, t) {
  var ids = null;
  if (layer) {
    ids = layer._ids;
    var selected = ids.intersection(this._selected);
    var nonselected = ids.difference(this._selected);
    this.eachT(nonselected.toArray(), function () {
      this.dim();
    });
    this.eachT(selected.toArray(), function () {
      this.dimhl();
    });
    this.layerSelectedActions(layer, function () {
      this.dim();
    }, function () {
      this.dimhlsome();
    }, function () {
      this.dimhl();
    });
  } else if (t) {
    ids = new Set(this._getIds([t]));
    var selected = ids.intersection(this._selected);
    if (selected.isEmpty()) {
      t.dim();
    } else {
      t.dimhl();
    }

    var layers = this._getLayers(ids.toArray());
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      this.layerSelectedActions(layer, function () {
        this.dim();
      }, function () {
        this.dimhlsome();
      }, function () {
        this.dimhl();
      });
    }
  }
  if (this._table && ids) {
    var self = this;
    ids.forEach(function (id) {
      self._table.dim(id);
    });
  }
};

Model.prototype.out = function(layer, t) {
  var ids = null;
  if (layer) {
    ids = layer._ids;
    var selected = ids.intersection(this._selected);
    this.eachT(ids.difference(this._selected).toArray(), function () {
      this.dark(layer._color);
    });
    this.eachT(selected.toArray(), function () {
      this.hl();
    });
    this.layerSelectedActions(layer, function () {
      this.dark();
    }, function () {
      this.hlsome();
    }, function () {
      this.hl();
    });
  } else if (t) {
    ids = new Set(this._getIds([t]));
    var selected = ids.intersection(this._selected);

    var layers = this._getLayers(ids.toArray());
    var layerWithMaxId = null;
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      if (!layerWithMaxId || layerWithMaxId.id < layer.id) {
        layerWithMaxId = layer;
      }
      this.layerSelectedActions(layer, function () {
        this.dark();
      }, function () {
        this.hlsome();
      }, function () {
        this.hl();
      });
    }

    if (selected.isEmpty()) {
      if (layerWithMaxId) {
        t.dark(layerWithMaxId._color);
      } else {
        t.dark('#000000');
      }
    } else {
      t.hl();
    }
  }
  if (this._table && ids) {
    var self = this;
    ids.forEach(function (id) {
      self._table.dark(id);
    });
  }
};

Model.prototype.click = function(layer, t) {
  var ids = null;
  if (layer) {
    ids = layer._ids;

    var selected = layer._ids.intersection(this._selected);

    if (selected.isEqual(layer._ids)) {
      this.removeSelected(selected);
      layer.dim();
      this.eachT(layer._ids.toArray(), function () {
        this.dim();
      });
    } else {
      this.addSelected(layer._ids);
      layer.dimhl();
      this.eachT(layer._ids.toArray(), function () {
        this.hl();
      });
    }
  } else if (t) {
    ids = new Set(this._getIds([t]));
    var selected = ids.intersection(this._selected);

    if (selected.isEmpty()) {
      this.addSelected(ids);
      t.hl();
    } else {
      this.removeSelected(ids);
      t.dim();
    }

    var layers = this._getLayers(ids.toArray());
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      this.layerSelectedActions(layer, function () {
        this.dark();
      }, function () {
        this.hlsome();
      }, function () {
        this.hl();
      });
    }
  }
};

Model.prototype.removeT = function (tid) {
  var track = this._t[tid];
  if (track) {
    track.set('map', null);
  }
  delete this._t[tid];
};

Model.prototype.removeId = function (id) {
  var tid = this._id_tid[id];
  this._tid_ids[tid].remove(id);
  if (this._tid_ids[tid].getLength() < 1) {
    this.removeT(tid);
  }
  if (this._selected.has(id)) {
    this.removeSelected([id]);
  }
};

Model.prototype.removeIdFromLayer = function (id, layer) {
  this._id_ls[id].remove(layer.id);
  if (this._id_ls[id].getLength() < 1) {
    this.removeId(id);
  }
};

Model.prototype.dissociate = function (layer) {
  var ids = layer._ids;
  var gcids = [];
  var self = this;
  ids.forEach(function (id) {
    self.removeIdFromLayer(id, layer);
  });
};

Model.prototype.query = function (layer, query, callback, tracks_callback,
                                  error_callback) {
  var self = this;

  function handleData(data) {
    var id_t = data["id_t"];
    if (getNumberOfProperties(id_t) > CCHDO.MAP.NRESULT_WARN_THRESHOLD) {
      $('<div>There are more than ' + CCHDO.MAP.NRESULT_WARN_THRESHOLD +
        ' results for your query. If you continue, plotting will take time.' + 
        '</div>').dialog({
        modal: true,
        title: 'Are you sure?',
        buttons: {
          Cancel: function () {
            $(this).dialog('destroy');
            error_callback.call(self);
          },
          Ok: function () {
            $(this).dialog('destroy');
            insertData(data, id_t);
          }
        }
      });
      return;
    }
    insertData(data, id_t);
  }

  function insertData(data, id_t) {
    var ids = [];
    for (var id in id_t) {
      ids.push(id);
      var tid = id_t[id];
      if (self._id_tid[id] === undefined) {
        self._id_tid[id] = tid;
      }
      var set = self._tid_ids[tid];
      if (set === undefined) {
        set = self._tid_ids[tid] = new Set();
      }
      set.add(id);

      var ls = self._id_ls[id];
      if (ls === undefined) {
        ls = self._id_ls[id] = new Set();
      }

      if (layer.id === undefined) {
        layer.id = self._next_lid;
        self._next_lid += 1;
      }
      ls.add(layer.id);
      self._l[layer.id] = layer;
    }

    var infos = data["i"];
    for (var id in infos) {
      self._infos[id] = infos[id];
    }

    var ts = data["t"];
    setTimeout(function () {
      var tracks = [];
      for (var tid in ts) {
        if (self._t[tid] === undefined) {
          var track = new Track(tid, ts[tid], {map: self._map});
          track._model = self;
          self._t[tid] = track;
          tracks.push(track);
        }
      }
      if (tracks_callback) {
        tracks_callback.call(self, tracks);
      }
    }, 0);

    callback.call(self, ids);
  }

  var queryData = {};

  var x = query.query;

  if (typeof(x) == 'string') {
    queryData = {q: x};
  } else {
    var overlay = x.get('overlay');
    var shape = {shape: "polygon", v: []};
    if (overlay instanceof google.maps.Circle) {
      shape.shape = "circle";
      shape.v = x.getCirclePolygon().getPath();
    } else if (overlay instanceof google.maps.Rectangle) {
      shape.shape = "rectangle";

      var b = overlay.getBounds();
      var sw = b.getSouthWest();
      var ne = b.getNorthEast();
      var nw = new google.maps.LatLng(ne.lat(), sw.lng());
      var se = new google.maps.LatLng(sw.lat(), ne.lng());
      shape.v = [sw, nw, ne, se, sw];
    } else {
      shape.v = overlay.getPath();
    }

    function serializeLatLng(ll) {
      return [ll.lng().toFixed(5), ll.lat().toFixed(5)].join(',');
    }

    function serializeVs(vs) {
      var nvs = [];
      if (vs instanceof google.maps.MVCArray) {
        vs.forEach(function (x) {
          nvs.push(serializeLatLng(x));
        });
      } else {
        for (var i = 0; i < vs.length; i += 1) {
          nvs.push(serializeLatLng(vs[i]));
        }
      }
      return nvs.join('_');
    }

    function serializeShape(shape) {
      return [shape.shape, serializeVs(shape.v)].join(':')
    }

    queryData = {shapes: [serializeShape(shape)].join('|')};
  }

  queryData.min_time = query.min_time || CM.MIN_TIME;
  queryData.max_time = query.max_time || CM.MAX_TIME;

  $.ajax({
    url: CM.APPNAME + '/ids',
    method: 'GET',
    dataType: 'json',
    data: queryData,
    success: handleData,
    error: function () {
      CM.tip(CM.TIPS['searcherror']);
      error_callback.apply(self, arguments);
    }
  });
};

Model.prototype.showDetail = function (id, t) {
  console.log('show detail for ', id, t);
};


function View() {
  this._dom = null;
}

function TimeSlider(timerange) {
  View.call(this);
  var self = this;

  this._dom = $('<div></div>')[0];

  this.slide = $('<div></div>').appendTo(this._dom);
  var coords = $('<div></div>').appendTo(this._dom);

  var min = $('<input type="text">').width('4em').appendTo(coords);
  var max = min.clone().css('float', 'right').appendTo(coords);

  function setTimeDisplay(values) {
    min.val(values[0]);
    max.val(values[1]);
  }

  $(this.slide).slider({
    range: true,
    min: CM.MIN_TIME,
    max: CM.MAX_TIME,
    values: [CM.MIN_TIME, CM.MAX_TIME],
    slide: function (event, ui) { setTimeDisplay(ui.values); }
  });

  setTimeDisplay(this.getTimeRange());

  function checkTimeInputs() {
    var max_time = parseInt(max.val(), 10);
    var min_time = parseInt(min.val(), 10);
    if (max_time < min_time) {
      min.val(max_time);
      max.val(min_time);
      CM.tip(CM.TIPS['timeswap']);
    }
    if (min_time < CM.MIN_TIME) { min.val(CM.MIN_TIME); }
    if (max_time > CM.MAX_TIME) { max.val(CM.MAX_TIME); }
    $(self.slide).slider('values', 0, min.val());
    $(self.slide).slider('values', 1, max.val());
  }
  min.blur(checkTimeInputs);
  max.blur(checkTimeInputs);

  if (timerange) {
    setTimeDisplay(timerange);
    checkTimeInputs();
  }
}

TimeSlider.prototype = new View();

TimeSlider.prototype.getTimeRange = function () {
  return $(this.slide).slider('values');
};


function Table() {
  View.call(this);
  var self = this;

  this._dom = document.createElement('DIV');
  $(this._dom).autoPopDialog({
    autoOpen: false,
    position: ['left', 'bottom'],
    width: 800,
    height: 300,
    title: 'Cruise information for selected cruises',
    close: function () {
      if (self._layer) {
        $(self._layer._check).prop('checked', false);
      }
    }
  });
}

Table.prototype = new View();

Table.prototype.setLayer = function (layer) {
  this._layer = layer;
};

Table.prototype.idsAdded = function (ids) {
};

Table.prototype.idsRemoved = function (ids) {
};

Table.prototype.show = function (show) {
  if (show) {
    $(this._dom).dialog('open');
  } else {
    $(this._dom).dialog('close');
  }
}

function GVTable() {
  Table.call(this);
  this._dt = new google.visualization.DataTable({
    cols: [
      {label: 'id', type: 'string'},
      {label: 'link', type: 'string'},
      {label: 'Name', type: 'string'},
      {label: 'Programs', type: 'string'},
      {label: 'Ship', type: 'string'},
      {label: 'Country', type: 'string'},
      {label: 'Cruise Dates', type: 'string'},
      {label: 'Contacts', type: 'string'},
      {label: 'Institutions', type: 'string'}],
    rows: []
  }, 0.6);

  this._table_view_opts = {
    allowHtml: true,
    alternatingRowStyle: true,
    sort: 'enable',
    sortColumn: 0,
    sortAscending: false
  };

  this._explanation = $(
    '<p>Click on a layer ' +
    'or track to select it and its information will appear here.</p>'
  ).appendTo(this._dom).hide();

  this._table_dom = $('<div>').appendTo(this._dom);

  this.setTableJDOM(this._table_dom);
}

GVTable.prototype = new Table();

GVTable.prototype.idsAdded = function (ids) {
  var model = this._model;
  var self = this;
  ids.forEach(function (id) {
    var tid = model._id_tid[id];
    var info = model._infos[id];
    self.add(id, info, tid != null);
  });
  this.redraw();
};

GVTable.prototype.idsRemoved = function (ids) {
  var self = this;
  ids.forEach(function (id) {
    var dtRows = self.getDtRowsForCid(id).sort();
    for (var i = dtRows.length - 1; i >= 0; i -= 1) {
      self._dt.removeRow(dtRows[i]);
    }
  });
  this.redraw();
};

GVTable.prototype.show = function (show) {
  Table.prototype.show.call(this, show);
  if (show) {
    this.redraw();
  }
}

GVTable.prototype.setTableJDOM = function (jdom) {
  if (this._table_jdom) {
    this._table_jdom.empty();
    delete this._table_view;
  }

  this._table_jdom = jdom;
  this._table_view = new google.visualization.Table(this._table_jdom[0]);

  var self = this;

  this.tableRows()
  .live('mouseover', function () {
    var cid = self.getCruiseIdForTr(this);
    if (cid !== undefined && cid > -1) {
      self._model.over(null, self.getTrackForCid(cid));
    }
    return false;
  })
  .live('mouseout', function () {
    var cid = self.getCruiseIdForTr(this);
    if (cid !== undefined && cid > -1) {
      self._model.out(null, self.getTrackForCid(cid));
    }
    return false;
  })
  // TODO Sending a click will de select the cruise. Do we really want that?
  .live('click', function () {
    var dtrow = self.get_dtrow(this);
    if (dtrow > -1) {
      var link = self._dt.getValue(dtrow, 1);
      window.open(link, '');
    }
    return true;
  });

  google.visualization.events.addListener(this._table_view, 'sort', function (event) {
    self.syncSortorder(event);
  });
};

GVTable.prototype.syncSortorder = function (event) {
  if (!event) {
    return;
  }
  this._table_view_opts.sortColumn = event.column;
  this._table_view_opts.sortAscending = event.ascending;
  this.trid_to_dtrow = event.sortedIndexes;
};

GVTable.prototype.tableRows = function () {
  // WARN: This must be bound to a DOM node context, not a jQuery object,
  // hence the subscript.
  return $('tr[class^=google-visualization-table-tr]:not([class$=head])',
           this._table_jdom[0]);
};

GVTable.prototype.getDtRowsForCid = function (cid) {
  return this._dt.getFilteredRows([{column: 0, value: cid}]);
};

GVTable.prototype.getCidForDtRow = function (dtrow) {
  if (dtrow < 0) {
    return -1;
  }
  return this._dt.getValue(dtrow, 0);
};

GVTable.prototype.getTrackForCid = function (cid) {
  return this._model._t[this._model._id_tid[cid]];
};

GVTable.prototype.getCruiseIdForTr = function (tr) {
  return this.getCidForDtRow(this.get_dtrow(tr));
};

GVTable.prototype.getTrsForId = function (id) {
  var dtrows = this.getDtRowsForCid(id);
  var trs = [];
  for (var i = 0; i < dtrows.length; i += 1) {
    trs.push(this.getTr(this.dtrowToTrid(dtrows[i])));
  }
  return trs;
};

GVTable.prototype.dtrowToTrid = function (dtrow) {
  if (this.trid_to_dtrow) {
    return this.trid_to_dtrow.indexOf(dtrow);
  }
  return dtrow;
};

GVTable.prototype.tridToDtrow = function (trid) {
  if (this.trid_to_dtrow) {
    return this.trid_to_dtrow[trid];
  }
  return trid;
};

GVTable.prototype.get_dtrow = function (tr) {
  return this.tridToDtrow(this.get_trid(tr));
};

GVTable.prototype.getTr = function (i) {
  return this.tableRows()[i];
};

GVTable.prototype.get_trid = function (tr) {
  var trs = this.tableRows();
  for (var i = 0; i < trs.length; i += 1) {
    var itr = trs[i];
    if (tr === itr) {
      return i;
    }
  }
  return -1;
};

GVTable.prototype.add = function (id, info, hasTrack) {
  var data_row = this._dt.addRow([
    id, '/cruise/' + info.name, info.name, info.programs, info.ship, info.country,
    info.cruise_dates, info.contacts, info.institutions]);
  if (!hasTrack) {
    for (var i = 0; i < this._dt.getNumberOfColumns(); i += 1) {
      this._dt.setProperty(data_row, i, 'style', 'background-color: #fdd;');
    }
  }
  return data_row;
};

GVTable.prototype.remove = function (ids) {
  if (ids instanceof Array) {
    ids = ids.sort();
    for (var i = ids.length - 1; i >= 0; i -= 1) {
      this._dt.removeRow(ids[i]);
    }
  } else {
    this._dt.removeRow(ids);
  }
  this.redraw();
};

GVTable.prototype.hl = function (id) {
  this._table_view.setSelection([{row: id}]);
  this.selected = this._table_view.getSelection();
};

GVTable.prototype.DIM_CLASS = 'google-visualization-table-tr-over';

GVTable.prototype.dimTr = function (tr) {
  //var selection = this._table_view.getSelection();
  //for (var i = 0; i < selection.length; i += 1) {
  //  var selector = selection[i];
  //  if (selector.row != this.get_dtrow(tr)) {
  //    $(tr).addClass(this.DIM_CLASS);
  //  }
  //}
  $(tr).addClass(this.DIM_CLASS);
};

GVTable.prototype.darkTr = function (tr) {
  //var selection = this._table_view.getSelection();
  //for (var i = 0; i < selection.length; i += 1) {
  //  var selector = selection[i];
  //  if (selector.row != this.get_dtrow(tr)) {
  //    $(tr).removeClass(this.DIM_CLASS);
  //  }
  //}
  $(tr).removeClass(this.DIM_CLASS);
};

GVTable.prototype.dim = function (id) {
  var trs = this.getTrsForId(id);
  for (var i = 0; i < trs.length; i += 1) {
    var tr = trs[i];
    this.dimTr(tr);
  }
};

GVTable.prototype.dark = function (id) {
  var trs = this.getTrsForId(id);
  for (var i = 0; i < trs.length; i += 1) {
    var tr = trs[i];

    $(tr).removeClass(this.DIM_CLASS);
    var selection = this._table_view.getSelection();
    if (selection.length > 0) {
      for (var i in selection) {
        if (selection[i].row == id) {
          selection.splice(i, 1);
          this._table_view.setSelection(selection);
        }
      }
    }
  }
};

GVTable.prototype.redraw = function () {
  if (this._dt.getNumberOfRows() < 1) {
    $(this._explanation).show();
    $(this._table_dom).hide();
  } else {
    $(this._explanation).hide();
    $(this._table_dom).show();
  }
  if (this._table_view) {
    var dt_view = new google.visualization.DataView(this._dt);
    var cols = [];
    for (var i = 2; i < this._dt.getNumberOfColumns(); i += 1) {
      cols.push(i);
    }
    dt_view.setColumns(cols);
    this._table_view.draw(dt_view, this._table_view_opts);
    this.syncSortorder(this._table_view.getSortInfo());
    if (this.selected) {
      this._table_view.setSelection(this.selected);
    }
  }
};


function Track(id, coords, opts) {
  this.id = id;
  this.setValues(opts);

  var track = [];
  for (var i = 0; i < coords.length; i += 1) {
    var coord = coords[i];
    track.push(new google.maps.LatLng(coord[1], coord[0]));
  }

  this._line = new google.maps.Polyline({path: track});
  this._start = new google.maps.Marker({position: track[0],
                                        icon: this.icons.start});
  this._line.bindTo('map', this);
  this._line.bindTo('strokeColor', this);
  this._line.bindTo('zIndex', this);
  this._start.bindTo('map', this);
  this._start.bindTo('zIndex', this);

  var self = this;

  google.maps.event.addListener(this._start, 'mouseover', function () {
    self._model.over(null, self);
  });
  google.maps.event.addListener(this._start, 'mouseout', function () {
    self._model.out(null, self);
  });
  google.maps.event.addListener(this._start, 'click', function () {
    self._model.click(null, self);
  });
  google.maps.event.addListener(this._line, 'mouseover', function () {
    self._model.over(null, self);
  });
  google.maps.event.addListener(this._line, 'mouseout', function () {
    self._model.out(null, self);
  });
  google.maps.event.addListener(this._line, 'click', function () {
    self._model.click(null, self);
  });
}

Track.prototype = new google.maps.MVCObject();

Track.prototype.icons = {
  start: new google.maps.MarkerImage(
    CM.host + "/static/cchdomap/images/cruise_start_icon.png",
    new google.maps.Size(32, 16),
    null,
    new google.maps.Point(0, 16),
    new google.maps.Size(32, 16)),
  station: new google.maps.MarkerImage(
    CM.host + "/static/cchdomap/images/station_icon.png",
    new google.maps.Size(2, 2),
    null,
    new google.maps.Point(1, 1))
};

Track.prototype._createStations = function () {
  var self = this;
  if (!this._station_leader) {
    this._station_leader = new google.maps.MVCObject();
    this._station_leader.bindTo('map', this);
  }
  if (!this._stations) {
    this._stations = new google.maps.MVCArray();
  }
  this._line.getPath().forEach(function (x, i) {
    if (i < self._stations.getLength()) {
      self._stations.getAt(i).setPosition(x);
    } else {
      var stationmkr = new google.maps.Marker({
        position: x,
        clickable: false,
        flat: true,
        icon: self.icons.station
      });
      stationmkr.bindTo('visible', self._station_leader);
      stationmkr.bindTo('map', self._station_leader);
      self._stations.push(stationmkr);
    }
  });
  while (this._stations.getLength() > this._line.getPath().getLength()) {
    var stationmkr = this._stations.pop();
    stationmkr.unbind('map');
    stationmkr.setMap(null);
  }
};

Track.prototype.hl = function () {
  this.set('strokeColor', '#ffaa22');
  this.set('zIndex', CM.Z['hl']);
  var self = this;

  // TODO low performance
  //setTimeout(function () {
  //  self._createStations();
  //  self._station_leader.set('visible', true);
  //}, 0);
};

Track.prototype.dimhl = function () {
  this.set('strokeColor', '#ffffaa');
  this.set('zIndex', CM.Z['dimhl']);
  var self = this;

  // TODO low performance on hl
  //setTimeout(function () {
  //  self._createStations();
  //  self._station_leader.set('visible', true);
  //}, 0);
};

Track.prototype.dim = function () {
  this.set('strokeColor', '#ffffaa');
  this.set('zIndex', CM.Z['dim']);
  if (this._station_leader) {
    this._station_leader.set('visible', false);
  }
};

Track.prototype.dark = function (color) {
  this.set('strokeColor', color);
  this.set('zIndex', CM.Z['dark']);
  if (this._station_leader) {
    this._station_leader.set('visible', false);
  }
};


/**
 * A LayerView provides a view into 
 */
function LayerView(map) {
  var dom = this._dom = document.createElement('DIV');
  dom.className = 'layerview unselectable';
  this._sections = [];
  this._model = new Model(map, new Table());
}

LayerView.prototype = new View();

LayerView.prototype.pushSection = function (section) {
  this._sections.push(section);
  this._dom.appendChild(section._dom);
  section._layerView = this;
};


/**
 *
 */
function LayerSection(name) {
  var dom = this._dom = document.createElement('DIV');
  dom.className = 'section';

  this._title = document.createElement('H1');
  dom.appendChild(this._title);

  this._list = document.createElement('UL');
  dom.appendChild(this._list);

  this.setName(name);
}

LayerSection.prototype = new View();

LayerSection.prototype.setName = function (name) {
  var classname = this._dom.className.replace(this.name, name);
  if (this._dom.className.indexOf(name) < 0) {
    if (classname.length > 0) {
      classname += ' ';
    }
    classname += name;
  }
  this._dom.className = classname;
  this.name = name;
  while (this._title.hasChildNodes()) {
    this._title.removeChild(this._title.firstChild);
  }
  this._title.innerHTML = name;
};

LayerSection.prototype.addLayer = function (layer) {
  var lastChild = this._list.lastChild;
  if (lastChild && lastChild.className.indexOf('layer-creator') > -1) {
    this._list.insertBefore(layer._dom, lastChild);
  } else {
    this._list.appendChild(layer._dom);
  }
  layer._layerSection = this;
};

LayerSection.prototype.getLayers = function () {
  return this._list;
};

LayerSection.prototype.removeLayer = function (layer) {
  this._list.removeChild(layer._dom);
  layer._layerSection = undefined;
};


/**
 *
 */
function Layer() {
  var dom = this._dom = document.createElement('LI');
  dom.className = 'layer clickable';

  this._check = document.createElement('INPUT');
  this._check.type = 'checkbox';
  dom.appendChild(this._check);

  this._content = document.createElement('SPAN');
  this._content.className = 'content';
  dom.appendChild(this._content);

  this._accessory = document.createElement('SPAN');
  this._accessory.className = 'accessory';
  dom.appendChild(this._accessory);

  var self = this;

  $(dom).hover(function () {
    if (self._ids) {
      self._layerSection._layerView._model.over(self, null);
    }
  }, function () {
    if (self._ids) {
      self._layerSection._layerView._model.out(self, null);
    }
  }).click(function () {
    if (self._ids) {
      self._layerSection._layerView._model.click(self, null);
    }
  });

  $(this._check).change(function () {
    self._turnOn($(this).is(':checked'));
  }).click(function (event) {
    event.stopPropagation();
  });
}

Layer.prototype = new View();

Layer.prototype._turnOn = function (on) {
  if (on) {
    this._on();
  } else {
    this._off();
  }
};

Layer.prototype.setOn = function (on) {
  this._check.checked = on ? 'checked' : '';
  try {
    $(this._check).change();
  } catch (e) {
    this._check.checked = !on ? 'checked' : '';
  }
};

Layer.prototype.enable = function () {
  this._dom.className = this._dom.className.replace(' disabled', '');
  this._check.disabled = '';
  this.showAccessory();
  if (this.setColor) {
    this.setColor(this._color);
  }
};

Layer.prototype.disable = function () {
  this._dom.className += ' disabled';
  this._check.disabled = 'disabled';
  this.showAccessory(false);
};

Layer.prototype.showAccessory = function (show) {
  this._accessory.style.visibility = (show !== false ? 'visible' : 'hidden');
};

/**
 * Removes this layer from the section.
 */
Layer.prototype.remove = function () {
  if (this._ids) {
    this._layerSection._layerView._model.dissociate(this);
  }
  if (this._layerSection) {
    this._layerSection.removeLayer(this);
  }
};

Layer.prototype.associate = function (ids) {
  var newids = new Set(ids);

  if (this._ids) {
    var removedIds = this._ids.difference(newids);

    var self = this;
    removedIds.forEach(function (id) {
      self._layerSection._layerView._model.removeIdFromLayer(id, self);
    });
  }

  this._ids = newids;
  this._associated();
};

Layer.prototype.eachT = function (callback) {
  this._layerSection._layerView._model.eachT(this._ids.toArray(), callback);
};

Layer.prototype.hl = function (ids) {
  this._dom.style.background = '#ffffaa';
};

Layer.prototype.hlsome = function (ids) {
  this._dom.style.background = '#dddd88';
};

Layer.prototype.dimhl = function (ids) {
  this._dom.style.background = '#ffffcc';
};

Layer.prototype.dimhlsome = function (ids) {
  this._dom.style.background = '#ffffcc';
};

Layer.prototype.dim = function (ids) {
  this._dom.style.background = '#aaaaaa';
};

Layer.prototype.dark = function (ids) {
  this._dom.style.background = 'transparent';
};

/* Abstract */
Layer.prototype._on = function () {
};

Layer.prototype._off = function () {
};

Layer.prototype._associated = function () {
};


function LayerCreator() {
  Layer.call(this);
  this._dom.className = 'layer-creator';
}

LayerCreator.prototype = new Layer();


function DefaultLayerView(map) {
  var dom = this._dom = document.createElement('DIV');
  dom.className = 'layerview unselectable';
  this._sections = [];
  var table = new GVTable();
  this._model = new Model(map, table);

  this.layerSectionPermanent = new PermanentLayerSection(table);
  this.layerSectionSearch = new SearchLayerSection();
  this.layerSectionRegion = new RegionLayerSection();
  this.layerSectionKML = new KMLLayerSection();
  this.layerSectionNAV = new NAVLayerSection();
  var sections = [
    this.layerSectionPermanent,
    this.layerSectionSearch,
    this.layerSectionRegion,
    this.layerSectionKML,
    this.layerSectionNAV
  ];
  for (var i = 0; i < sections.length; i += 1) {
    this.pushSection(sections[i]);
  }
}

DefaultLayerView.prototype = new LayerView();


function PermanentLayerSection(table) {
  LayerSection.call(this, '<img src="/static/cchdomap/images/layers_off.png" />');

  this.tablelayer = new PermanentLayer('Table', false, function (on) {
    table.show(on);
  });
  table.setLayer(this.tablelayer);
  this.addLayer(this.tablelayer);

  this.gratlayer = new PermanentLayer('Graticules', true, function (on) {
    CM.earth.set('graticules', on);
  });
  this.gratlayer._dom.firstChild.id = 'gridon';
  this.addLayer(this.gratlayer);

  if (CM.earth.get('earth_plugin')) {
    this.atmolayer = new PermanentLayer('Atmosphere', true, function (on) {
      CM.earth.set('atmosphere', on);
    });
    $(this.atmolayer._dom).hide();
    this.addLayer(this.atmolayer);
    var self = this;
    google.maps.event.addListener(CM.earth, 'showing_changed', function () {
      if (CM.earth.get('showing')) {
        $(self.atmolayer._dom).show('fast');
      } else {
        $(self.atmolayer._dom).hide('fast');
      }
    });
  }
}

PermanentLayerSection.prototype = new LayerSection();


function PermanentLayer(name, on, onoff_callback) {
  Layer.call(this);
  this._content.appendChild(document.createTextNode(name));
  var self = this;
  $(this._dom).click(function () {
    $(self._check).click();
    return false;
  });
  this._onoff_callback = onoff_callback;
  this.setOn(on);
}

PermanentLayer.prototype = new Layer();
PermanentLayer.prototype.remove = function () {};
PermanentLayer.prototype._on = function () {
  this._onoff_callback.call(this, true);
};
PermanentLayer.prototype._off = function () {
  this._onoff_callback.call(this, false);
};


function addColorBox(layer, color) {
  if (!color) {
    color = '#000000';
  }

  layer._colorpicker = $('<span class="colorbox clickable"></span>').css({
    backgroundColor: color
  }).appendTo(layer._content);

  layer._colorpicker.ColorPicker({
    color: color,
    onChange: function (hsb, hex, rgb) {
      layer._colorpicker.css('backgroundColor', '#' + hex);
      layer.setColor('#' + hex);
    },
    onSubmit: function (hsb, hex, rgb) {
      layer._colorpicker.ColorPickerHide();
    }
  });
  layer.setColor(color);
}


function QueryLayer() {
  Layer.call(this);
  var self = this;

  this._accessory_count = 
    $('<span class="accessory-count">loading...</span>').appendTo(this._accessory)[0];
  this._accessory_edit = 
    $('<span class="accessory-edit">&raquo;</span>').appendTo(this._accessory)[0];

  $(this._accessory_edit).click(function () {
    return self.edit();
  });
}

QueryLayer.prototype = new Layer();

QueryLayer.prototype.setQuery = function (query) {
  if (!this._query) {
    this._query = {
      query: query,
      min_time: CM.MIN_TIME,
      max_time: CM.MAX_TIME
    };
  } else {
    this._query.query = query;
  }
};

QueryLayer.prototype.query = function () {
};

QueryLayer.prototype.edit = function () {
};


function SearchLayerSection() {
  LayerSection.call(this, 'Searches');
  this.creator = new SearchLayerCreator();
  this.addLayer(this.creator);
}

SearchLayerSection.prototype = new LayerSection();


function SearchLayer(query, color) {
  QueryLayer.call(this);

  addColorBox(this, color);

  this.setQuery(query);
  $('<span class="search-query"></span>').html(query).css('vertical-align', 'top').appendTo(this._content);
}

SearchLayer.prototype = new QueryLayer();

SearchLayer.prototype.setColor = function (color) {
  if (this._ids) {
    this.eachT(function () {
      this.set('strokeColor', color);
    });
  }
  this._color = color;
};

SearchLayer.prototype._on = function () {
  var map = this._layerSection._layerView._model._map;
  this.eachT(function () {
    this.set('map', map);
  });
};

SearchLayer.prototype._off = function () {
  var self = this;
  setTimeout(function () {
    self.eachT(function () {
      this.set('map', null);
    });
  }, 0);
};

SearchLayer.prototype.edit = function () {
  var self = this;

  var dialog = $('<div></div>').dialog({
    modal: true,
    title: 'Edit layer',
    buttons: {
      'Done': function () {
        $(this).dialog('close');
      },
      'Delete': function () {
        self.remove();
        $(this).dialog('destroy');
      }
    }
  });
  return false;
};

SearchLayer.prototype._associated = function () {
  $(this._accessory_count).empty().html(this._ids.getLength());
};

SearchLayer.prototype.query = function () {
  var self = this;
  var query = this._query;
  this.disable();
  this._layerSection._layerView._model.query(this, query, function (ids) {
    self.associate(ids);
    self.enable();
    self.setOn(true);
  }, function (ts) {
    for (var i = 0; i < ts.length; i += 1) {
      ts[i].set('strokeColor', self._color);
    }
  }, function () {
    self.remove();
  });
};


function SearchLayerCreator() {
  LayerCreator.call(this);
  var textfield = document.createElement('INPUT');
  textfield.type = 'search';
  textfield.setAttribute('x-webkit-speech', 'true');
  var submit = document.createElement('INPUT');
  submit.type = 'submit';
  submit.value = 'Search';

  $(textfield).tipTipTip({activation: 'focus', content: CM.TIPS['search']});

  var form = document.createElement('FORM');
  form.appendChild(textfield);
  form.appendChild(submit);
  this._content.appendChild(form);

  var self = this;
  $(form).submit(function () {
    var query = textfield.value;
    // Empty query
    if (query.length < 1) {
      return false;
    }
    var layer = new SearchLayer(query, nextColor());
    self._layerSection.addLayer(layer);
    layer.query();
    $(textfield).blur();
    return false;
  });
}

SearchLayerCreator.prototype = new LayerCreator();


function RegionLayerSection() {
  LayerSection.call(this, 'Regions');
  this.creator = new RegionLayerCreator();
  this.addLayer(this.creator);

  $(this._dom).tipTipTip({defaultPosition: 'right', content: CM.TIPS['region']});
}

RegionLayerSection.prototype = new LayerSection();


function RegionLayer(shape, color) {
  QueryLayer.call(this);
  this._shape = shape;

  addColorBox(this, color);
}

RegionLayer.prototype = new QueryLayer();

RegionLayer.prototype.remove = function () {
  this._shape.setMap(null);
  Layer.prototype.remove.call(this);
};

RegionLayer.prototype.edit = function () {
  var self = this;

  // TODO stations slider
  //<p class="maxstations">
  //  <%= text_field_tag 'max_coords', @DEFAULT[:max_coords] %>
  //  stations shown / cruise
  //</p>

  var timeslider = new TimeSlider([self._query.min_time, self._query.max_time]);

  function updateTimeRange() {
    var timerange = timeslider.getTimeRange();
    var changed = self._query.min_time != timerange[0] ||
                  self._query.max_time != timerange[1];
    self._query.min_time = timerange[0];
    self._query.max_time = timerange[1];
    if (changed) {
      self.query();
    }
  }

  var dialog = $('<div></div>').dialog({
    modal: true,
    title: 'Edit layer',
    beforeClose: updateTimeRange,
    buttons: {
      'Done': function () {
        updateTimeRange();
        $(this).dialog('close');
      },
      'Delete': function () {
        self.remove();
        $(this).dialog('destroy');
      }
    }
  }).append(timeslider._dom);
  return false;
};

RegionLayer.prototype._on = function () {
  var map = this._layerSection._layerView._model._map;
  if (this._shape) {
    this._shape.set('map', map);
  }

  this.eachT(function () {
    this.set('map', map);
  });
};

RegionLayer.prototype._off = function () {
  var self = this;
  if (this._shape) {
    this._shape.set('map', null);
  }

  setTimeout(function () {
    self.eachT(function () {
      this.set('map', null);
    });
  }, 0);
};

RegionLayer.prototype.setColor = function (color) {
  if (this._ids) {
    this.eachT(function () {
      this.set('strokeColor', color);
    });
  }
  this._shape.set('strokeColor', color);
  this._color = color;
};

RegionLayer.prototype._associated = function () {
  $(this._accessory_count).empty().html(this._ids.getLength());
  this.setColor(this._color);
};

RegionLayer.prototype.query = function () {
  var self = this;
  this.disable();
  var query = this._query;
  this._layerSection._layerView._model.query(this, query, function (ids) {
    self.associate(ids);
    self.enable();
    self.setOn(true);
  }, function (ts) {
    for (var i = 0; i < ts.length; i += 1) {
      ts[i].set('strokeColor', self._color);
    }
  }, function () {
    self.remove();
  });
};


function RegionLayerCreator(name) {
  LayerCreator.call(this);
  var button = document.createElement('BUTTON');
  button.appendChild(document.createTextNode('Draw region of interest'));
  this._content.appendChild(button);

  var self = this;
  button.onclick = function () {
    var shape = new DShape();
    var layer = new RegionLayer(shape, nextColor());
    button.disabled = 'disabled';

    function finished() {
      button.disabled = '';
    }

    shape.setMap(self._layerSection._layerView._model._map);
    shape.start();
    CM.tip(CM.TIPS['startDraw']);

    var completed = false;
    function requery() {
      if (completed) {
        layer.setQuery(shape);
        layer.query();
      }
    }
    google.maps.event.addListener(shape, 'shape_changed', requery);
    google.maps.event.addListener(shape, 'draw_updated', requery);
    google.maps.event.addListener(shape, 'draw_canceled', function () {
      shape.setMap(null);
      finished();
    });
    google.maps.event.addListener(shape, 'draw_ended', function () {
      self._layerSection.addLayer(layer);
      completed = true;
      layer.setQuery(shape);
      layer.query();
      finished();
    });
    var polyEar = google.maps.event.addListenerOnce(shape, 'drawing_polygon', function () {
      CM.tip(CM.TIPS['polyclose']);
      google.maps.event.removeListener(presetEar);
    });
    var presetEar = google.maps.event.addListenerOnce(shape, 'drawing_presets', function () {
      CM.tip(CM.TIPS['presetChoose']);
      google.maps.event.removeListener(polyEar);
    });
    var editingEar = google.maps.event.addListener(shape, 'editable_changed', function () {
      if (shape.get('editable')) {
        CM.tip(CM.TIPS['polyedit']);
        google.maps.event.removeListener(editingEar);
      }
    });
    return false;
  };
}

RegionLayerCreator.prototype = new LayerCreator();


function KMLLayerSection() {
  LayerSection.call(this, '<img src="/static/cchdomap/images/gearth.gif" />');
  this.creatorUpload = new KMLLayerCreatorUpload();
  this.addLayer(this.creatorUpload);
  this.creatorLink = new KMLLayerCreatorLink();
  this.addLayer(this.creatorLink);
  this._importer = new ImportKML();
  this._mapobj = null;

  $(this._dom).tipTipTip({defaultPosition: 'right', content: CM.TIPS['kml']});
}

KMLLayerSection.prototype = new LayerSection();


function KMLLayer(filename) {
  Layer.call(this);
  this._content.title = filename;
  this._content.appendChild(document.createTextNode(filename.replace(CM.host, '')));
  var self = this;
  $('<span>x</span>').click(function () {
    self.remove();
  }).appendTo(this._accessory);
}

KMLLayer.prototype = new Layer();

KMLLayer.prototype._on = function () {
  if (!this._mapobj) {
    return;
  }
  this._mapobj.setMap(this._layerSection._layerView._model._map);
};

KMLLayer.prototype._off = function () {
  if (!this._mapobj) {
    return;
  }
  this._mapobj.setMap(null);
};

KMLLayer.prototype.remove = function () {
  this._off();
  Layer.prototype.remove.call(this);
};

KMLLayer.prototype.setTour = function (tour) {
  if (!tour) {
    return;
  }
  this._tour = tour;

  var self = this;

  var playbutton = $('<span class="kml-tour-play">&#9658;</span>').prependTo(this._accessory);
  playbutton.click(function () {
    if ($(this).data('playing')) {
      self.pauseTour();
      playbutton.attr('class', 'kml-tour-play').html('&#9658;');
    } else {
      self.playTour();
      playbutton.attr('class', 'kml-tour-pause').html('||');
    }
    $(this).data('playing', !$(this).data('playing'));
    return false;
  });

  // TODO change kml tour status according to status
  playbutton.hide();
  google.maps.event.addListener(CM.earth, 'showing_changed', function () {
    if (CM.earth.get('showing')) {
      playbutton.show('fast');
    } else {
      playbutton.hide('fast');
    }
  });
};

KMLLayer.prototype.pauseTour = function () {
  CM.earth._withEarth(function (ge) {
    ge.getTourPlayer().pause();
  });
};

KMLLayer.prototype.playTour = function () {
  CM.earth._withEarth(function (ge) {
    ge.getTourPlayer().setTour(self._tour);
    ge.getTourPlayer().play();
  });
};


function KMLLayerCreator() {
  var layer = null;
}

KMLLayerCreator.prototype = new LayerCreator();

KMLLayerCreator.prototype.setMapLayer = function (layer, mapLayer) {
  layer._mapobj = mapLayer;
  layer.enable();
  google.maps.event.addListenerOnce(mapLayer, 'metadata_changed', function () {
    var metadata = mapLayer.getMetadata();
    if (metadata) {
      var name = metadata.name;
      if (name) {
        layer._content.childNodes[0].nodeValue = name;
      }
    }
  });
  if ($(this._layerSection.getLayers()).find('.layer').length <= CM.MAPS_KML_LIMIT) {
    layer.setOn(true);
  } else {
    CM.tip(CM.TIPS['kml_too_many']);
  }
};


function KMLLayerCreatorUpload() {
  LayerCreator.call(this);
  var filefield = document.createElement('INPUT');
  filefield.name = 'file';
  filefield.type = 'file';

  var form = document.createElement('FORM');
  form.enctype = 'multipart/form-data';
  form.appendChild(filefield);
  this._content.appendChild(form);

  $(filefield).change(function () {
    $(form).submit();
  });

  var layer;

  function error() {
    $(layer._dom).animate({backgroundColor: '#ffaaaa'});
  }

  var self = this;
  $(form).ajaxForm({
    url: CM.APPNAME + '/layer',
    dataType: 'json',
    data: csrf(),
    iframe: true,
    beforeSubmit: function (arr, form, options) {
      var filename = filefield.value;
      if (filename.length < 1) {
        $(form).animate({backgroundColor: '#ffaaaa'})
          .animate({backgroundColor: 'transparent'});
        return false;
      }
      var ext = filename.slice(-4);
      if (ext != '.kml' && ext != '.kmz') {
        if (!confirm(['The file extension is not .kml nor .kmz. Continue ',
                      'with unexpected file extension?'].join(''))) {
          filefield.value = '';
          $(form).css({backgroundColor: '#ffaaaa'})
            .animate({backgroundColor: 'transparent'});
          return false;
        }
      }
      CM.tip(CM.TIPS['importing']);
      layer = new KMLLayer(filename);

      layer.disable();
      self._layerSection.addLayer(layer);

      // XXX HACK bug in jquery.form
      // Remove file url serialization so that the file actually gets uploaded.
      arr.shift();
    }, 
    success: function (response, s, xhr) {
      var filename = filefield.value;
      filefield.value = '';

      self._layerSection._importer.importURL(
          response['url'], function (mapLayer) {
        self.setMapLayer(layer, mapLayer);
      }, function (kmlobj, tour) {
        if (tour) {
          layer.setTour(tour);
        }
      }, error
      );
    },
    error: error
  });
}

KMLLayerCreatorUpload.prototype = new KMLLayerCreator();


function KMLLayerCreatorLink() {
  LayerCreator.call(this);
  var linkfield = document.createElement('INPUT');
  linkfield.name = 'link';
  linkfield.type = 'text';

  var submit = document.createElement('INPUT');
  submit.value = 'Load URL';
  submit.type = 'submit';

  var form = document.createElement('FORM');
  form.appendChild(linkfield);
  form.appendChild(submit);
  this._content.appendChild(form);

  var layer;

  function error() {
    $(layer._dom).animate({backgroundColor: '#ffaaaa'});
  }

  var self = this;
  $(form).submit(function (event) {
    event.preventDefault();
    event.stopPropagation();
    CM.tip(CM.TIPS['importing']);
    var url = linkfield.value;
    linkfield.value = '';

    layer = new KMLLayer(url);
    layer.disable();
    self._layerSection.addLayer(layer);
    self._layerSection._importer.importURL(url, function (mapLayer) {
      self.setMapLayer(layer, mapLayer);
    }, function (kmlobj, tour) {
      if (tour) {
        layer.setTour(tour);
      }
    }, error
    );
    return false;
  });
}

KMLLayerCreatorLink.prototype = new KMLLayerCreator();


function NAVLayerSection() {
  LayerSection.call(this, 'NAVs');
  this.creator = new NAVLayerCreator();
  this.addLayer(this.creator);
  this._importer = new ImportNAV();

  $(this._dom).tipTipTip({defaultPosition: 'right', content: CM.TIPS['nav']});
}

NAVLayerSection.prototype = new LayerSection();


function NAVLayer(filename, color) {
  Layer.call(this);

  addColorBox(this, color);

  $('<span class="nav-filename"></span>').html(filename).appendTo(this._content);
  this._accessory.appendChild(document.createTextNode('x'));
  var self = this;
  $(this._accessory).click(function () {
    self.remove();
  });

  this._mapobj = null;
  this._color = null;
}

NAVLayer.prototype = new Layer();

NAVLayer.prototype._on = function () {
  if (!this._mapobj) {
    return;
  }
  this._mapobj.setMap(this._layerSection._layerView._model._map);
};

NAVLayer.prototype._off = function () {
  if (!this._mapobj) {
    return;
  }
  this._mapobj.setMap(null);
};

NAVLayer.prototype.setColor = function (color) {
  if (this._mapobj) {
    this._mapobj.set('strokeColor', color);
  }
  this._color = color;
};

NAVLayer.prototype.remove = function () {
  this._off();
  Layer.prototype.remove.call(this);
};

function NAVLayerCreator() {
  LayerCreator.call(this);

  var filefield = document.createElement('INPUT');
  filefield.name = 'file';
  filefield.type = 'file';

  var form = document.createElement('FORM');
  form.enctype = 'multipart/form-data';
  form.appendChild(filefield);
  this._content.appendChild(form);

  $(filefield).change(function () {
    $(form).submit();
  });

  var layer;
  
  function error() {
    $(layer._dom).animate({backgroundColor: '#ffaaaa'});
  }

  var self = this;
  $(form).ajaxForm({
    url: CM.APPNAME + '/layer',
    dataType: 'json',
    data: csrf(),
    iframe: true,
    beforeSubmit: function (arr, form, options) {
      var filename = filefield.value;
      if (filename.length < 1) {
        $(form).animate({backgroundColor: '#ffaaaa'})
          .animate({backgroundColor: 'transparent'});
        return false;
      }
      var ext = filename.slice(-6);
      if (ext != 'na.txt') {
        if (!confirm(['The file extension is not na.txt. Continue ',
                      'with unexpected file extension?'].join(''))) {
          filefield.value = '';
          $(form).css({backgroundColor: '#ffaaaa'})
            .animate({backgroundColor: 'transparent'});
          return false;
        }
      }
      CM.tip(CM.TIPS['importing']);
      layer = new NAVLayer(filename);
      layer.disable();
      self._layerSection.addLayer(layer);

      // XXX HACK bug in jquery.form
      // Remove file url serialization so that the file actually gets uploaded.
      arr.shift();
    }, 
    success: function (response, s, xhr) {
      var filename = filefield.value;
      filefield.value = '';

      self._layerSection._importer.importURL(response['url'],
                                             function (imported) {
        layer._mapobj = imported.mapsLayer;

        layer.setColor(nextColor());
        layer.enable();
        layer.setOn(true);
      });
    },
    error: error
  });
}

NAVLayerCreator.prototype = new LayerCreator();


if (window.CCHDO && window.CCHDO.MAP) {
  window.CCHDO.MAP.Layers = {
    LayerView: LayerView,
    DefaultLayerView: DefaultLayerView,
    LayerSection: LayerSection,
    Layer: Layer,
    LayerCreator: LayerCreator
  };
}

})();

google.setOnLoadCallback(CCHDO.MAP.load);