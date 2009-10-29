var $ = $ ? $ : function(id) { return document.getElementById(id); };
function classes_of(e) { return e.className.split(' '); }
function add_class(domelem, classname) {
  var classes = classes_of(domelem);
  if (classes.indexOf(classname) == -1) {
    classes.push(classname);
  }
  domelem.className = classes.join(' ');
}
function remove_class(domelem, classname) {
  var classes = classes_of(domelem);
  var index = classes.indexOf(classname);
  if (index != -1) {
    classes.splice(index, 1);
  }
  domelem.className = classes.join(' ');
}

var CCHDO = CCHDO ? CCHDO : {};
var CM = CCHDO.map_search = {
  map: null,
  ge: null,
  MIN_TIME: 1975,
  MAX_TIME: new Date().getFullYear()
};

/*=============================================================================
 * Controls */
var CMC = CM.ctrls = {};
CMC.deactivate_all_except = function(me) {
  CM.results.clear();
  for (var ctrl in CMC) {
    if (ctrl == 'time' || ctrl == 'deactivate_all_except' || CMC[ctrl] === me) { continue; }
    CMC[ctrl].setInactive();
  }
};
CMC.query = {
  setActive: function() {
    CMC.deactivate_all_except(this);
    $('tool').value = 'query';
  },
  setInactive: function() {
    $('tool').value = 'none';
  }
};
CMC.rectangle = {
  mark: function() {
    this.control.set_bounds(new google.maps.LatLngBounds(this.getSW(), this.getNE()));
    this.control.redraw();
  }, //sanitizing in controller
  setActive: function() {
    CMC.deactivate_all_except(this);
    $('tool').value = 'rectangle';
    this.mark();
  },
  setInactive: function() {
    $('tool').value = 'none';
    this.control.close_ear();
    this.control.erase();
  },
  sync: function() {
    this.setActive();
  },
  getSW: function() { return new google.maps.LatLng(parseFloat(this.sw_lat_box.value), parseFloat(this.sw_lng_box.value)); },
  getNE: function() { return new google.maps.LatLng(parseFloat(this.ne_lat_box.value), parseFloat(this.ne_lng_box.value)); },
  setSWBox: function(latlng) {
    this.sw_lat_box.value = latlng.lat();
    this.sw_lng_box.value = latlng.lng();
  },
  setNEBox: function(latlng) {
    this.ne_lat_box.value = latlng.lat();
    this.ne_lng_box.value = latlng.lng();
  },
  hook_moving: function(pt) {
    var latlng = CM.map.fromContainerPixelToLatLng(pt);
    CMC.rectangle.setSWBox(latlng);
    CMC.rectangle.setNEBox(latlng);
    this.setActive();
  },
  hook_dragging: function(bounds) {
    this.setSWBox(bounds.getSouthWest());
    this.setNEBox(bounds.getNorthEast());
  },
  hook_dragend: function(selection) {
    this.setSWBox(selection.getSouthWest());
    this.setNEBox(selection.getNorthEast());
    CM.recenter();
    CM.remote_submit();
  }
};
CMC.circle = {
  mark: function() {
    this.control.set_bounds(new google.maps.LatLng(parseFloat(this.center_lat_box.value),
                                                   parseFloat(this.center_lng_box.value)),
                            parseFloat(this.radius_box.value));
    this.control.redraw();
  },
  setActive: function() {
    CMC.deactivate_all_except(this);
    $('tool').value = 'circle';
    this.mark();
  },
  setInactive: function() {
    $('tool').value = 'none';
    this.control.close_ear();
    this.control.erase();
  },
  sync: function() {
    this.setActive();
  },
  setCircleCenterBox: function(bounds) {
    var latlng = bounds.latlng;
    this.center_lat_box.value = latlng.lat(); 
    this.center_lng_box.value = latlng.lng(); 
    this.radius_box.value = bounds.radius;
  },
  hook_moving: function(pt) {
    CMC.circle.setCircleCenterBox({latlng: CM.map.fromContainerPixelToLatLng(pt), radius: 0});
    this.setActive();
  },
  hook_dragging: function(bounds) {
    this.setCircleCenterBox(bounds);
  },
  hook_dragend: function(bounds) {
    CM.recenter();
    CM.remote_submit();
  }
};
CMC.polygon = {
  polygon: null,
  ear: null,
  delete_ear: null,
  drawing: false,
  ignorecnt: 0,
  drawNew: function() {
    var me = this;
    var listento = google.maps.Event.addListener;
    me.clear();
    $('polygon_status').innerHTML = 'Ready - click on first vertex.';
    if(!me.ear) {
      me.ear = listento(CM.map, 'click', function(overlay, latlng) {
        google.maps.Event.removeListener(me.ear);
        me.ear = null;
        var color = "#aa22ff";
        $('polygon_status').innerHTML = 'Drawing - click on next vertex or first vertex to end';
        me.polygon = new google.maps.Polygon([latlng], color, 3, 1.0, color, 0.5);
        //listento(me.polygon, 'mouseover', function(){me.edit();});
        //listento(me.polygon, 'mouseout', function(){me.stone();});
        CM.map.addOverlay(me.polygon);
        me.polygon.enableDrawing();
        me.drawing = true;
        listento(me.polygon, 'endline', function(){
          me.drawing = false;
          me.setActive();
          CM.remote_submit();
          $('polygon_status').innerHTML = 'Inactive - click on button to start';
        });
      });
    }
  },
  stopDraw: function() {
    if(this.polygon){
      CM.map.removeOverlay(this.polygon);
      this.polygon = null;
    }
    $('polygon_status').innerHTML = 'Inactive - click on button to start';
  },
  clear: function() {
    if(this.polygon) {
      this.stone();
      CM.map.removeOverlay(this.polygon);
    }
  },
  edit: function() {
    var me = this;
    me.polygon.enableEditing();
    if(!me.delete_ear) {
      me.delete_ear = google.maps.Event.addListener(CM.map, "singlerightclick", function(pt, src, olay){
        if(typeof(olay.index) !== "undefined"){
          me.polygon.deleteVertex(olay.index);
        }
      }); 
    }
  },
  stone: function() {
    this.polygon.disableEditing();
    if(this.delete_ear){
      google.maps.Event.removeListener(this.delete_ear);
      this.delete_ear = null;
    }
  },
  mark: function() {
    if(this.polygon) {
      CM.map.addOverlay(this.polygon);
    }
  },
  setActive: function() {
    CMC.deactivate_all_except(this);
    $('tool').value = 'polygon';
    this.mark();
    $('polygon_status').innerHTML = 'Inactive - click on button to start';
    $('polygon_status').style.color = '#aa22ff';
  },
  setInactive: function() {
    $('tool').value = 'none';
    this.clear();
  },
  sync: function() {
    this.mark();
  },
  toLineString: function() {
    var coords = [];
    for(var i=0; i<this.polygon.getVertexCount(); i++ ) {
      var v = this.polygon.getVertex(i);
      coords.push(v.lng()+' '+v.lat());
    }
    return "LINESTRING("+coords.join(', ')+")";
  }
};
CMC.importpt = {
  importedCircles: [],
  setActive: function() {
    var ctrls = CMC;
    ctrls.query.setInactive();
    ctrls.rectangle.setInactive();
    ctrls.circle.setInactive();
    ctrls.polygon.setInactive();
    this.clear();
    CM.results.clear();
    $('tool').value = 'import';
    var latlngs = $('latlons').value.split("\n").map(function(x) {
      var latlng = x.split(', ').map(function(x) {return parseInt(x, 10);});
      return new google.maps.LatLng(latlng[0], latlng[1]);
    });
    if (latlngs.length > 0) {
      this.mark(latlngs, parseInt($('import_radius').value, 10));
    }
  },
  setInactive: function() {
    $('tool').value = 'none';
    this.clear();
  },
  clear: function() {
    while (this.importedCircles.length > 0) {
      CM.map.removeOverlay(this.importedCircles.pop());
    }
  }, 
  mark: function(latlngs, radius) {
    for (var i=0; i < latlngs.length; i++) {
      var marker = new google.maps.Marker(latlngs[i], CM.entries.station_marker);
      CM.map.addOverlay(marker);
      this.importedCircles.push(marker);
      var circle = CM.get_circle(latlngs[i], radius, '#88ff88');
      CM.map.addOverlay(circle);
      this.importedCircles.push(circle);
    }
  }
};
CMC.time = {
  min_time: null,
  max_time: null,
  sanitize: function() {
    var T = CMC.time;
    var max_time = parseInt(T.max_time.value, 10);
    var min_time = parseInt(T.min_time.value, 10);
    if (max_time < min_time) {
      var tmp = T.min_time.value;
      T.min_time.value = T.max_time.value;
      T.max_time.value = tmp;
      CM.state('Swapped min time with max time; the values you entered were not min/max.');
    }
    if (min_time < CM.MIN_TIME) { T.min_time.value = CM.MIN_TIME; }
    if (max_time > CM.MAX_TIME) { T.max_time.value = CM.MAX_TIME; }
  }
};
/*=============================================================================
 * Pane */
