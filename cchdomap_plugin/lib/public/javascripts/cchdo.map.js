// Dependecies:
// >=jQuery 1.4.0
// jQuery UI
// kmldomwalk
// google.maps v2 (v3 does not have enough features yet, e.g. stop event
//                 bubbling, google earth)
// google.visualization [table]

function defaultTo(x, d) { return x ? x : d; };
var GM = google.maps;
var listenTo = GM.Event.addListener;

var CCHDO = defaultTo(CCHDO, {});
var CM = CCHDO.MAP = {
  map: null,
  MIN_TIME: 1967,
  MAX_TIME: new Date().getFullYear(),
  APPNAME: '/search_maps',
  LOADING_IMG: '<img src="/images/rotate.gif" />',
  TIP_FADE_TIME: 4000,
  Z: {
    'region': 1,
    'inactive': 2,
    'transient': 3,
    'active': 4
  }
};

CM.TIPS = {
  'searching': 'Searching '+CM.LOADING_IMG,
  'searcherror': 'Encountered error while searching',
  'noresults': 'No cruises found',
  'escape': 'Press ESC to cancel drawing. The drawing will be editable later.',
  'importing': 'Importing '+CM.LOADING_IMG,
  'shape': 'Select a shape or keep clicking for a polygon',
  'polyclose': ['Double click or click on starting vertex to close ',
    'the polygon.'].join(''),
  'polyedit': 'Drag the vertices to edit the polygon',
  'timeswap': ['Swapped min time with max time; ',
    'the values you entered were not min/max.'].join(''),
  'search': ["Search a specific parameter using the following syntax in ",
    "the textbox to the left: parameter:query. For example, ship:knorr ",
    "line:p10 chief_scientist:swift. The following parameters are valid: ",
    "Group, Chief_Scientist, ExpoCode, Alias, Ship, Line. Refine your ",
    "search results with the tools on the right and click ",
    '"Search."'].join('')
};

CM.host = (function () {
  var loc = window.location;
  return [loc.protocol, '//', loc.host].join('');
})();

CM.GE = function (func) {
  CM.map.getEarthInstance(function (ge) {
    if (ge) {
      func(ge);
    }
  });
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
    return new GM.LatLng(center.lat(),
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
        new GM.Point(center.x + radius * Math.cos(aRad),
                     center.y + radius * Math.sin(aRad))));
    }
    
    return new GM.Polygon(pts, color, 2, 0.5, color, 0.5);
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

//  -make new ShapeMgr and set it's status as drawing.
//  -next click goes to ShapeMgr and pops up a tip: Select shape or keep
//  -clicking and pops up a shapebox
//   -hovering over shape snaps the SS into a preview
//   -clicking a shape snaps the SS into that shape and locks its type to shape
//  -clicking off the shapebox inserts a new vertex and locks the type to poly
//  -on hover:
//   -selection becomes editable (vertices shown, split points shown)
//   -dragging moves selection.
//   -right click menu
//    -delete
//   -on hover over vertex
//    -lat, lng box is shown (auto focus box for keyboard)
//    -delete
CM.SmartShape = (function () {
  function _(mgr, latlng) {
    var opts = {
      strokeColor: '#05a',
      strokeWeight: 3,
      strokeOpacity: 0.8,
      fillColor: '#05a',
      fillOpacity: 0.5,
      opts: {}
    };

    var self = this;
    this.mgr = mgr;
    this.shape = 'polygon';
    this.poly = new GM.Polygon(
      [latlng], opts.strokeColor, opts.strokeWeight, opts.strokeOpacity,
      opts.fillColor, opts.fillOpacity, opts.opts);
    CM.map.addOverlay(this.poly);
    this.poly.enableDrawing();
    CM.tip(CM.TIPS['escape']);
    listenTo(self.poly, 'lineupdated', function () {
      if (self.poly.getVertexCount() == 2) {
        CM.tip(CM.TIPS['shape']);
        mgr.showShapebox(self);
      } else if (self.poly.getVertexCount() == 3) {
        CM.tip(CM.TIPS['polyclose']);
        mgr.hideShapebox();
      }
      $(self).trigger('delta');
    });
    listenTo(self.poly, 'endline', function () {
      CM.tip();
      $(self).trigger('complete');
    });
    listenTo(self.poly, 'mouseover', function () {
      if (!self.shape) {
        CM.tip(CM.TIPS['polyedit']);
        this.enableEditing();
      }
    });
    listenTo(self.poly, 'mouseout', function () {
      if (!self.shape) {
        this.disableEditing();
        CM.tip();
      }
    });
    listenTo(mgr.map, 'singlerightclick', function (pt, src, overlay) {
      if (self.poly === overlay) {
        self.remove();
      }
    });
  }
  var _p = _.prototype;
  _p.form = function (shape) {
    console.log('forming', shape);
    this.poly.disableEditing();
    var one = this.poly.getVertex(0),
        two = this.poly.getVertex(1);
    if (shape == 'rectangle') {
      var vs = [];
      if (one.lat() > two.lat()) {
        vs[0] = new GM.LatLng(one.lat(), two.lng());
        vs[1] = new GM.LatLng(two.lat(), one.lng());
      } else {
        vs[0] = new GM.LatLng(two.lat(), one.lng());
        vs[1] = new GM.LatLng(one.lat(), two.lng());
      }
      this.poly.insertVertex(1, vs[0]);
      this.poly.insertVertex(3, vs[1]);
      this.poly.insertVertex(4, one);
    } else if (shape == 'circle') {
      var circle = CM.get_circle(one, one.distanceFrom(two) / 1000, '#0af');
      for (var i = 0; i < circle.getVertexCount(); i++) {
        this.poly.insertVertex(i+2, circle.getVertex(i));
      }
      this.poly.deleteVertex(0);
      this.poly.deleteVertex(0);
    } else {
      console.log("Unknown preset shape", shape);
    }
    this.shape = shape;
    this.mgr.hideShapebox();
    CM.tip();
    $(this).trigger('complete');
  };
  _p.remove = function () {
    this.poly.disableEditing();
    CM.map.removeOverlay(this.poly)
    $(this).trigger('removed');
    CM.tip();
  };
  _p.toJSON = function () {
    var vertices = [];
    var latlng;
    for (var i = 0; i < this.poly.getVertexCount(); i++) {
      latlng = this.poly.getVertex(i);
      vertices.push(latlng.lng()+','+latlng.lat());
    }
    return { shape: this.shape, v: vertices.join('_') };
  };
  return _;
})();

