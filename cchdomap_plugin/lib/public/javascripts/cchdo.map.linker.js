var GM = google.maps;

function Linked(linker) {
  this.linker = linker;
  this.objs = {};
  this.generateKey = (function () {
    var i = 0;
    return function (o) {
      var k = i;
      i += 1;
      return k;
    };
  })();
}
Linked.prototype = function () {};
Linked.prototype.add = function (o, key) {
  if (!key) {
    key = this.generateKey(o);
  }
  this.objs[key] = o;
  return key;
};
Linked.prototype.findKey = function (o) {
  for (var key in this.objs) {
    if (this.objs[key] === o) {
      return key;
    }
  }
  return null;
};
Linked.prototype.remove = function (key) {
  var o = this.objs[key];
  delete this.objs[key];
  return o;
};
Linked.prototype.toString = function () {
  return 'Linked';
};
Linked.prototype.light = function (key) {
  this.linker.light(key, this);
};
Linked.prototype.dim = function (key) {
  this.linker.dim(key, this);
};
Linked.prototype.dark = function (key) {
  this.linker.dark(key, this);
};
Linked.prototype._light = function (key) {
  console.log(this, 'lighten', key);
};
Linked.prototype._dim = function (key) {
  console.log(this, 'dim', key);
};
Linked.prototype._dark = function (key) {
  console.log(this, 'darken', key);
};

function Linker(mapLink, tableLink) {
  this.mapLink = mapLink;
  this.tableLink = tableLink;
  this.active = null;
  if (!this.mapLink.linker) {
    this.mapLink.linker = this;
  }
  if (!this.tableLink.linker) {
    this.tableLink.linker = this;
  }
  this.map_table = {};
  this.table_map = {};
}
Linker.prototype = function () {};
Linker.prototype.add = function (map, table) {
  var mapKey = this.mapLink.add(map);
  var tableKey = this.tableLink.add(table);
  this.map_table[mapKey] = tableKey;
  this.table_map[tableKey] = mapKey;
};
Linker.prototype.remove = function (map, table) {
  if (map) {
    var mapKey = this.mapLink.findKey(map);
    if (mapKey) {
      var tableKey = this.tableKey(key);
      this.mapLink.remove(mapKey);
      this.tableLink.remove(tableKey);
    }
  } else if (table) {
    var tableKey = this.tableLink.findKey(table);
    if (tableKey) {
      var mapKey = this.mapKey(tableKey);
      this.tableLink.remove(tableKey);
      this.mapLink.remove(mapKey);
    }
  }
};
Linker.prototype.mapKey = function (tableKey) {
  return this.table_map[tableKey];
};
Linker.prototype.tableKey = function (mapKey) {
  return this.map_table[mapKey];
};
Linker.prototype.getKeyLink = function (id) {
  return [id, this.tableLink];
};
Linker.prototype.getId = function (key, link) {
  if (link == this.mapLink) {
    return this.tableKey(key);
  }
  return key;
};
Linker.prototype.light = function (key, link) {
  var id = this.getId(key, link);
  if (this.active != id) {
    var kl = this.getKeyLink(this.active);
    if (kl) {
      this.active = id;
      this.dark(kl[0], kl[1]);
    }
  }
  this.active = id;
  if (link) {
    if (link === this.mapLink) {
      this.mapLink._light(key);
      this.tableLink._light(this.tableKey(key));
    } else if (link === this.tableLink) {
      this.mapLink._light(this.mapKey(key));
      this.tableLink._light(key);
    }
  }
};
Linker.prototype.dim = function (key, link) {
  if (link) {
    if (link === this.mapLink) {
      this.mapLink._dim(key);
      this.tableLink._dim(this.tableKey(key));
    } else if (link === this.tableLink) {
      this.mapLink._dim(this.mapKey(key));
      this.tableLink._dim(key);
    }
  }
};
Linker.prototype.dark = function (key, link) {
  var id = this.getId(key, link);
  if (id === null) {
    return;
  }
  if (this.active == id) {
    return this.light(key, link);
  }
  if (link) {
    if (link === this.mapLink) {
      this.mapLink._dark(key);
      this.tableLink._dark(this.tableKey(key));
    } else if (link === this.tableLink) {
      this.mapLink._dark(this.mapKey(key));
      this.tableLink._dark(key);
    }
  }
};

function LinkedTable(dom) {
  Linked.call();
  this.dom = dom;
}
LinkedTable.prototype = new Linked();
LinkedTable.prototype.constructor = LinkedTable;
LinkedTable.prototype.toString = function () {
  return 'LinkedTable';
};
Linked.prototype.findKey = function (o) {
  for (var key in this.objs) {
    if (this.objs[key][0] === o[0]) {
      return key;
    }
  }
  return null;
};
LinkedTable.prototype.add = function (o, key) {
  var key = Linked.prototype.add.call(this, o, key);
  var self = this;
  o.data('linked-table-origbg', o.css('background-color'));
  o.mouseenter(function () {
    self.dim(key);
  });
  o.mouseleave(function () {
    self.dark(key);
  });
  o.click(function () {
    self.light(key);
  });
  return key;
};
LinkedTable.prototype.remove = function (key) {
  this.objs[key].unbind().remove();
  Linked.prototype.remove.call(this, key);
};
LinkedTable.prototype._light = function (key) {
  var o = this.objs[key];
  o.find('td').css('background', '#ffaa00');
};
LinkedTable.prototype._dim = function (key) {
  var o = this.objs[key];
  o.find('td').css('background', '#ffff55');
};
LinkedTable.prototype._dark = function (key) {
  var o = this.objs[key];
  o.find('td').css('background', o.data('linked-table-origbg'));
};

function LinkedMap(map) {
  Linked.call();
  this.map = map;
}
LinkedMap.prototype = new Linked();
LinkedMap.prototype.constructor = LinkedMap;
LinkedMap.prototype.toString = function () {
  return 'LinkedMap';
};
LinkedMap.prototype.add = function (o, key) {
  var key = Linked.prototype.add.call(this, o, key);
  var self = this;
  GM.Event.addListener(o, 'mouseover', function () {
    self.dim(key);
  });
  GM.Event.addListener(o, 'mouseout', function () {
    self.dark(key);
  });
  GM.Event.addListener(o, 'click', function (coord) {
    self.light(key);
  });
  return key;
};
LinkedMap.prototype.remove = function (key) {
  this.map.removeOverlay(this.objs[key]);
  Linked.prototype.remove.call(this, key);
};
LinkedMap.prototype._light = function (key) {
  var o = this.objs[key];
  o.setStrokeStyle({color: '#ffaa00'});
  o.redraw(true);

  if (!this.map.getBounds().containsBounds(o.getBounds())) {
    this.map.panTo(o.getBounds().getCenter());
    var zoom = this.map.getBoundsZoomLevel(o.getBounds());
    if (zoom <= 2) { zoom = 2 };
    this.map.setZoom(zoom);
  }
};
LinkedMap.prototype._dim = function (key) {
  var o = this.objs[key];
  o.setStrokeStyle({color: '#ffff55'});
  o.redraw(true);

  if (!this.map.getBounds().containsBounds(o.getBounds())) {
    this.map.panTo(o.getBounds().getCenter());
  }
};
LinkedMap.prototype._dark = function (key) {
  var o = this.objs[key];
  o.setStrokeStyle({color: '#55ff00'});
  o.redraw(true);
};