CM.Pane = function() {
  this.resize_ear = window.addEventListener('resize', function() { CM.pane.refresh_map(); }, false);
};
CM.Pane.prototype = {
  active: false,
  shaded: false,
  resize_ear: null,
  map_ratio: 0.55,
  handle_width: 15,
  width: $('map_space').offsetWidth
};
CM.Pane.prototype.redraw = function() {
  this.width = $('map_space').offsetWidth;
  if (this.active) {
    $('pane_handle').style.width = this.handle_width+'px';
    $('handle_img').style.width = this.handle_width+'px';
    $('map_pane').style.display = 'block';
    $('pane_content').style.marginLeft = this.handle_width+'px';
    if (this.shaded) {
      var map_width = this.width - this.handle_width;
      $('map').style.width = map_width+'px';
      $('map_pane').style.left = map_width+'px';
      $('map_pane').style.width = this.handle_width+'px';
      $('handle_img').src = '/images/map_search/shade_arrow_left.png';
      $('pane_content').style.display = 'none';
    } else {
      var map_width = this.width * this.map_ratio;
      $('map').style.width = map_width+'px';
      $('map_pane').style.left = map_width+'px';
      $('map_pane').style.width = (this.width - map_width)+'px';
      $('handle_img').src = '/images/map_search/shade_arrow_right.png';
      $('pane_content').style.display = 'block';
    }
  } else {
    $('map').style.width = this.width+'px';
    $('map_pane').style.display = 'none';
  }
};
CM.Pane.prototype.activate = function() {
  /* Show the pane handle and content */
  this.active = true;
  this.refresh_map();
};
CM.Pane.prototype.deactivate = function() {
  /* Hide the pane handle and content */
  this.active = false;
  this.refresh_map();
};
CM.Pane.prototype.refresh_map = function() {
  this.redraw();
  CM.map.checkResize();
  CM.graticule.redraw();
  CM.recenter();
};
CM.Pane.prototype.shade = function() {
  /* Hide the pane contents */
  this.shaded = true;
  this.refresh_map();
};
CM.Pane.prototype.unshade = function() {
  /* Show the pane contents */
  this.shaded = false;
  this.refresh_map();
};
CM.Pane.prototype.toggle = function() {
  if (this.shaded) { this.unshade(); } else { this.shade(); }
};
CM.pane = new CM.Pane();
$('pane_handle').addEventListener('click', function() { CM.pane.toggle(); }, false);