// Selection Manager
// Tracks selections on the map and which results are associated with them.
CM.ShapeMgr = (function () {
  function _(map) {
    var self = this;
    this.map = map;
    this.shapes = [];
    this.current = null;
    this.starting = false;
    this.shapebox = new CM.TransientPop(self.map, {position: 'absolute'});
    this.timebox = new CM.TransientPop(self.map,
      {position: 'absolute', bottom: 0, width: '60%', left: '15%'});
    this.timerange = $('#timerange').detach();
    var cancelHandler = function (event) {
      if (event.keyCode == KEY_ESC) {
        $(window).unbind('keyup', cancelHandler);
        self.current.remove();
        self.current = null;
        self.hideShapebox();
        CM.tip();
      }
    };

    // Any clicks on the map that are not associated with something else should
    // should begin a new selection. TODO
    var KEY_ESC = 27;
    listenTo(self.map, 'click', function (overlay, latlng) {
      if (!self.current && self.starting) {
        self.starting = false;
        self.current = new CM.SmartShape(self, latlng);
        $(self.current)
          .bind('complete', function () {
            $(window).unbind('keyup', cancelHandler);
            self.shapes.push(self.current);
            $(self).trigger('newshape', [self.shapes.length - 1, self.current]);
            self.current = null;
            // Listen for further changes to the shape.
            $(this).bind('delta', function () {
              console.log('deltaed');
            });
          })
          .bind('removed', function () {
            for (var i in self.shapes) {
              if (self.shapes[i] === this) {
                self.shapes.splice(i, 1);
              }
              if (self.shapes.length < 1) {
                self.hideTimebox();
              }
            }
          });
        $(window).bind('keyup', cancelHandler);
      }
    });
    $(self).bind('newshape', function (event, i, shape) {
      if (i == 0) {
        self.showTimebox();
      }
      console.log('newshape');
      $.ajax({
        url: CM.APPNAME+'/ids',
        dataType: 'json',
        data: {
          shapes: $.map(self.shapes, function (e) { return e.toJSON(); }),
          min_time: $('#min_time').val(),
          max_time: $('#max_time').val()
        },
        beforeSend: function (xhr) { CM.tip(CM.TIPS['searching']); },
        error: function (xhr) { CM.tip(CM.TIPS['searcherror']); },
        success: function (response, textStatus, xhr) {
          if (response) {
            CM.tip();
            CM.tracks_handler(response);
          } else {
            CM.tip('No cruises found');
          }
        }
      });
    });
  }
  var _p = _.prototype;
  _p.start = function () {
    this.starting = true;
  };
  _p.showShapebox = function (shape) {
    var self = this;
    var latlng = shape.poly.getVertex(1);
    var point = this.map.fromLatLngToContainerPixel(latlng);
    this.shapebox._pop.css({top: point.y, left: point.x});
    this.shapebox.set('placeholder');
    this.shapebox._pop.empty();
    $('<img src="/images/cchdomap/select_rectangle_button_off.gif" />')
      .click(function () { shape.form('rectangle'); })
      .appendTo(this.shapebox._pop);
    $('<img src="/images/cchdomap/select_circle_button_off.gif" />')
      .click(function () { shape.form('circle'); })
      .appendTo(this.shapebox._pop);
    if (!this.shapebox._pop.is(':empty')) {
      $('<div class="clickable">Close</div>')
        .css({'font-size': 'small', 'position': 'absolute',
              'top': 0, 'right': 0})
        .appendTo(this.shapebox._pop)
        .click(function () {
          self.hideShapebox();
        });
    }
  };
  _p.hideShapebox = function () {
    this.shapebox.set();
  };
  _p.showTimebox = function () {
    this.timebox.set(this.timerange);
    this.timebox._pop.hover(function () { $(this).fadeTo('fast', 1); },
                            function () { $(this).fadeTo('slow', 0.2); })
                     .fadeTo('slow', 0.2);
    CM.initTimeSlider();
  };
  _p.hideTimebox = function () {
    this.timebox.set();
  };
  return _;
})();

