(function () {

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

Model.prototype.query = function (layer, query, callback, tracks_callback, error_callback) {
  var self = this;

  function handleData(data) {
    var id_t = data["id_t"];
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

    queryData = {shapes: [serializeShape(shape)]};
  }

  queryData.min_time = query.min_time || CM.MIN_TIME;
  queryData.max_time = query.max_time || CM.MAX_TIME;

  $.ajax({
    url:'/cchdomap/ids',
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
        $(self._layer._check).attr('checked', '');
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
      {label: 'id', type: 'number'},
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
    self.add(Number(id), info, tid != null);
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
  //.live('click', function () {
  //  var cid = self.getCruiseIdForTr(this);
  //  if (cid !== undefined && cid > -1) {
  //    self._model.click(null, self.getTrackForCid(cid));
  //  }
  //  return true;
  //});

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
  return this._dt.getFilteredRows([{column: 0, value: Number(cid)}]);
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
    id, info.name, info.programs, info.ship, info.country,
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
    for (var i = 1; i < this._dt.getNumberOfColumns(); i += 1) {
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

//      _.popout = function () {
//        if (CM._table_view_popped) { return; }
//        CM.pane.deactivate();
//        CM._table_view_popped = window.open('', '_table_view_popped',
//                                           'toolbar=0,location=0');
//        var doc = CM._table_view_popped.document;
//        doc.write('<div id="centering"><div id="_table_view"></div></div>');
//        /* Closing the document lets the window be written to later. I know, weird. */
//        doc.close();
//        doc.title = document.title + ' Results';
//        $('head', doc)
//          .append($('<base href="' +CM.host() + '" />', doc))
//          .append($('<link rel="icon" type="image/x-icon" href="favicon.ico" />', doc));
//        $('link').each(function () {
//          if (this.rel == 'stylesheet') {
//            $(['<link href="', this.href, '" rel="stylesheet" type="text/css" ',
//               'media="screen" />'].join(''), doc)
//              .appendTo($('head', doc));
//          }
//        });
//        $(['<div id="pop_button" class="clickable">Close window ',
//           '<img src="images/cchdomap/popin.png" ',
//           'title="Popin" alt="Popin" /></div>'].join(''))
//          .click(_.popin)
//          .prependTo($('#centering', doc));
//        if (CM._table_view_popped) {
//          _.setJdom($('#_table_view', doc));
//          _.redraw();
//        }
//      };
//      _.popin = function () {
//        CM._table_view_popped.close();
//        delete CM._table_view_popped;
//        _.setJdom($('#_table_view'));
//        CM.pane.activate();
//        CM.pane.unshade();
//        _.redraw();
//      };
//
//      $('#pop_button').addClass('clickable').click(_.popout);
//      (function popup_close_guard() {
//        if (CM._table_view_popped && CM._table_view_popped.closed) { CM.info.popin(); }
//        setTimeout(popup_close_guard, 1000);
//      })();
//      _.setJdom($('#_table_view'));


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
    CM.host + "/images/cchdomap/cruise_start_icon.png",
    new google.maps.Size(32, 16),
    null,
    new google.maps.Point(0, 16),
    new google.maps.Size(32, 16)),
  station: new google.maps.MarkerImage(
    CM.host + "/images/cchdomap/station_icon.png",
    new google.maps.Size(2, 2),
    null,
    new google.maps.Point(1, 1)),
};

Track.prototype._createStations = function () {
  var self = this;
  if (!this._station_leader) {
    this._station_leader = new google.maps.MVCObject();
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
  setTimeout(function () {
    //self._createStations();
    //self._station_leader.set('map', self.get('map'));
  }, 0);
};

Track.prototype.dimhl = function () {
  this.set('strokeColor', '#ffffaa');
  this.set('zIndex', CM.Z['dimhl']);
  var self = this;
  //setTimeout(function () {
  //  //self._createStations();
  //  //self._station_leader.set('map', self.get('map'));
  //}, 0);
};

Track.prototype.dim = function () {
  this.set('strokeColor', '#ffffaa');
  this.set('zIndex', CM.Z['dim']);
  if (this._station_leader) {
    this._station_leader.set('map', null);
  }
};

Track.prototype.dark = function (color) {
  this.set('strokeColor', color);
  this.set('zIndex', CM.Z['dark']);
  if (this._station_leader) {
    this._station_leader.set('map', null);
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
  // XXX
  //this._title.appendChild(document.createTextNode(name));
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
  $(this._check).change();
};

Layer.prototype.enable = function () {
  this._dom.className = this._dom.className.replace(' disabled', '');
  this._check.disabled = '';
  this.showAccessory();
  this.setColor(this._color);
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
  this._layerSection._layerView._model.dissociate(this);
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
    this.layerSectionNAV,
  ];
  for (var i = 0; i < sections.length; i += 1) {
    this.pushSection(sections[i]);
  }
}

DefaultLayerView.prototype = new LayerView();


function PermanentLayerSection(table) {
  LayerSection.call(this, '<img src="/images/cchdomap/layers_off.png" />');

  var tablelayer = new PermanentLayer('Table', false, function (on) {
    table.show(on);
  });
  table.setLayer(tablelayer);
  this.addLayer(tablelayer);

  var gratlayer = new PermanentLayer('Graticules', true, function (on) {
    CM.earth.set('graticules', on);
  });
  gratlayer._dom.firstChild.id = 'gridon';
  this.addLayer(gratlayer);

  if (CM.earth.get('earth_plugin')) {
    var atmolayer = new PermanentLayer('Atmosphere', true, function (on) {
      CM.earth.set('atmosphere', on);
    });
    $(atmolayer._dom).hide();
    this.addLayer(atmolayer);
    google.maps.event.addListener(CM.earth, 'showing_changed', function () {
      if (CM.earth.get('showing')) {
        $(atmolayer._dom).show('fast');
      } else {
        $(atmolayer._dom).hide('fast');
      }
    });
  }
}

PermanentLayerSection.prototype = new LayerSection();


function PermanentLayer(name, on, onoff_callback) {
  Layer.call(this);
  this._content.appendChild(document.createTextNode(name));
  var self = this;
  $(this._check).click(function (event) {
    event.stopPropagation();
  });
  $(this._dom).click(function () {
    $(self._check).click().change();
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
  textfield.type = 'text';
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
  LayerSection.call(this, '<img src="/images/cchdomap/gearth.gif" />');
  this.creator = new KMLLayerCreator();
  this.addLayer(this.creator);
  this._importer = new ImportKML();
  this._mapobj = null;

  $(this._dom).tipTipTip({defaultPosition: 'right', content: CM.TIPS['kml']});
}

KMLLayerSection.prototype = new LayerSection();


function KMLLayer(filename) {
  Layer.call(this);
  this._content.appendChild(document.createTextNode(filename));
  this._accessory.appendChild(document.createTextNode('x'));
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


function KMLLayerCreator() {
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
    data: rails_csrf(),
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

      self._layerSection._importer.importURL(response['url'], 
                                             function (imported) {
        console.log('imported: ', imported);
        layer._mapobj = imported.mapsLayer;
        layer.enable();
        layer.setOn(true);
      });
    },
    error: error
  });
}

KMLLayerCreator.prototype = new LayerCreator();


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
    data: rails_csrf(),
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