/*=============================================================================
 * Entries */
CM.entries = {
  entries: [],
  drilled: -1,
  station_marker: {icon: new google.maps.Icon(), clickable: false},
  cruise_start_marker: {icon: new google.maps.Icon()},
  initial_color: '#00aa00',
  light_poly_style: {color: "#ff8800"},
  dim_poly_style: {color: "#ffcc00"},
  dark_poly_style: {color: "#00aa00"}
};
CM.entries.init = function() {
  var G = google.maps;
  var c = CM.entries.cruise_start_marker.icon;
  c.image = "/images/map_search/cruise_start_icon.png";
  c.iconSize = new G.Size(24, 12);
  c.shadowSize = new G.Size(0, 0);
  c.iconAnchor = new G.Point(12, 12);
  c.infoWindowAnchor = new G.Point(0, 0);
  var s = CM.entries.station_marker.icon;
  s.image = "/images/map_search/station_icon.png";
  s.iconSize = new G.Size(32, 32);
  s.shadowSize = new G.Size(0, 0);
  s.iconAnchor = new G.Point(0, 32);
  s.infoWindowAnchor = new G.Point(0, 0);
  s.imageMap = [0,0, 3,0, 3,3, 0,3];
}(); /* note the init is called! */
CM.entries.add = function(track) {
  var G = google.maps;
  var entry = {
    start_station: new G.Marker(track[0], this.cruise_start_marker),
    track: new G.Polyline(track, this.initial_color, 2, 1),
    stations: []
  };
  CM.map.addOverlay(entry.start_station);
  CM.map.addOverlay(entry.track);
  var id = this.entries.length;
  this.entries[id] = entry;
  return id;
};
CM.entries.remove = function(id) {
  var entry = this.get(id);
  if (entry === undefined) { return; }
  CM.state('Removing '+entry.expocode);
  var G = google.maps;
  var map = CM.map;
  map.removeOverlay(entry.start_station);
  map.removeOverlay(entry.track);
  while (entry.stations.length > 0) {
    CM.map.removeOverlay(entry.stations.pop());
  }
  CM.state('');
};
CM.entries.get = function(id) { return this.entries[id]; };
CM.entries.lighten = function(id) {
  var entry = this.get(id);
  if (entry === undefined) { return; }
  entry.track.setStrokeStyle(this.light_poly_style);
  entry.track.redraw(true);
  var self = this;
  setTimeout(function() {
    for (var i=1; i<entry.track.getVertexCount(); i++) {
      var station = new google.maps.Marker(entry.track.getVertex(i), self.station_marker);
      entry.stations.push(station);
      CM.map.addOverlay(station);
    }
  }, 0);
};
CM.entries.dim = function(id) {
  var entry = this.get(id);
  if (entry === undefined) { return; }
  entry.track.setStrokeStyle(this.dim_poly_style);
  entry.track.redraw(true);
};
CM.entries.darken = function(id) {
  var entry = this.get(id);
  if (entry === undefined) { return; }
  while (entry.stations.length > 0) {
    CM.map.removeOverlay(entry.stations.pop());
  }
  entry.stations = [];
  entry.track.setStrokeStyle(this.dark_poly_style);
  entry.track.redraw(true);
};