CM.importpt = {
  importedCircles: [],
  setActive: function () {
    this.clear();
    CM.results.clear();
    var latlngs = $.map($('#latlons').val().split("\n"), function (x) {
      var latlng = $.map(x.split(', '), function (x) {return parseInt(x, 10);});
      return new GM.LatLng(latlng[0], latlng[1]);
    });
    if (latlngs.length > 0) {
      this.mark(latlngs, parseInt($('#import_radius').val(), 10));
    }
  },
  clear: function () {
    while (this.importedCircles.length > 0) {
      this.importedCircles.pop().setMap(null);
    }
  },
  mark: function (latlngs, radius) {
    for (var i=0; i < latlngs.length; i++) {
      var marker = new GM.Marker({
        position: latlngs[i],
        icon: CM.plot.icon_station_marker,
        map: CM.map
      });
      this.importedCircles.push(marker);
      var circle = CM.get_circle(latlngs[i], radius, '#88ff88');
      circle.setMap(CM.map);
      this.importedCircles.push(circle);
    }
  }
};

CM.importFile = {
  gotoImported: function (jobj) {
    if (jobj.data('kml')) {
      var kml = jobj.data('kml');
      CM.GE(function (ge) {
        ge.getFeatures().appendChild(kml);
        if (kml.getAbstractView) {
          ge.getView().setAbstractView(kml.getAbstractView());
        }
      });
    } else {
      var polyline = jobj.data('nav');
      polyline.setMap(CM.map);
      CM.map.setCenter(polyline.getBounds().getCenter());
    }
  },
  removeImported: function (jobj) {
    if (jobj.data('kml')) {
      var kml = jobj.data('kml');
      CM.GE(function (ge) {
        ge.getFeatures().removeChild(kml);
      });
    } else {
      var polyline = jobj.data('nav');
      polyline.setMap(null);
    }
  },
  newImportedFile: function (file) {
    var x = $('<div>'+file+'</div>')
      .appendTo('#imported_files')
      .prepend($('<input type="checkbox" checked="true" />').click(function () {
        if ($(this).is(':checked')) {
          CM.importFile.gotoImported($(this).parent());
        } else {
          CM.importFile.removeImported($(this).parent());
        }
      }))
      .append($(['<span style="width: 2em;">&nbsp;</span>',
                 '<a href="#">Delete</a>',
                 '<span style="width: 2em;">&nbsp;</span>'].join(''))
      .click(function () {
        CM.importFile.removeImported($(this).parent());
        $(this).parent().removeData('kml').removeData('nav').remove();
      }));
    console.log(x);
    return x;
  },
  getKmlTour: function (kmlobj) {
    var tour = null;
    CM.GE(function (ge) {
      new GEarthExtensions(ge).dom.walk({rootObject: kmlobj, features: true,
        geometries: false,
        visitCallback: function (context) {
        if (this.getType() == 'KmlTour') {
          tour = this;
          return false; // Stop walking.
        }
      }});
    });
    return tour;
  },
  importKMLFile: function (file, filename) {
    CM.GE(function (ge) {
      google.earth.fetchKml(ge, CM.host() + '/'+file, function (kmlobj) {
        if (kmlobj) {
          var importedFile = CM.importFile.newImportedFile(filename)
                                          .data('kml', kmlobj);
          var tour = CM.importFile.getKmlTour(kmlobj);
          if (tour) {
            importedFile.append($(' <a href="#">Play</a>').click(function () {
              CM.GE(function (ge) {
                ge.getTourPlayer().setTour(tour);
                ge.getTourPlayer().play();
              });
           }));
          }
          CM.importFile.gotoImported(importedFile);
        } else {
          alert('Sorry, there was an error loading the file.');
        }
      });
    });
    CM.map.setMapType(G_SATELLITE_3D_MAP);
  },
  importNAVFile: function (file, filename) {
    $.ajax({type: 'GET', dataType: 'text', url: CM.host() + '/'+file,
      success: function (nav) {
        var coords = $.map(nav.split('\n'), function (coordstr) {
          var coord = coordstr.replace(/^\s+/, '').split(/\s+/);
          if (isNaN(coord[0]) || isNaN(coord[1])) { return null; }
          return new GM.LatLng(parseFloat(coord[1]), parseFloat(coord[0]));
        });
        var color = $('#navcolor').val();
        if (!color) { color = '#f00'; }
        var polyline = new GM.Polyline({path: coords, strokeColor: color});
        CM.importFile.gotoImported(CM.importFile.newImportedFile(filename)
                                   .data('nav', polyline));
      }
    });
  }
};

