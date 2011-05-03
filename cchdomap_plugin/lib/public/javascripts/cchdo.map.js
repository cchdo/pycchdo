// Dependecies:
// >=jQuery 1.4.0
// jQuery UI
// kmldomwalk
// google.maps v3
// google.visualization [table]

function defaultTo(x, d) { return x ? x : d; };

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
  'region': '<p>Selects all cruises that pass through a defined region.</p>',
  'kml': '<p>KML or KMZ files used by Google Earth can be loaded into the map.</p>',
  'nav': '<p>NAV files have the format (in decimal degrees): </p>' + 
         '<pre>lon &lt;whitespace&gt; lat\n' + 
         'lon &lt;whitespace&gt; lat\netc.</pre>' +
         '<p>This tool displays such files as a line. One possible use is ' + 
         'comparing tracks.</p>',
  'search': "<p>You may search for specific parameters using the syntax " + 
            "'parameter:query' e.g.</p>" + 
            "<ul><li>ship:knorr</li><li>line:p10</li>" + 
            "<li>chief_scientist:swift</li></ul>" + 
            "<p>These parameters are valid:</p>" +
            "<ul><li>Group</li><li>Chief_Scientist</li><li>ExpoCode</li>" + 
            "<li>Alias</li><li>Ship</li><li>Line</li></ul>."
};

CM.util = (function () {
  var _ = {};
  _.get_radius_coord = function(center, radius) {
    if (radius <= 0) { return center; }
    var EARTH_RADIUS = 6378.137; //km
    var arclen = radius / EARTH_RADIUS;
    var deltalng = Math.acos((Math.cos(arclen) -
                              Math.pow(Math.sin(center.latRadians()), 2)) /
                              Math.pow(Math.cos(center.latRadians()), 2));
    return new google.maps.LatLng(center.lat(),
                         (center.lngRadians() + deltalng) * 180 / Math.PI);
  };
  _.get_circle_on_map_from_pts = function(map, center, outer, color) {
    var radius = Math.sqrt(Math.pow(center.x - outer.x, 2) +
                 Math.pow(center.y - outer.y, 2));
    var NUMSIDES = 20;
    var SIDELENGTH = 18;
    var sideLengthRad = SIDELENGTH * Math.PI / 180;
    var maxRad = (NUMSIDES + 1) * sideLengthRad;
    var pts = [];
    for (var aRad = 0; aRad < maxRad; aRad += sideLengthRad) {
      pts.push(map.fromContainerPixelToLatLng(
        new google.maps.Point(center.x + radius * Math.cos(aRad),
                     center.y + radius * Math.sin(aRad))));
    }
    
    return new google.maps.Polygon(pts, color, 2, 0.5, color, 0.5);
  };
  _.get_circle_on_map_from_latlngs = function(map, centerlatlng,
                                              outerlatlng, color) {
    var ll2px = map.fromLatLngToContainerPixel;
    var center = ll2px(centerlatlng);
    var outer = ll2px(outerlatlng);
    return _.get_circle_on_map_from_pts(map, center, outer, color);
  };
  return _;
})();

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

//// Tracks selections on the map and which results are associated with them.
//    this.timebox = new CM.TransientPop(self.map,
//      {position: 'absolute', bottom: 0, width: '60%', left: '15%'});
//    this.timerange = $('#timerange').detach();
//  _p.showTimebox = function () {
//    this.timebox.set(this.timerange);
//    this.timebox._pop.hover(function () { $(this).fadeTo('fast', 1); },
//                            function () { $(this).fadeTo('slow', 0.2); })
//                     .fadeTo('slow', 0.2);
//    CM.initTimeSlider();
//  };


// TODO
//  importedCircles: [],


//            info_id = CMI.add(info);
//            info_id = CMI.add(info, true);


CM.tracks_handler = function (cruise_tracks) {
  CM.R.add(cruise_tracks);
  if ($.isEmptyObject(cruise_tracks)) {
    CM.tip(CM.TIPS['noresults']);
    CM.R.clear();
  } else {
    CM.pane.activate();
    CM.pane.unshade();
  }
};

CM.get_circle = function (center, radius, polyColor) {
  if (radius <= 0) { return null; }
  var outer = CM.map.fromLatLngToContainerPixel(
    CM.util.get_radius_coord(center, radius));
  center = CM.map.fromLatLngToContainerPixel(center);
  return CM.util.get_circle_on_map_from_pts(CM.map, center, outer, polyColor);
};

CM.tip = $.jGrowl;

CM.initTimeSlider = function () {
  var min = $('#min_time'),
      max = $('#max_time'),
      slide = $('#timeslider');
  function setTimeDisplay(values) {
    min.val(values[0]);
    max.val(values[1]);
  }
  slide.slider({
    range: true,
    min: CM.MIN_TIME,
    max: CM.MAX_TIME,
    values: [CM.MIN_TIME, CM.MAX_TIME],
    slide: function (event, ui) { setTimeDisplay(ui.values); }
  });
  setTimeDisplay(slide.slider('values'));

  $('.time.coords').blur(function () {
    var max_time = parseInt(max.val(), 10);
    var min_time = parseInt(min.val(), 10);
    if (max_time < min_time) {
      min.val(max_time);
      max.val(min_time);
      CM.tip(CM.TIPS['timeswap']);
    }
    if (min_time < CM.MIN_TIME) { min.val(CM.MIN_TIME); }
    if (max_time > CM.MAX_TIME) { max.val(CM.MAX_TIME); }
  });
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

  var cchdo_map_type = 'CCHDO';
  var cchdomt = new CCHDOMapType();
  CM.map.get('mapTypes').set(cchdo_map_type, cchdomt);

  CM.earth = new EarthMapType(CM.map);

  // Add map types to menu
  var mapTypeControlOptions = CM.map.get('mapTypeControlOptions');
  var ids = mapTypeControlOptions.mapTypeIds;
  if (!ids) {
    ids = [];
  }
  ids.push(CM.earth.name);
  ids.push(cchdo_map_type);
  mapTypeControlOptions.mapTypeIds = ids;
  CM.map.set('mapTypeControlOptions', mapTypeControlOptions);;

  CM.pane = new PanedMap(domroot[0], CM.map);
  CM.pane._on = true;
  CM.pane._open = true;

  function completeInit() {
    // graticules needs to be loaded before layerview
    var lv = new CM.Layers.DefaultLayerView(CM.map);
    CM.pane.setPaneContent(lv._dom);

    $(window).resize(function () {
      domroot.height($(this).height() - 20);
      var previousFx = $.fx.off;
      $.fx.off = true;
      CM.pane.redraw();
      $.fx.off = previousFx;
    }).resize();

    CM.map.setCenter(center);

    // XXX
    var creator = lv.layerSectionSearch.creator._content;
    $(':text', creator).val('p6');
    $('form', creator).submit();

    //  $.ajax({type: 'GET', url: CM.APPNAME+'/tracks',
    //    data: 'ids='+CM._autoload_cruises, dataType: 'json',
    //    beforeSend: function () {CM.tip('Loading cruises '+CM.LOADING_IMG);},
    //    success: function (response) {
    //      CM.tip();
    //      CM.tracks_handler(response);
    //    }
    //  });
    //}
  }

  google.maps.event.addListener(CM.earth, 'initialized', completeInit);
  google.maps.event.addListener(CM.earth, 'unableToLoadPlugin', function () {
    $('[title="Change map style"]').tipTip({
      content: 'Unable to load Google Earth plugin. This may have been caused by plugin blocking.',
      exit: function () {
      }
    });
    completeInit();
  });
};

google.setOnLoadCallback(CM.load);