/*=============================================================================
 * Info */
CM.Info = function() {
  $('pop_button').addEventListener('click', function() { CM.info.popout(); }, false);
  (function popup_close_guard() {
    if (CM.info_table_popped && CM.info_table_popped.closed) { CM.info.popin(); }
    setTimeout(popup_close_guard, 1000);
  })();
  this.assign_domelem($('info_table'));
};
CM.Info.prototype = {
  domelem: null,
  info_table: null,
  info_data_table: new google.visualization.DataTable({
    cols: [{label: 'Line', type: 'string'},
           {label: 'ExpoCode', type: 'string'},
           {label: 'Ship', type: 'string'},
           {label: 'Country', type: 'string'},
           {label: 'PI', type: 'string'},
           {label: 'Begin Date', type: 'date'}],
    rows: []
  }, 0.6), /* = wire protocol version */
  data_table_opts: {
    allowHtml: true,
    sort: 'enable',
    height: '500px'
  },
  i_to_d: null
};
CM.Info.prototype.table_rows = function() { return this.domelem.firstChild.firstChild.firstChild.firstChild.children; }
CM.Info.prototype.assign_domelem = function(domelem) {
  if (this.domelem) {
    this.domelem.removeEventListener('mouseover', this.mouseover_ear, false);
    this.domelem.removeEventListener('mouseout', this.mouseout_ear, false);
    this.domelem.removeEventListener('click', this.click_ear, false);
    while (this.domelem.hasChildNodes()) { this.domelem.removeChild(this.domelem.lastChild); }
    delete this.info_table;
  }
  this.domelem = domelem;
  this.data_table_opts.height = this.domelem.style.height;
  this.info_table = new google.visualization.Table(this.domelem);

  var CMI = this;
  this.mouseover_ear = this.domelem.addEventListener('mouseover', function(e) {
    var tg = e.target;
    while (tg && tg !== document && tg.tagName != 'TR') { tg = tg.parentNode; } if (tg === document) { return; }
    CM.results.dim(CMI.get_id(tg), true);
    e.stopPropagation();
  }, false);
  this.mouseout_ear = this.domelem.addEventListener('mouseout', function(e) {
    /* detect REAL mouseout */
    var tg = e.target;
    var reltg = e.relatedTarget;
    if (!tg || !reltg || tg == reltg) { return; }
    while (tg && tg !== document && tg.tagName != 'TR') { tg = tg.parentNode; }
    try {
      while (reltg && reltg !== document && reltg.tagName != 'TR') { reltg = reltg.parentNode; }
    } catch (e) {}
    if (reltg.tagName == 'TR' && reltg == tg) { return; }
    if (tg === document) { tg = reltg; }
    if (!tg.children) { return; }
    CM.results.darken(CMI.get_id(tg), true);
    e.stopPropagation();
  }, false);
  this.click_ear = this.domelem.addEventListener('click', function(e) {
    CM.results.lighten(CMI.get_id(e.target.parentNode), true);
    e.stopPropagation();
  }, false);
  google.visualization.events.addListener(this.info_table, 'sort', function(event) {
    CM.info.data_table_opts.sortColumn = event.column;
    CM.info.data_table_opts.sortAscending = event.ascending;
    CM.info.i_to_d = event.sortedIndexes;
  });
};
CM.Info.prototype.row_to_id = function(row) {
  if (this.i_to_d) { return this.i_to_d[row]; }
  return row;
};
CM.Info.prototype.id_to_row = function(id) {
  if (this.i_to_d) { return this.i_to_d.indexOf(id); }
  return id;
};
CM.Info.prototype.get_id = function(tr) {
  return this.row_to_id(this.get_row_num(tr));
};
CM.Info.prototype.get_row = function(id) {
  return this.table_rows()[this.id_to_row(id)+1];
};
CM.Info.prototype.get_row_num = function(tr) {
  if (tr.tagName != 'TR' || tr.className.indexOf('tr-head') > -1) { return -1; }
  for (var i=1; i<this.table_rows().length; i++) {
    var itr = this.table_rows()[i];
    if (tr === itr) { return i-1; }
  }
  return -1;
};
CM.Info.prototype.add = function(info, notrack) {
  var data_row = this.info_data_table.addRow([info.line, info.expocode, info.ship, info.country, info.pi, info.date_begin]);
  if (notrack) {
    for (var i=0; i<this.info_data_table.getNumberOfColumns(); i++) {
      this.info_data_table.setProperty(data_row, i, 'style', 'background-color: #ffdddd;');
    }
  }
  return data_row;
};
CM.Info.prototype.remove = function(id) { this.info_data_table.removeRow(id); this.redraw(); };
CM.Info.prototype.lighten = function(id) {
  this.info_table.setSelection([{row: id}]);
  this.selected = this.info_table.getSelection();
};
CM.Info.prototype.dim = function(id) {
  var row = this.get_row(id);
  var selection = this.info_table.getSelection();
  if (selection.length <= 0 || selection[0].row != id) {
    add_class(row, 'google-visualization-table-tr-over');
  }
};
CM.Info.prototype.darken = function(id) {
  var row = this.get_row(id);
  remove_class(row, 'google-visualization-table-tr-over');
  var selection = this.info_table.getSelection();
  if (selection.length > 0) {
    for (var i in selection) {
      if (selection[i].row == id) {
        selection.splice(i, 1);
        this.info_table.setSelection(selection);
      }
    }
  }
};
CM.Info.prototype.redraw = function() {
  if (this.info_table) {
    this.info_table.draw(this.info_data_table, this.data_table_opts);
    if (this.selected) { this.info_table.setSelection(this.selected); }
  }
};
CM.Info.prototype.popout = function() {
  if (CM.info_table_popped) { return; }
  CM.pane.deactivate();
  CM.info_table_popped = window.open('', 'info_table_popped');
  var doc = CM.info_table_popped.document;
  doc.write('<div id="centering"></div>');doc.close(); /* Strange hack that lets the window be written to later. */
  doc.title = 'CCHDO Map Search Results';
  var head = doc.getElementsByTagName('head')[0];
  var base = doc.createElement('base');
  base.href = 'http://'+window.location.host;
  head.appendChild(base);
  var favicon = doc.createElement('link');
  favicon.rel = 'icon';
  favicon.type = 'image/x-icon';
  favicon.href = 'favicon.ico';
  head.appendChild(favicon);
  var links = document.getElementsByTagName('link');
  for (var i=0; i<links.length; i++) {
    if (links[i].rel == 'stylesheet') {
      var css = doc.createElement('link');
      css.href = links[i].href;
      css.rel = 'stylesheet';
      css.type = 'text/css';
      css.media = 'screen';
      head.appendChild(css);
    }
  }
  var self = this;
  var close_button = doc.createElement('img');
  close_button.src = 'images/map_search/popin.png';
  close_button.title = 'Popin';
  close_button.alt = 'Popin';
  close_button.id = 'pop_button';
  close_button.addEventListener('click', function() { self.popin(); }, false);
  doc.body.appendChild(close_button);
  if (CM.info_table_popped) {
    this.assign_domelem(doc.getElementById('centering'));
    this.redraw();
  }
};
CM.Info.prototype.popin = function() {
  CM.info_table_popped.close();
  delete CM.info_table_popped;
  this.assign_domelem($('info_table'));
  this.redraw();
  CM.pane.activate();
  CM.pane.unshade();
};
CM.info = new CM.Info();