CM.pane = (function () {
  var active = false,
      shaded = false,
      map_ratio = 0.55,
      handle_width = 15;
  var map_space = $('#map_space');
      handle = $('#pane_handle'),
      map = $('#map'),
      pane = $('#map_pane'),
      handleimg = $('#handle_img'),
      content = $('#pane_content');

  handle.css('width', handle_width);
  handleimg.css('width', handle_width);
  content.css('marginLeft', handle_width);

  var _ = {};

  _.redraw = function () {
    width = map_space.attr('offsetWidth');
    if (active) {
      var map_width = width;
      var pane_width = handle_width;
      var handle_dir = 'left';

      if (shaded) {
        map_width -= handle_width;
        content.hide();
      } else {
        map_width *= map_ratio;
        pane_width = width - map_width;
        handle_dir = 'right';
        content.show();
      }

      map.css('width', map_width);
      pane.css({'left': map_width, 'width': pane_width});
      handleimg.attr('src', '/images/cchdomap/shade_arrow_' + handle_dir + '.png');
      pane.show();
    } else {
      map.css('width', width);
      pane.hide();
    }
    CM.map.checkResize();
    if (CM.graticule) { CM.graticule.redraw(); }
  };
  _.activate = function () {
    /* Show the pane handle and content */
    active = true;
    _.redraw();
  };
  _.deactivate = function () {
    /* Hide the pane handle and content */
    active = false;
    _.redraw();
  };
  _.shade = function () {
    /* Hide the pane contents */
    shaded = true;
    _.redraw();
  };
  _.unshade = function () {
    /* Show the pane contents */
    shaded = false;
    _.redraw();
  };
  _.toggle = function () {
    if (shaded) { _.unshade(); } else { _.shade(); }
  };

  handle.click(_.toggle);
  $(window).resize(_.redraw);
 
  return _;
})();

CM.Layer = (function () {
  var results = [];
  var _ = {};
  _.show = function () {
  };
  _.hide = function () {
  };
  _.remove = function () {
  };
  return _;
})();

/* Results
 * Pairs plots and info. This should be the only way to add tracks and info to
 * the app. */
CM.results = {
  lit: -1,
  info_entry: {},
  entry_info: {},
  add: function (id, track) {
    /* Fetch more information for the cruise record display */
    track = $.map(track, function (x) {return new GM.LatLng(x[1], x[0]);});
    $.ajax({type: 'GET', url: CM.APPNAME+'/info?id='+id, dataType: 'json',
      beforeSend: function () {CM.tip('Fetching '+id);},
      success: function (response) {
        try {
          CM.tip('Received '+id);
          var CMP = CM.plots;
          var info = response;
          if (info) {
            info.name = '<a href="/cruises/'+id+'">'+info.name+'</a>';
          } else {
            info = {'name': '<a href="/cruises/'+id+'">'+id+'</a>',
                    'programs': '', 'ship': '', 'country': '',
                    'cruise_dates': '', 'contacts': '', 'institutions': ''};
          }
          /* Plot the cruise track and do the appropriate event attaching */
          var entry_id;
          var info_id;
          if (track.length > 0) {
            CM.tip('Plotting '+id);
            entry_id = CMP.add(track);
          }

          CM.tip('Linking '+id);
          var CMR = CM.results;
          var CMI = CM.info;
          var entry = CMP.get(entry_id);
          var darken = function () { CMR.darken(entry_id); };
          var dim = function () { CMR.dim(entry_id); };
          var lighten = function () { CMR.lighten(entry_id); };
          if (entry) {
            listenTo(entry.track, 'mouseout', darken);
            listenTo(entry.track, 'mouseover', dim);
            listenTo(entry.track, 'click', lighten);
            listenTo(entry.start_station, 'mouseout', darken);
            listenTo(entry.start_station, 'mouseover', dim);
            listenTo(entry.start_station, 'click', lighten);
            info_id = CMI.add(info);
          } else {
            info_id = CMI.add(info, true);
          }

          CMR.info_entry[info_id] = entry_id;
          CMR.entry_info[entry_id] = info_id;

          CM.tip();
        } catch(e) {
          console.log('Error handling received cruise information:', e);
        }
      }
    });
  },
  clear: function () {
    for (var info_id in this.info_entry) {
      this.remove(parseInt(info_id, 10), true);
    }
  },
  remove: function (id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    var entry_id = this.info_entry[id];
    CM.plots.remove(entry_id);
    CM.info.remove(id);
    if (id == this.lit) { this.lit = -1; }
    for (var eid in this.entry_info) {
      if (this.entry_info[eid] > id) { this.entry_info[eid]--; }
    }
    var max = -1;
    for (var info_id in this.info_entry) {
      if (info_id > id) { this.info_entry[info_id-1] = this.info_entry[info_id]; }
      max = Math.max(max, info_id);
    }
    delete this.entry_info[entry_id];
    delete this.info_entry[max];
  },
  lighten: function (id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1) {
      if (this.lit > -1 && this.lit != id) {
        CM.plots.darken(this.info_entry[this.lit]);
        CM.info.darken(this.lit);
      }
      CM.plots.lighten(this.info_entry[id]);
      CM.info.lighten(id);
      this.lit = id;
    }
  },
  dim: function (id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1 && this.lit != id) {
      CM.plots.dim(this.info_entry[id]);
      CM.info.dim(id);
    }
  },
  darken: function (id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1 && this.lit != id) {
      CM.plots.darken(this.info_entry[id]);
      CM.info.darken(id);
    }
  }
};

// CM.Results
// Handles results given by id.
// add([id, ...])
// remove([id, ...])
// select([id, ...])
// deselect([id, ...])
//
// events:
// - added(ids)
// - removed(ids)
// - empty

