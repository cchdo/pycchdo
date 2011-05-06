// Dependecies:
// >=jQuery 1.4.0
// jQuery UI
// kmldomwalk
// google.maps v3
// google.visualization [table]

function rails_csrf() {
  var data = {};
  data[$('meta[name=csrf-param]').attr('content')] =
    $('meta[name=csrf-token]').attr('content');
  return data;
}

function loadStyle(url) {
  var s = document.createElement('LINK');
  s.rel = 'stylesheet';
  s.type = 'text/css';
  s.media = 'screen';
  s.href = url;
  document.head.appendChild(s);
}

function loadScript(url) {
  var s = document.createElement('SCRIPT');
  s.type = 'text/javascript';
  s.src = url;
  document.body.appendChild(s);
}

function defaultTo(x, d) {
  return x ? x : d;
}

var CCHDO = defaultTo(CCHDO, {});
var CM = CCHDO.MAP = {
  map: null,
  host: (function () {
    var loc = window.location;
    return [loc.protocol, '//', loc.host].join('');
  })(),
  MIN_TIME: 1967,
  MAX_TIME: new Date().getFullYear(),
  APPNAME: '/cchdomap',
  LOADING_IMG: '<img src="/images/cchdomap/rotate.gif" />',
  Z: {
    'region': google.maps.Marker.MAX_ZINDEX + 1,
    'dark': google.maps.Marker.MAX_ZINDEX + 2,
    'hl': google.maps.Marker.MAX_ZINDEX + 3,
    'dim': google.maps.Marker.MAX_ZINDEX + 4,
    'dimhl': google.maps.Marker.MAX_ZINDEX + 5
  }
};

CM.TIPS = {
  'earthPluginBlocked': 
    '<p>Unable to load the Google Earth plugin.</p>' + 
    '<p>You will not be able to use 3D earth functionality.</p>' +
    '<p>This may have been caused by plugin blocking.</p>',
  'searcherror': 'Encountered error while searching',
  'importing': 'Importing '+CM.LOADING_IMG,
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
  'nav': 
    '<p>Display NAV files as a line.</p><p>This may be useful for comparing ' +
    'tracks.</p>' +
    '<p>NAV files have the format (in decimal degrees):</p>' + 
    '<pre>lon &lt;whitespace&gt; lat\n' + 
    'lon &lt;whitespace&gt; lat\netc.</pre>',
  'search': "<p>You may search for specific parameters using the syntax " + 
            "'parameter:query' e.g.</p>" + 
            "<ul><li>ship:knorr</li><li>line:p10</li>" + 
            "<li>chief_scientist:swift</li></ul>" + 
            "<p>These parameters are valid:</p>" +
            "<ul><li>Group</li><li>Chief_Scientist</li><li>ExpoCode</li>" + 
            "<li>Alias</li><li>Ship</li><li>Line</li></ul>."
};

CM.TransientPop = (function () {
  function _(map, positioning) {
    if (!positioning) {
      positioning = {
        'position': 'absolute',
        'width': '60%',
        'top': 0,
        'left': '15%', 
      };
    }
    this._pop = $('<div class="transientpop"></div>')
      .appendTo(map.getContainer())
      .css(positioning)
      .fadeTo(0, 0.8)
      .hide();
  }
  var _p = _.prototype;
  _p.set = function (pop) {
    if (pop) {
      this._pop.html(pop).fadeIn('fast');
    } else {
      this._pop.fadeOut('slow');
    }
  };
  _p.remove = function () {
    if (this._pop) {
      this._pop.fadeOut().remove();
    }
  };
  return _;
})();

// TODO
//  importedCircles: [],

CM.tip = $.jGrowl;

CM.initTimeSlider = function () {
};

CM.processHashCommands = function () {
  if (!CM.layerView) {
    return;
  }
  var hash = location.hash;
  if (hash) {
    commands = hash.substring(1).split(',');
    var searchCreator = CM.layerView.layerSectionSearch.creator._content;
    for (var i = 0; i < commands.length; i += 1) {
      var command = commands[i];
      if (/^search\:(.+)/.test(command)) {
        $(':text', searchCreator).val(command.substring('search:'.length));
        $('form', searchCreator).submit();
      } else {
  // TODO autoload cruise ids
  //    data: 'ids='+CM._autoload_cruises, dataType: 'json',
      }
    }
  }
};

CM.load = function () {
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
  CM.map = new google.maps.Map(mapdiv[0], opts);

  // TODO
  //var lltip = new LatLngTooltip(CM.map);

  var etopo_map_type = 'ETOPO';
  var etopomt = new ETOPOMapType();
  CM.map.get('mapTypes').set(etopo_map_type, etopomt);

  CM.earth = new EarthMapType(CM.map);

  // Add map types to menu
  var mapTypeControlOptions = CM.map.get('mapTypeControlOptions');
  var ids = mapTypeControlOptions.mapTypeIds;
  if (!ids) {
    ids = [];
  }
  ids.push(CM.earth.name);
  ids.push(etopo_map_type);
  mapTypeControlOptions.mapTypeIds = ids;
  CM.map.set('mapTypeControlOptions', mapTypeControlOptions);;

  CM.pane = new PanedMap(domroot[0], CM.map);
  CM.pane._on = true;
  CM.pane._open = true;

  function completeInit() {
    // graticules needs to be loaded before layerview
    CM.layerView = new CM.Layers.DefaultLayerView(CM.map);
    CM.pane.setPaneContent(CM.layerView._dom);

    $(window).resize(function () {
      domroot.height($(this).height() - 20);
      var previousFx = $.fx.off;
      $.fx.off = true;
      CM.pane.redraw();
      $.fx.off = previousFx;
    }).resize();

    CM.map.setCenter(center);

    CM.processHashCommands();
  }

  google.maps.event.addListener(CM.earth, 'initialized', completeInit);
  google.maps.event.addListener(CM.earth, 'unableToLoadPlugin', function () {
    CM.tip(CM.TIPS['earthPluginBlocked']);
    completeInit();
  });
};

google.setOnLoadCallback(CM.load);