/*=============================================================================
 * Entry Info results */
CM.results = {
  lit: -1,
  info_entry: {},
  entry_info: {},
  add: function(expocode, track) {
    /* Fetch more information for the cruise record display */
    var req = new Ajax.Request('/staff/map_search/info?expocode='+expocode,
      {asynchronous: true,
       evalScripts: true,
       onLoading: function() {
         CM.state('Fetching '+expocode);
         track = track.map(function(x) { return new google.maps.LatLng(x[0], x[1]); });
       },
       onComplete: function(request) {
         try {
           CM.state('Received '+expocode);
           var CME = CM.entries;
           var info = request.responseJSON;
           if (info) {
             info.expocode = '<a href="/search?ExpoCode='+expocode+'">'+expocode+'</a>';
             var date_begin = new Date();
             date_begin.setTime(Date.parse(info.date_begin));
             info.date_begin = date_begin;
             var date_end = new Date();
             date_end.setTime(Date.parse(info.date_end));
             info.date_end = date_end;
           } else {
             info = {'expocode': '<a href="/search?ExpoCode='+expocode+'">'+expocode+'</a>',
                     'line': null, 'ship': null, 'country': null, 'pi': null, 'date_begin': null};
           }
           /* Plot the cruise track and do the appropriate event attaching */
           var G = google.maps;
           var entry_id;
           var info_id;
           if (track.length > 0) {
             CM.state('Plotting '+expocode);
             entry_id = CM.entries.add(track);
           }

           CM.state('Linking '+expocode);
           var CMR = CM.results;
           var CMI = CM.info;
           var entry = CM.entries.get(entry_id);
           if (entry) {
             G.Event.addListener(entry.track, 'mouseout', function() { CMR.darken(entry_id); });
             G.Event.addListener(entry.track, 'mouseover', function() { CMR.dim(entry_id); });
             G.Event.addListener(entry.track, 'click', function() { CMR.lighten(entry_id); });
             G.Event.addListener(entry.start_station, 'mouseout', function() { CMR.darken(entry_id); });
             G.Event.addListener(entry.start_station, 'mouseover', function() { CMR.dim(entry_id); });
             G.Event.addListener(entry.start_station, 'click', function() { CMR.lighten(entry_id); });
             info_id = CMI.add(info);
           } else {
             info_id = CMI.add(info, true);
           }

           CMR.info_entry[info_id] = entry_id;
           CMR.entry_info[entry_id] = info_id;

           CMI.redraw();

           CM.state('');
         } catch(e) {
           console.log('Error handling received cruise information:', e);
         }
       }
      }
    );
  },
  clear: function() { for (var info_id in this.info_entry) { this.remove(parseInt(info_id, 10), true); } },
  remove: function(id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    var entry_id = this.info_entry[id];
    CM.entries.remove(entry_id);
    CM.info.remove(id);
    if (id == this.lit) { this.lit = -1; }
    for (var entry_id in this.entry_info) {
      if (this.entry_info[entry_id] > id) { this.entry_info[entry_id]--; }
    }
    var max = -1;
    for (var info_id in this.info_entry) {
      if (info_id > id) { this.info_entry[info_id-1] = this.info_entry[info_id]; }
      max = Math.max(max, info_id);
    }
    delete this.entry_info[entry_id];
    delete this.info_entry[max];
  },
  lighten: function(id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1) {
      if (this.lit > -1 && this.lit != id) {
        CM.entries.darken(this.info_entry[this.lit]);
        CM.info.darken(this.lit);
      }
      CM.entries.lighten(this.info_entry[id]);
      CM.info.lighten(id);
      this.lit = id;
    }
  },
  dim: function(id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1 && this.lit != id) {
      CM.entries.dim(this.info_entry[id]);
      CM.info.dim(id);
    }
  },
  darken: function(id, is_info_id) {
    if (!is_info_id) { id = this.entry_info[id]; }
    if (id > -1 && this.lit != id) {
      CM.entries.darken(this.info_entry[id]);
      CM.info.darken(id);
    }
  }
};