CM.R = (function () {
  var _ = {
    element: $(),
    ids_views: {},
    selected: []
  };
  _.views = (function () {
    var V = {};
    V.plots = (function () {
      function SelectableTrack(coords, id) {
        this.coords = coords;
        this.id = id;
        this.opts = {
          initialColor: '#0a0',
          active_poly_style: {strokeColor: "#ff8800", zIndex: CM.Z['active']},
          hover_poly_style: {strokeColor: "#ffcc00", zIndex: CM.Z['transient']},
          rest_poly_style: {strokeColor: "#00aa00", zIndex: CM.Z['inactive']},
          //icon_station_marker: new GM.Icon(G_DEFAULT_ICON,
          //  CM.host() + "/images/cchdomap/station_icon.png"),
          //icon_cruise_start: new GM.Icon(G_DEFAULT_ICON,
          //  CM.host() + "/images/cchdomap/cruise_start_icon.png")
          icon_station_marker: new GM.Icon(),
          icon_cruise_start: new GM.Icon()
        };
        var cm = this.opts.icon_cruise_start;
        cm.image = CM.host() + "/images/cchdomap/cruise_start_icon.png";
        cm.iconSize = new GM.Size(24, 12);
        cm.shadowSize = new GM.Size(0, 0);
        cm.iconAnchor = new GM.Point(12, 6);
        cm.infoWindowAnchor = new GM.Point(0, 0);
                 
        var sm = this.opts.icon_station_marker;
        sm.image = CM.host() + "/images/cchdomap/station_icon.png";
        sm.iconSize = new GM.Size(2, 2);
        sm.iconAnchor = new GM.Point(1, 1);
        sm.shadowSize = new GM.Size(0, 0);
      }
      SelectableTrack.prototype = new GM.Overlay();
      SelectableTrack.prototype.initialize = function (map) {
        var self = this;
        this.map = map;
        this.isactive = false;
        this.stations = [];
    
        var polyline = this.polyline = 
          new GM.Polyline(this.coords, this.opts.initialColor, 2, 1);
        var marker = this.marker = 
          new GM.Marker(this.coords[0], this.opts.icon_cruise_start);
        
        CM.map.addOverlay(polyline);
        CM.map.addOverlay(marker);
        
        listenTo(polyline, 'click', function () {
           self.active();
           return false;
        });
        listenTo(polyline, 'mouseover', function () {
           self.hover();
           return false;
        });
        listenTo(polyline, 'mouseout', function () {
           self.rest();
           return false;
        });
        listenTo(marker, 'click', function () {
          GM.Event.trigger(polyline, 'click');
        });
        listenTo(marker, 'mouseover', function () {
          GM.Event.trigger(polyline, 'mouseover');
        });
        listenTo(marker, 'mouseout', function () {
          GM.Event.trigger(polyline, 'mouseout');
        });
      };
      SelectableTrack.prototype.remove = function () {
        this.polyline.remove();
        this.marker.remove();
      };
      SelectableTrack.prototype.redraw = function (force) {};
      SelectableTrack.prototype.show = function () {
        this.polyline.show();
        this.marker.show();
      };
      SelectableTrack.prototype.hide = function () {
        this.polyline.hide();
        this.marker.hide();
      };
      SelectableTrack.prototype.rest = function () {
        if (!this.isactive) {
          this.polyline.setStrokeStyle(
            {color: this.opts.rest_poly_style.strokeColor});
          this.isactive = false;
          for (var i = 0; i < this.stations.length; i += 1) {
            CM.map.removeOverlay(this.stations[i]); 
          }
          this.stations = [];
        }
      };
      SelectableTrack.prototype.hover = function () {
        if (!this.isactive) {
          this.polyline.setStrokeStyle(
            {color: this.opts.hover_poly_style.strokeColor});
        }
      };
      SelectableTrack.prototype.active = function () {
        if (this.isactive) {
          this.isactive = false;
          this.rest();
        } else {
          this.polyline.setStrokeStyle(
            {color: this.opts.active_poly_style.strokeColor});
          for (var i = 0; i < this.polyline.getVertexCount(); i += 1) {
            var marker = new GM.Marker(
              this.polyline.getVertex(i), this.opts.icon_station_marker);
            this.stations.push(marker);
            CM.map.addOverlay(marker);
          }
          this.isactive = true;
        }
      };
      
      var nextid = 0;
      var plots = {};
      var drilled = -1;

      var _ = {};
      _.add = function (track) {
        var coords = $.map(track, function (c) { return new GM.LatLng(c[0], c[1]); });
        var id = nextid;
        nextid += 1;
        var track = new SelectableTrack(coords, id);
        CM.map.addOverlay(track);
        plots[id] = track;
        return id;
      };
      _.get = function (id) {
        return plots[id];
      };
      _.remove = function (id) {
        CM.map.removeOverlay(plots[id]);
        delete plots[id];
      };
      _.selected = function () {
      };
      return _;
    })();
    V.table = (function () {
      var _ = {
        jdom: null,
        info_table: null,
        info_data_table: new google.visualization.DataTable({
          cols: [{label: 'Name', type: 'string'},
                 {label: 'Programs', type: 'string'},
                 {label: 'Ship', type: 'string'},
                 {label: 'Country', type: 'string'},
                 {label: 'Cruise Dates', type: 'string'},
                 {label: 'Contacts', type: 'string'},
                 {label: 'Institutions', type: 'string'}],
          rows: []
        }, 0.6), /* = wire protocol version */
        data_table_opts: {
          allowHtml: true,
          alternatingRowStyle: true,
          height: 590,
          sort: 'enable',
          sortColumn: 5,
          sortAscending: false
        },
        i_to_d: null
      };
      _.add = function (info, hasTrack) {
        var data_row = _.info_data_table.addRow([
          info.name, info.programs, info.ship, info.country,
          info.cruise_dates, info.contacts, info.institutions]);
        if (!hasTrack) {
          for (var i=0; i<_.info_data_table.getNumberOfColumns(); i++) {
            _.info_data_table.setProperty(data_row, i, 'style', 'background-color: #fdd;');
          }
        }
        return data_row;
      };
      _.get = function (id) {
        console.log('table.get', id);
      };
      _.remove = function (id) {
        console.log('table.get', id);
      };
      
      _.table_rows = function () { return $('tr', _.jdom); };
      _.setJdom = function (jdom) {
        if (_.jdom) {
          _.jdom.empty();
          delete _.info_table;
        }
        _.jdom = jdom;
        _.info_table = new google.visualization.Table(_.jdom[0]);
      
        var CMI = _;
        _.table_rows()
          .live('mouseenter', function () {
            CM.results.dim(CMI.get_id(_), true);
            return false;
          })
          .live('mouseleave', function () {
            CM.results.darken(CMI.get_id(_), true);
            return false;
          })
          .live('click', function () {
            CM.results.lighten(CMI.get_id(_), true);
            return true;
          });
        google.visualization.events.addListener(_.info_table, 'sort', function (event) {
          CMI.sync_sortorder(event);
        });
      };
      _.sync_sortorder = function (sortorder) {
        if (!sortorder) {return;}
        _.data_table_opts.sortColumn = sortorder.column;
        _.data_table_opts.sortAscending = sortorder.ascending;
        _.i_to_d = sortorder.sortedIndexes;
      };
      _.row_to_id = function (row) {
        if (_.i_to_d) { return _.i_to_d[row]; }
        return row;
      };
      _.id_to_row = function (id) {
        if (_.i_to_d) { return _.i_to_d.indexOf(id); }
        return id;
      };
      _.get_id = function (tr) {
        return _.row_to_id(_.get_row_num(tr));
      };
      _.get_row = function (id) {
        return _.table_rows()[_.id_to_row(id)+1];
      };
      _.get_row_num = function (tr) {
        for (var i=1; i<_.table_rows().length; i++) {
          var itr = _.table_rows()[i];
          if (tr === itr) { return i-1; }
        }
        return -1;
      };
      _.remove = function (id) { _.info_data_table.removeRow(id); _.redraw(); };
      _.lighten = function (id) {
        _.info_table.setSelection([{row: id}]);
        _.selected = _.info_table.getSelection();
      };
      _.dim = function (id) {
        var row = _.get_row(id);
        var selection = _.info_table.getSelection();
        if (selection.length <= 0 || selection[0].row != id) {
          $(row).addClass('google-visualization-table-tr-over');
        }
      };
      _.darken = function (id) {
        var row = _.get_row(id);
        $(row).removeClass('google-visualization-table-tr-over');
        var selection = _.info_table.getSelection();
        if (selection.length > 0) {
          for (var i in selection) {
            if (selection[i].row == id) {
              selection.splice(i, 1);
              _.info_table.setSelection(selection);
            }
          }
        }
      };
      _.redraw = function () {
        if (_.info_table) {
          _.info_table.draw(_.info_data_table, _.data_table_opts);
          _.sync_sortorder(_.info_table.getSortInfo());
          if (_.selected) { _.info_table.setSelection(_.selected); }
        }
      };
      _.popout = function () {
        if (CM.info_table_popped) { return; }
        CM.pane.deactivate();
        CM.info_table_popped = window.open('', 'info_table_popped',
                                           'toolbar=0,location=0');
        var doc = CM.info_table_popped.document;
        doc.write('<div id="centering"><div id="info_table"></div></div>');
        /* Closing the document lets the window be written to later. I know, weird. */
        doc.close();
        doc.title = document.title + ' Results';
        $('head', doc)
          .append($('<base href="' +CM.host() + '" />', doc))
          .append($('<link rel="icon" type="image/x-icon" href="favicon.ico" />', doc));
        $('link').each(function () {
          if (this.rel == 'stylesheet') {
            $(['<link href="', this.href, '" rel="stylesheet" type="text/css" ',
               'media="screen" />'].join(''), doc)
              .appendTo($('head', doc));
          }
        });
        $(['<div id="pop_button" class="clickable">Close window ',
           '<img src="images/cchdomap/popin.png" ',
           'title="Popin" alt="Popin" /></div>'].join(''))
          .click(_.popin)
          .prependTo($('#centering', doc));
        if (CM.info_table_popped) {
          _.setJdom($('#info_table', doc));
          _.redraw();
        }
      };
      _.popin = function () {
        CM.info_table_popped.close();
        delete CM.info_table_popped;
        _.setJdom($('#info_table'));
        CM.pane.activate();
        CM.pane.unshade();
        _.redraw();
      };

      $('#pop_button').addClass('clickable').click(_.popout);
      (function popup_close_guard() {
        if (CM.info_table_popped && CM.info_table_popped.closed) { CM.info.popin(); }
        setTimeout(popup_close_guard, 1000);
      })();
      _.setJdom($('#info_table'));

      return _;
    })();
    return V;
  })();

  _.add = function (ids_tracks) {
    //_.plots.bind('added', {map: _.ids_views}, function (e, id, plot) {
    //  e.data.map[id].plot = plot;
    //});
    //_.table.bind('added', {map: _.ids_views}, function (e, id, row) {
    //  e.data.map[id].row = row;
    //});
    var ids = [], track_ids = [];
    $.each(ids_tracks, function (id, track_id) {
      if (id in _.ids_views) { return; }
      ids.push(id);
      track_ids.push(track_id);
    });
    if (ids.length < 1) {
      return;
    }
    var infos = null, tracks = null; // TODO eliminate unneccessary data fetches
    $.ajax({type: 'GET', dataType: 'json',
      url: [CM.APPNAME, '/info'].join(''),
      data: {ids: ids},
      beforeSend: function () { CM.tip('Fetching infos'); },
      success: function (info) {
        CM.tip('Received infos');
        infos = info;
      },
      error: function () {
        console.log('oops info');
      },
      async: false
    });
    $.ajax({type: 'GET', dataType: 'json',
      url: [CM.APPNAME, '/track'].join(''),
      data: {ids: track_ids},
      beforeSend: function () { CM.tip('Fetching tracks'); },
      success: function (track) {
        CM.tip('Received tracks');
        tracks = track;
      },
      error: function () {
        console.log('oops tracks');
      },
      async: false
    });
  
    $.each(ids, function (i, id) {
      var info = infos[id], track = tracks[id];
      console.log(info, track);
  
      _.ids_views[id] = { plot: null, row: null };
  
      if (track) {
        _.views.plots.add(track);
      }
      _.views.table.add(info, track);
    });
    _.views.table.redraw();
    CM.tip();
  };
  _.remove = function (ids) {
    $.each(ids, function (i, id) {
      _.views.plots.remove(_.ids_views[id].plot);
      _.views.table.remove(_.ids_views[id].row);
      delete _.ids_views[id];
    });
    var empty = true;
    for (var i in _.ids_views) {
      empty = false;
      break;
    }
    if (empty) {
      _.trigger('empty');
    }
  };
  _.clear = function () {
    for (var id in _.ids_views) {
      _.views.plots.remove(_.ids_views[id].plot);
      _.views.table.remove(_.ids_views[id].row);
    }
    _.ids_views = {};
    _.trigger('empty');
  };
  _.select = function (ids) {
    $.merge(_.selected, ids);
  };
  _.deselect = function (ids) {
  };
  _.hover = function (ids) {
  };
  _.dehover = function (ids) {
  };
  _.bind = function () {
    _.element.bind(arguments);
  };
  _.trigger = function () {
    _.element.trigger(arguments);
  };
  return _;
})();

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