/*=============================================================================
 * Tool bar */
CM.tool_bar = {
  active: null,
  need_granularity: ['rectangle', 'circle', 'polygon', 'import'],
  tool_button_to_tool_details: {}
};
CM.tool_bar.set_active = function(tool_button) {
  if (this.active) {
    remove_class(CM.tool_bar.active, 'active');
    this.tool_button_to_tool_details[this.active.id].style.display = 'none';
    if (this.need_granularity.indexOf(this.active.id.replace('_button', '')) != -1) {
      $('granularity').style.display = 'none';
    }
    $('tool').value = 'none';
  }
  add_class(tool_button, 'active');
  this.active = tool_button;
  var details = this.tool_button_to_tool_details[tool_button.id];
  details.style.display = 'block';
  if (this.need_granularity.indexOf(tool_button.id.replace('_button', '')) != -1) {
    $('granularity').style.display = 'block';
  }
  var tool = $('tool').value = this.active.id.replace('_button', '');
  if (tool == 'query') {
    CMC.query.setActive();
  } else if (tool == 'rectangle') {
    CMC.rectangle.setActive();
  } else if (tool == 'circle') {
    CMC.circle.setActive();
  } else if (tool == 'polygon') {
    CMC.polygon.setActive();
  } else if (tool == 'import') {
    CMC.importpt.setActive();
  }
};
CM.tool_bar.init = function() {
  var tool_bar = $('tool_bar');
  var tool_buttons = tool_bar.children;
  var self = this;
  for (var i=0; i < tool_buttons.length; i++) {
    var tool_button = tool_buttons[i];
    /* Skip non-buttons, e.g. state */
    if (tool_button.className.indexOf('tool_button') == -1) { continue; }
    this.tool_button_to_tool_details[tool_button.id] = $(tool_button.id.replace('_button', '')+'_details');
    tool_button.addEventListener('click', function(e) {
      if (this === self.active) {
        var tool = $('tool').value;
        if (tool == 'rectangle') {
          CMC.rectangle.control.erase();
          CMC.rectangle.control.open_ear();
        } else if (tool == 'circle') {
          CMC.circle.control.erase();
          CMC.circle.control.open_ear();
        } else if (tool == 'polygon') {
          CMC.polygon.drawNew();
        }
      } else {
        self.set_active(this);
      }
    }, false);
  }
  this.set_active(tool_buttons[1]);
};
CM.init_ge = function(instance) {
  this.ge = instance;
  if (this.ge) {
    var geopts = this.ge.getOptions();
    geopts.setGridVisibility(true);
    geopts.setAtmosphereVisibility(false);
  }
};
CM.initDragTool = function(ctrl, tool) {
  var hooks = {
    moving: function(point) { ctrl.hook_moving(point); }, 
    dragging: function(bounds) { ctrl.hook_dragging(bounds); },
    dragend: function(bounds) { ctrl.hook_dragend(bounds); }
  };
  return new tool(this.map, hooks);
};
CM.state = function(stat) { $('status').update(stat); };
CM.recenter = function() {
  if ($('tool').value == 'rectangle') {
    this.map.setCenter(this.ctrls.rectangle.control.get_bounds().getCenter());
  } else if ($('tool').value == 'circle') {
    this.map.setCenter(this.ctrls.circle.control.get_bounds().latlng);
  }
};
CM.tracks_handler = function(request) {
  var cruise_tracks = request.responseJSON;
  var check = undefined;
  for (var expocode in cruise_tracks) {
    check = expocode;
    CM.results.add(expocode, cruise_tracks[expocode]);
  }
  if (check === undefined) {
    CM.state('No cruises found');
    this.results.clear();
  } else {
    CM.pane.activate();
    CM.pane.unshade();
  }
};
CM.remote_submit = function() { document.forms.tool_details.onsubmit(); };
CM.submit = function() {
  var type = $('tool').value;
  if (type == 'query') {
    this.ctrls.query.setActive();
    this.results.clear();
    this.map.setCenter(new google.maps.LatLng(0, 0), 1);
  } else if (type == 'rectangle') {
    this.ctrls.rectangle.sync();
  } else if (type == 'circle') {
    this.ctrls.circle.sync();
  } else if (type == 'polygon') {
    $('polygon').value = this.ctrls.polygon.toLineString();
    this.ctrls.polygon.sync();
  } else if (type == 'import') {
    this.ctrls.importpt.setActive();
  }
};
CM.get_circle = function(center, radius, polyColor) {
  if (radius <= 0) { return null; }
  var outer = this.map.fromLatLngToContainerPixel(CCHDO.Util.get_radius_coord(center, radius));
  center = this.map.fromLatLngToContainerPixel(center);
  return CCHDO.Util.get_circle_on_map_from_pts(this.map, center, outer, polyColor);
};
CM.init_ge = function(instance) {
  this.ge = instance;
  if (this.ge) {
    var geopts = this.ge.getOptions();
    geopts.setGridVisibility(true);
    geopts.setAtmosphereVisibility(false);
  }
};
CM.initDragTool = function(ctrl, tool) {
  var hooks = {
    moving: function(point) { ctrl.hook_moving(point); }, 
    dragging: function(bounds) { ctrl.hook_dragging(bounds); },
    dragend: function(bounds) { ctrl.hook_dragend(bounds); }
  };
  return new tool(this.map, hooks);
};
CM.state = function(stat) { $('status').update(stat); };
CM.recenter = function() {
  if ($('tool').value == 'rectangle') {
    this.map.setCenter(this.ctrls.rectangle.control.get_bounds().getCenter());
  } else if ($('tool').value == 'circle') {
    this.map.setCenter(this.ctrls.circle.control.get_bounds().latlng);
  }
};
CM.tracks_handler = function(request) {
  var cruise_tracks = request.responseJSON;
  var check = undefined;
  for (var expocode in cruise_tracks) {
    check = expocode;
    CM.results.add(expocode, cruise_tracks[expocode]);
  }
  if (check === undefined) {
    CM.state('No cruises found');
    this.results.clear();
  } else {
    CM.pane.activate();
    CM.pane.unshade();
  }
};
CM.remote_submit = function() { document.forms.tool_details.onsubmit(); };
CM.submit = function() {
  var type = $('tool').value;
  if (type == 'query') {
    this.ctrls.query.setActive();
    this.results.clear();
    this.map.setCenter(new google.maps.LatLng(0, 0), 1);
  } else if (type == 'rectangle') {
    this.ctrls.rectangle.sync();
  } else if (type == 'circle') {
    this.ctrls.circle.sync();
  } else if (type == 'polygon') {
    $('polygon').value = this.ctrls.polygon.toLineString();
    this.ctrls.polygon.sync();
  } else if (type == 'import') {
    this.ctrls.importpt.setActive();
  }
};
CM.get_circle = function(center, radius, polyColor) {
  if (radius <= 0) { return null; }
  var outer = this.map.fromLatLngToContainerPixel(CCHDO.Util.get_radius_coord(center, radius));
  center = this.map.fromLatLngToContainerPixel(center);
  return CCHDO.Util.get_circle_on_map_from_pts(this.map, center, outer, polyColor);
};
CM.load = function() {
  var G = google.maps;
  window.onunload=G.Unload; 
  if (G.BrowserIsCompatible()) { 
    var ctrls = CMC;
    var self = CM;
    var m = CM.map = new G.Map2($('map'), {mapTypes: [G_PHYSICAL_MAP, G_SATELLITE_MAP, G_SATELLITE_3D_MAP]});
    m.setCenter(new G.LatLng(0, 0), 3);// MUST be done right after map creation
    ctrls.rectangle.control = CM.initDragTool(ctrls.rectangle, DragRectangle);
    ctrls.circle.control = CM.initDragTool(ctrls.circle, DragCircle);
    CM.graticule = new Grat();
    m.addControl(new G.SmallZoomControl());
    m.addControl(new G.MenuMapTypeControl());
    m.enableContinuousZoom();
    m.enableScrollWheelZoom();
    m.setMapType(G_PHYSICAL_MAP);
    m.addOverlay(CM.graticule);
    CM.earth_ear = G.Event.addListener(m, 'maptypechanged', function() {
      if(!CM.ge && CM.map.getCurrentMapType().getName() == 'Earth') {
        CM.map.getEarthInstance(CM.init_ge);
      }
    });
  }

  var rctrl = ctrls.rectangle;
  rctrl.ne_lat_box = $('ne_lat'); 
  rctrl.ne_lng_box = $('ne_lng');
  rctrl.sw_lat_box = $('sw_lat'); 
  rctrl.sw_lng_box = $('sw_lng');
  var cctrl = ctrls.circle;
  cctrl.center_lat_box = $('circle_center_lat'); 
  cctrl.center_lng_box = $('circle_center_lng');
  cctrl.radius_box = $('circle_radius');
  var tctrl = ctrls.time;
  tctrl.min_time = $('min_time_display');
  tctrl.max_time = $('max_time_display');

  var l = G.Event.addDomListener;
  var sync_r = function() {rctrl.sync();};
  var sync_c = function() {cctrl.sync();};
  var sync_t = function() {tctrl.sanitize();};
  l(rctrl.ne_lat_box, 'keyup', sync_r);
  l(rctrl.ne_lng_box, 'keyup', sync_r);
  l(rctrl.sw_lat_box, 'keyup', sync_r);
  l(rctrl.sw_lng_box, 'keyup', sync_r);
  l(cctrl.center_lat_box, 'keyup', sync_c);
  l(cctrl.center_lng_box, 'keyup', sync_c);
  l(cctrl.radius_box, 'keyup', sync_c);
  l(tctrl.min_time, 'blur', sync_t);
  l(tctrl.max_time, 'blur', sync_t);
  l($('query_details'), 'click', function() {ctrls.query.setActive();});
  l($('rectangle_details'), 'click', function() {ctrls.rectangle.setActive();});
  l($('circle_details'), 'click', function() {ctrls.circle.setActive();});
  l($('polygon_details'), 'click', function() {ctrls.polygon.setActive();});
  l($('import_details'), 'click', function() {ctrls.importpt.setActive();});

  CM.tool_bar.init();
  CM.pane.deactivate();
  new Slider($('time_slider'), CM.MIN_TIME, CM.MAX_TIME, 200);

  ctrls.rectangle.sync();
};
CM.load_with_submit = function() {
  CM.load();
  CM.remote_submit();
};
google.setOnLoadCallback(CM.load);