CM.tip = function (tip) {
  if (!CM._tipster) {
    CM._tipster = new CM.TransientPop(CM.map);
  }
  CM._tipster.set(tip);
  if (CM._tipster_time) {
    clearTimeout(CM._tipster_time);
  }
  CM._tipster_time = setTimeout(function () {
    CM._tipster.set();
  }, CM.TIP_FADE_TIME);
};

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

CM.gridOn = function () { return $('#gridon').is(':checked'); };

CM.setGrid = function(on) {
  CM.GE(function (ge) {
    ge.getOptions().setGridVisibility(on);
  });
  if (on) {
    CM.graticule.show();
  } else {
    CM.graticule.hide();
  }
};

CM.initGE = function () {
  CM.GE(function (ge) {
    var opts = ge.getOptions();
    opts.setGridVisibility(CM.gridOn());
    opts.setAtmosphereVisibility($('#atmosphereon').is(':checked'));
  });
};

CM.initDialogs = function () {
  function togglify(jdom, className, overrides) {
    var opts = {
      autoOpen: false,
      draggable: false,
      resizable: false,
      open: function () {
        var s = $(className);
        s.attr('src', s.attr('src').replace('off', 'on'));
        $(':text', this).focus();
      },
      close: function () {
        var s = $(className);
        s.attr('src', s.attr('src').replace('on', 'off'));
      }
    };
    for (var k in overrides) {
      opts[k] = overrides[k];
    }
    jdom.dialog(opts);
    $(className).click(function () {
      if (jdom.dialog('isOpen')) {
        jdom.dialog('close');
      } else {
        jdom.dialog('open');
      }
    })
    .addClass('clickable');
  }

  // Search dialog
  var searchDialog = $('<div id="search" title="Search"></div>')
    .append($([
       '<form method="GET">',
       '<input type="text" name="q" />',
       '<input type="submit" value="Search" />',
       '</form>'].join('')));
  togglify(searchDialog, '.toggle.search');
  $('form', searchDialog)
    .ajaxForm({
      url: CM.APPNAME+'/ids',
      dataType: 'json',
      beforeSubmit: function (arr, form, options) {
        searchDialog.dialog('close');
        CM.tip(CM.TIPS['searching']);
        CM.results.clear(); // TODO ask whether to clear or not
      },
      error: function () {
        CM.tip(CM.TIPS['searcherror']);
      },
      success: function (response, textStatus, xhr) {
        CM.tip();
        CM.tracks_handler(response);
      }
    });

  // Settings dialog
  var settingsDialog = $('<div id="settings" title="Settings"></div>');
  togglify(settingsDialog, '.toggle.settings', {width: 500, minWidth: 500,
    position: ['left', 'bottom']});
  $('#settings').detach().attr('id', '').appendTo(settingsDialog);

  // Layers dialog
  var layersDialog = $('<div id="layers" title="Layers"></div>')
  togglify(layersDialog, '.toggle.layers', {width: 500, minWidth: 500,
    position: ['right', 'bottom']});
  $('#layers').detach().appendTo(layersDialog);
  $('form', layersDialog)
    .ajaxForm({
      url: CM.APPNAME+'/layer',
      dataType: 'json',
      beforeSubmit: function (arr, form, options) {
        options.dataType = 'text';
        var filename = $('#layers input[name=kml]').val();
        if (filename == '') { alert('Please specify a file'); return false; }
        var filetype = $('#layers input[name=filetype]:checked').val();
        var ext = filename.slice(-4);
        if (filetype == 'KML' && ext != '.kml' && ext != '.kmz') {
          if (!confirm(['You said you were importing a KML file. Continue ',
                        'with unexpected extension that is not .kml or ',
                        '.kmz?'].join(''))) {
            return false;
          }
        }
        if (filetype != 'KML' && filename.slice(-6) != 'na.txt') {
          if (!confirm('You said you are importing a NAV file. Continue '+
                       'with unexpected extension that is not na.txt?')) {
            return false;
          }
        }
        CM.tip(CM.TIPS['importing']);
      }, 
      success: function (response) {
        var filename = $('#layers input[name=kml]').val();
        var filetype = $('#layers input[name=filetype]:checked').val();
        if (filetype == 'KML') {
          CM.importFile.importKMLFile(response, filename);
        } else {
          CM.importFile.importNAVFile(response, filename);
        }
        CM.tip();
      }
    });

  // GEarth dialog
  var gearthDialog = $('<div id="gearth" title="gearth"></div>');
  togglify(gearthDialog, '.toggle.gearth', {width: 500, minWidth: 500,
    position: 'top', title: '<img src="/images/cchdomap/gearth.gif" />'});
  $('#gearth').detach().attr('id', '').appendTo(gearthDialog);

  $('.templates').remove();
};

// Load up the app.
CM.load = function () {
  //var opts = {
  //  zoom: 3,
  //  center: new GM.LatLng(0, 0),
  //  mapTypeId: GM.MapTypeId.TERRAIN,
  //  mapTypeControl: true,
  //  mapTypeControlOptions: {
  //    style: GM.MapTypeControlStyle.DROPDOWN_MENU,
  //    mapTypeIds: [GM.MapTypeId.TERRAIN, GM.MapTypeId.SATELLITE,
  //                 GM.MapTypeId.HYBRID]
  //  },
  //  navigationControl: true,
  //  navigationControlOptions: {
  //    style: GM.NavigationControlStyle.SMALL
  //  }
  //};
  if (!GM.BrowserIsCompatible()) {
    alert('Your browser cannot run Google Maps v2');
    return false;
  }
  CM.map = new GM.Map2($('#map')[0],
    {mapTypes: [G_PHYSICAL_MAP, G_SATELLITE_MAP, G_SATELLITE_3D_MAP]});
  CM.map.setCenter(new GM.LatLng(0, 0), 3);
  CM.map.setUIToDefault();
  CM.map.setMapType(G_PHYSICAL_MAP);
  this._maptypeEar = GM.Event.addListener(CM.map, 'maptypechanged', CM.initGE);

  CM.pane.redraw();
  CM.map.setCenter(new GM.LatLng(0, 0), 3);
  CM.shapemgr = new CM.ShapeMgr(CM.map);

  $('.toggle.draw').click(function () {
    if ($(this).data('open')) {
      $(this).attr('src', $(this).attr('src').replace('off', 'on'));
      CM.shapemgr.start();
      $(this).data('open', false);
    } else {
      $(this).attr('src', $(this).attr('src').replace('on', 'off'));
      $(this).data('open', true);
    }
  });

  //$('#map_space').resizable({alsoResize: $('#map_space #map')});

  /* Page resizes while loading. Draw Graticules after page settles. */
  CM.graticule = new Graticule(CM.map);
  CM.map.addOverlay(CM.graticule);

  CM.initDialogs();

  // Set the grid to the checkbox setting and bind it to the grid checkbox
  $('#gridon').change(function () { CM.setGrid(CM.gridOn()); });

  $('#atmosphereon').change(function () {
    var checked = $(this).is(':checked');
    CM.GE(function (ge) {
      ge.getOptions().setAtmosphereVisibility(checked);
    });
  });
  
  if (CM._autoload_cruises) {
    $.ajax({type: 'GET', url: CM.APPNAME+'/tracks',
      data: 'ids='+CM._autoload_cruises, dataType: 'json',
      beforeSend: function () {CM.tip('Loading cruises '+CM.LOADING_IMG);},
      success: function (response) {
        CM.tip();
        CM.tracks_handler(response);
      }
    });
  }
};
google.setOnLoadCallback(CM.load);
