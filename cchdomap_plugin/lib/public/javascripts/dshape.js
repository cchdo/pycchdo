Number.prototype.mod = function (n) {
  // http://javascript.about.com/od/problemsolving/a/modulobug.htm
  // Corrects Javascript modulo expectations for negative numbers.
  return ((this % n) + n) % n;
}

google.maps.MVCObject.prototype.setUnbind = function (key, value) {
  this.unbind(key);
  this.set(key, value);
};

google.maps.MVCArray.prototype.indexOf = function(elem) {
  var a = this.getArray();
  for (var i = 0; i < a.length; i += 1) {
    if (a[i] === elem) {
      return i;
    }
  }
  return -1;
};

google.maps.MVCArray.prototype.extend = function(a) {
  if (a instanceof google.maps.MVCArray) {
    var self = this;
    a.forEach(function (x) {
      self.push(x);
    });
  } else if (a instanceof Array) {
    for (var i = 0; i < a.length; i += 1) {
      this.push(a[i]);
    }
  }
};

google.maps.MVCArray.prototype.getAt = (function () {
  var fn = google.maps.MVCArray.prototype.getAt;
  return function (i) {
    if (i < 0) {
      i += this.getLength();
    }
    return fn.call(this, i);
  };
})();

google.maps.MVCArray.prototype.setAt = (function () {
  var fn = google.maps.MVCArray.prototype.setAt;
  return function (i, elem) {
    if (i < 0) {
      i += this.getLength();
    }
    return fn.call(this, i, elem);
  };
})();

google.maps.MVCArray.prototype.isClosed = function () {
  return this.getAt(0).equals(this.getAt(-1));
};

google.maps.Polygon.prototype.isClosed = function () {
  return this.getPath().isClosed();
};

function absPos(div) {
  var p = div;
  var top = 0;
  var left = 0;
  do {
    top += p.offsetTop;
    left += p.offsetLeft;
    p = p.offsetParent;
  } while (p);
  return {top: top, left: left};
}

/**
 * (Number) dist(a:google.maps.Point, b:google.maps.Point)
 */
function dist(a, b) {
  return Math.sqrt(Math.pow(b.x - a.x, 2) + Math.pow(b.y - a.y, 2));
}

/**
 * (google.maps.LatLng) midPoint(s:google.maps.LatLng, e:google.maps.LatLng)
 */
function midPoint(s, e) {
  var dtcross = e.lng() < 0 && s.lng() > 0;
  var newlng = null;
  if (dtcross) {
    newlng = -180 + s.lng() - (s.lng() - e.lng()) / 2;
  } else {
    newlng = s.lng() - (s.lng() - e.lng()) / 2;
  }
  return new google.maps.LatLng(
    s.lat() - (s.lat() - e.lat()) / 2,
    newlng);
}

/**
 * (google.maps.Polygon) makeCirclePolygon(center:google.maps.LatLng,
 *                                         radius:Number)
 * http://code.google.com/apis/earth/documentation/geometries.html#circles
 */
function makeCirclePolygon(center, radius) {
  var poly = new google.maps.Polygon();
  var ring = poly.getPath();
  var steps = 25;
  var pi2 = Math.PI * 2;
  for (var i = 0; i < steps; i++) {
    var lat = center.lat() + radius * Math.cos(i / steps * pi2);
    var lng = center.lng() + radius * Math.sin(i / steps * pi2);
    ring.push(new google.maps.LatLng(lat, lng));
  }
  ring.push(ring.getAt(0));
  return poly;
}

/**
 * ([singleClicklistener,
 *   doubleClicklistener]) listenSingleDoubleClick(obj:google.maps.object,
 *                                                 singleClick:callback,
 *                                                 doubleClick:callback,
 *                                                 timeout?:Number,
 *                                                 dom?:boolean)
 */
function listenSingleDoubleClick(obj, singleClick, doubleClick, timeout, dom) {
  if (!timeout && timeout !== 0) {
    timeout = 150;
  }
  var f = dom ? google.maps.event.addDomListener : google.maps.event.addListener;
  var doubleClicked = false;
  var singleClickEar = f(
    obj, 'click', function (mouseevent) {
    var self = this;
    setTimeout(function () {
      if (!doubleClicked) {
        return singleClick.call(self, mouseevent);
      }
    }, timeout);
    return false;
  });
  var doubleClickEar = f(
    obj, 'dblclick', function (mouseevent) {
    doubleClicked = true;
    return doubleClick.call(this, mouseevent);
  });
  return [singleClickEar, doubleClickEar];
}


// A Dynamic Shape that is drawable and editable.
//
// Properties:
//   editable
// Events:
//   drawing_polygon
//   drawing_presets
//
//   draw_updated
//   draw_canceled
//   draw_ended
function DShape(opts) {
  var self = this;

  google.maps.event.addListener(this, 'editable_changed', function () {
    if (self.get('editable')) {
      self.makeEditable_();
    } else {
      self.makeNoneditable_();
    }
  });

  var handles = {
    solids: new google.maps.MVCArray(),
    gases: new google.maps.MVCArray(),
  };
  this.set('handles', handles);

  google.maps.event.addListener(this, 'overlay_changed', function () {
    var overlay = self.get('overlay');
    if (!overlay) {
      return;
    }
    if (overlay.get('initialized')) {
      return;
    }

    overlay.bindTo('map', self);

    // TODO explode presets on double click
    google.maps.event.addListener(overlay, 'click', function () {
      self.set('editable', !self.get('editable'));
    });

    function drawChanged() {
      google.maps.event.trigger(self, 'draw_updated');
    }

    function makeSolid(ll) {
      var mkr = new google.maps.Marker({
        position: ll,
        draggable: true,
        icon: self.icons.setVertex
      });
      mkr.bindTo('map', self);
      mkr.set(
        'listener', google.maps.event.addListener(
                      mkr, 'dragend', function (mouseevent) {
        var i = handles.solids.indexOf(mkr);

        if (overlay instanceof google.maps.Polyline) {
          overlay.getPath().setAt(i, mouseevent.latLng);
        } else if (overlay instanceof google.maps.Polygon) {
          if (i == 0 && overlay.isClosed()) {
            overlay.getPath().setAt(-1, mouseevent.latLng);
          }
          overlay.getPath().setAt(i, mouseevent.latLng);
        } else if (overlay instanceof google.maps.Rectangle) {
          var i = handles.solids.indexOf(mkr);
          var oldBounds = overlay.getBounds();
          var newBounds = null;
          if (i == 0) {
            newBounds = new google.maps.LatLngBounds(mkr.getPosition(), oldBounds.getNorthEast());
          } else if (i == 1) {
            newBounds = new google.maps.LatLngBounds(oldBounds.getSouthWest(), mkr.getPosition());
          } else if (i == 2) {
            var oldC = oldBounds.getCenter();
            var newC = mkr.getPosition();
            var dx = oldC.lng() - newC.lng();
            var dy = oldC.lat() - newC.lat();
            var sw = new google.maps.LatLng(
              oldBounds.getSouthWest().lat() - dy,
              oldBounds.getSouthWest().lng() - dx);
            var ne = new google.maps.LatLng(
              oldBounds.getNorthEast().lat() - dy,
              oldBounds.getNorthEast().lng() - dx);
            newBounds = new google.maps.LatLngBounds(sw, ne);
          }
          overlay.setBounds(newBounds);
        } else if (overlay instanceof google.maps.Circle) {
          var i = handles.solids.indexOf(mkr);
          if (i == 0) {
            overlay.setCenter(mkr.getPosition());
          } else {
            if (google.maps.geometry && google.maps.geometry.spherical) {
              overlay.setRadius(
                google.maps.geometry.spherical.computeDistanceBetween(
                  overlay.getCenter(), mkr.getPosition()));
            } else {
            }
          }
        }
        google.maps.event.trigger(overlay, 'shape_changed');
      }));
      return mkr;
    }

    function makeGas(ll) {
      var mkr = new google.maps.Marker({
        position: ll,
        draggable: true,
        icon: self.icons.gasVertex
      });
      mkr.bindTo('map', self);
      mkr.set(
        'listener', google.maps.event.addListener(
                      mkr, 'dragend', function (mouseevent) {
        var i = handles.gases.indexOf(mkr);

        var trigger = '';
        if (overlay instanceof google.maps.Polyline) {
          overlay.getPath().insertAt(i + 1, mouseevent.latLng);
        } else if (overlay instanceof google.maps.Polygon) {
          if (i == overlay.getPath().getLength() - 1 && overlay.isClosed()) {
            overlay.getPath().insertAt(i, mouseevent.latLng);
          } else {
            overlay.getPath().insertAt(i + 1, mouseevent.latLng);
          }
        }
        google.maps.event.trigger(overlay, 'shape_changed');
      }));
      return mkr;
    }

    function clearMapsForMVCArrayAfter(arr, n) {
      arr.forEach(function (mkr, i) {
        if (i < n) {
          return true;
        }
        mkr.unbind('map');
        mkr.setMap(null);
      });
    }

    google.maps.event.addListener(overlay, 'shape_changed', function () {
      if (overlay instanceof google.maps.Polyline) {
        google.maps.event.trigger(overlay, 'path_changed');
      } else if (overlay instanceof google.maps.Polygon) {
        google.maps.event.trigger(overlay, 'paths_changed');
      } else if (overlay instanceof google.maps.Circle) {
        google.maps.event.trigger(overlay, 'center_changed');
        google.maps.event.trigger(overlay, 'radius_changed');
      } else if (overlay instanceof google.maps.Rectangle) {
        google.maps.event.trigger(overlay, 'bounds_changed');
      } else {
        // TODO
      }
      google.maps.event.trigger(self, 'shape_changed');
    });

    google.maps.event.addListener(overlay, 'shape_changed', function () {
      if (!self.get('editable')) {
        return;
      }
      if (overlay instanceof google.maps.Polyline) {
        // The polyline has n solid and n - 1 gas.
        var lastLL = null;
        overlay.getPath().forEach(function (ll, i) {
          var solid = handles.solids.getAt(i);
          if (!solid) {
            solid = makeSolid(ll);
            handles.solids.setAt(i, solid);
          } else {
            solid.setPosition(ll);
            if (!solid.getMap()) {
              solid.bindTo('map', self);
            }
          }
          if (lastLL) {
            var gas = handles.gases.getAt(i - 1);
            var pt = midPoint(lastLL, ll);
            if (!gas) {
              gas = makeGas(pt);
              handles.gases.setAt(i - 1, gas);
            } else {
              gas.setPosition(pt);
              if (!gas.getMap()) {
                gas.bindTo('map', self);
              }
            }
          }
          lastLL = ll;
        });
        clearMapsForMVCArrayAfter(handles.solids, overlay.getPath().getLength());
        clearMapsForMVCArrayAfter(handles.gases, overlay.getPath().getLength() - 1);
        drawChanged();
      } else if (overlay instanceof google.maps.Polygon) {
        // The polygon has n solid and n gas.
        var path = overlay.getPath();
        var lastLL = null;
        var closed = path.isClosed();
        overlay.getPath().forEach(function (ll, i) {
          if (closed && path.getLength() - 1 == i) {
            return false;
          }
          var solid = handles.solids.getAt(i);
          if (!solid) {
            solid = makeSolid(ll);
            handles.solids.setAt(i, solid);
          } else {
            solid.setPosition(ll);
            if (!solid.getMap()) {
              solid.bindTo('map', self);
            }
          }
          if (lastLL) {
            var gas = handles.gases.getAt(i - 1);
            var pt = midPoint(lastLL, ll);
            if (!gas) {
              gas = makeGas(pt);
              handles.gases.setAt(i - 1, gas);
            } else {
              gas.setPosition(pt);
              if (!gas.getMap()) {
                gas.bindTo('map', self);
              }
            }
          }
          lastLL = ll;
        });
        var i = overlay.getPath().getLength() - 1;
        if (closed) {
          i -= 1;
        }
        var gas = handles.gases.getAt(i);
        var pt = midPoint(lastLL, overlay.getPath().getAt(0));
        if (!gas) {
          gas = makeGas(pt);
          handles.gases.setAt(i, gas);
        } else {
          gas.setPosition(pt);
          if (!gas.getMap()) {
            gas.bindTo('map', self);
          }
        }
        clearMapsForMVCArrayAfter(handles.solids, overlay.getPath().getLength());
        if (overlay.isClosed()) {
          clearMapsForMVCArrayAfter(handles.gases, overlay.getPath().getLength() - 1);
        } else {
          clearMapsForMVCArrayAfter(handles.gases, overlay.getPath().getLength());
        }
        drawChanged();
      } else if (overlay instanceof google.maps.Circle) {
        // Let's use two handles center and radius
        var c = handles.solids.getAt(0);
        var cll = overlay.getCenter();
        if (!c) {
          c = makeSolid(cll);
          handles.solids.setAt(0, c);
        } else {
          c.setPosition(cll);
          if (!c.getMap()) {
            c.bindTo('map', self);
          }
        }
        // XXX The google.maps circle distorts according to the projection but incorrectly.
        var r = handles.solids.getAt(1);
        var poly = makeCirclePolygon(overlay.getCenter(), overlay.getRadius() / Math.pow(10, 5));
        var pts = poly.getPath();
        pts.forEach(function (x, i) {
          if (i == pts.getLength() - 1) {
            return;
          }
          var p = handles.solids.getAt(i + 1);
          if (!p) {
            p = makeSolid(x);
            handles.solids.setAt(i + 1, p);
          } else {
            p.setPosition(x);
            if (!p.getMap()) {
              p.bindTo('map', self);
            }
          }
        });

        clearMapsForMVCArrayAfter(handles.solids, pts.getLength());
      } else if (overlay instanceof google.maps.Rectangle) {
        var sw = handles.solids.getAt(0);
        var swll = overlay.getBounds().getSouthWest();
        var nell = overlay.getBounds().getNorthEast();
        if (!sw) {
          sw = makeSolid(swll);
          handles.solids.setAt(0, sw);
        } else {
          sw.setPosition(swll);
          if (!sw.getMap()) {
            sw.bindTo('map', self);
          }
        }
        var ne = handles.solids.getAt(1);
        if (!ne) {
          ne = makeSolid(nell);
          handles.solids.setAt(1, ne);
        } else {
          ne.setPosition(nell);
          if (!ne.getMap()) {
            ne.bindTo('map', self);
          }
        }
        var c = handles.solids.getAt(2);
        var cll = overlay.getBounds().getCenter();
        if (!c) {
          c = makeSolid(cll);
          handles.solids.setAt(2, c);
        } else {
          c.setPosition(cll);
          if (!c.getMap()) {
            c.bindTo('map', self);
          }
        }
        clearMapsForMVCArrayAfter(handles.solids, 3);
      } else {
        // TODO
      }
    });
    overlay.set('initialized', true);
  });

  this.setValues(opts);
}

DShape.prototype = new google.maps.OverlayView();

DShape.prototype.sameVertexThreshold = 10;

DShape.prototype.icons = {
  setVertex: new google.maps.MarkerImage('/images/cchdomap/dshape-solid.png',
    new google.maps.Size(11, 11), new google.maps.Point(0, 0),
    new google.maps.Point(5, 5)),
  gasVertex: new google.maps.MarkerImage('/images/cchdomap/dshape-gas.png',
    new google.maps.Size(11, 11), new google.maps.Point(0, 0),
    new google.maps.Point(5, 5))
};

DShape.prototype.onAdd = function () {
};

DShape.prototype.draw = function () {
};

DShape.prototype.onRemove = function () {
  this.get('handles').solids.clear();
  this.get('handles').gases.clear();
};

/**
 * (google.maps.Point) eventPt(event)
 */
DShape.prototype.eventPt = function (event) {
  var x = event.x;
  var y = event.y;
  if (isNaN(x)) {
    x = event.clientX;
  }
  if (isNaN(y)) {
    y = event.clientY;
  }
  var abspos = absPos(this.getMap().getDiv());
  x -= abspos.left;
  y -= abspos.top
  return new google.maps.Point(Number(x), Number(y));
};

/**
 * (google.maps.LatLng) eventLatLng(event)
 */
DShape.prototype.eventLatLng = function (event) {
  return this.getProjection().fromContainerPixelToLatLng(this.eventPt(event));
};

DShape.prototype.setShape = function (path, type) {
  if (type == 'line') {
    var line = new google.maps.Polyline({path: path});
    line.bindTo('map', this);
    line.bindTo('strokeColor', this);
    line.bindTo('strokeWeight', this);
    this.set('overlay', line);
  } else {
    return false;
  }
};

DShape.prototype.setPath = function (path) {
  this.get('overlay').setPath(path);
  google.maps.event.trigger(this.get('overlay'), 'path_changed');
};

DShape.prototype.getPath = function () {
  return this.get('overlay').getPath();
};

DShape.prototype.samePoint = function (a, b, pxthresh) {
  if (!pxthresh) {
    pxthresh = this.sameVertexThreshold;
  }
  return dist(a, b) < pxthresh;
};
DShape.prototype.drawPolygon = function (ll, firstReset, lastReset) {
  google.maps.event.trigger(this, 'drawing_polygon');
  var self = this;

  var listeners = new google.maps.MVCArray();

  var placingFirst = true;
  var ll0 = ll;
  var pt0 = this.getProjection().fromLatLngToContainerPixel(ll0);

  var interim_poly;
  if (!self.get('line')) {
    interim_poly = new google.maps.Polygon({
      strokeWeight: 0,
      strokeOpacity: 0
    });
    interim_poly.bindTo('fillColor', self);
    interim_poly.bindTo('fillOpacity', self);
  } else {
    interim_poly = new google.maps.Polyline();
    interim_poly.bindTo('strokeColor', self);
    interim_poly.bindTo('strokeWeight', self);
  }
  self.set('overlay', interim_poly);
  interim_poly.getPath().push(ll0);
  interim_poly.bindTo('map', this);

  var interim_line = new google.maps.Polyline({
    cursor: 'crosshair',
  });
  interim_line.bindTo('strokeColor', self);
  interim_line.bindTo('strokeWeight', self);
  interim_line.getPath().push(ll0);
  interim_line.bindTo('map', this);

  var startVertex = new google.maps.Marker({icon: this.icons.setVertex, position: ll0});
  startVertex.bindTo('map', this);

  var indicator = new google.maps.Polyline({path: [ll0, ll0]});
  self.set('indicatorStrokeColor', interim_line.get('strokeColor'));
  indicator.bindTo('strokeColor', self, 'indicatorStrokeColor');
  indicator.bindTo('strokeWeight', self);
  indicator.bindTo('map', this);

  function indicate(event) {
    var pt = self.eventLatLng(event);
    indicator.getPath().setAt(1, pt);
  }
  listeners.push(google.maps.event.addDomListener(self.getMap().getDiv(), 'mousemove', indicate));

  function closePoly() {
    startVertex.unbind('map');
    startVertex.setMap(null);
    if (!self.get('line')) {
      interim_poly.getPath().push(ll0);
    }
    self.set('overlay', interim_poly);
    interim_poly.set('strokeOpacity', 1);
    interim_poly.bindTo('strokeColor', self);
    interim_poly.bindTo('strokeWeight', self);
    interim_poly.bindTo('fillColor', self);
    interim_poly.bindTo('fillOpacity', self);
    interim_line.setUnbind('map', null)
    indicator.setUnbind('map', null);
    listeners.forEach(function (l) {
      google.maps.event.removeListener(l);
    });

    firstReset();
    lastReset();
    return false;
  }

  function finish() {
    var rval = closePoly();
    google.maps.event.trigger(self, 'draw_ended');
    return rval;
  }

  function newVertex(event) {
    if (placingFirst) {
      placingFirst = false;
      return;
    }
    var pt = self.eventLatLng(event);

    var ptpt = self.getProjection().fromLatLngToContainerPixel(pt);
    if (self.samePoint(ptpt, pt0)) {
      finish();
      return;
    }

    indicator.setPath([pt, pt])
    interim_poly.getPath().push(pt);
    interim_line.getPath().push(pt);

    google.maps.event.trigger(self, 'draw_updated');
  }

  function keyPress(event) {
    if (event.keyCode == 13) {
      finish();
    }
  }

  function lastVertex(mouseevent) {
    try {
      event.preventDefault();
      event.stopPropagation();
    } catch (e) {
    }
    newVertex(mouseevent);
    return finish();
  }

  listeners.push(google.maps.event.addListener(startVertex, 'click', finish));
  listeners.extend(listenSingleDoubleClick(self.getMap().getDiv(), newVertex, lastVertex, null, true));
  listeners.push(google.maps.event.addDomListener(document, 'keydown', keyPress));

  listeners.push(google.maps.event.addListenerOnce(self, 'draw_canceled', function () {
    closePoly();
    var overlay = self.get('overlay');
    if (overlay) {
      overlay.unbind('map');
      overlay.setMap(null);
    }
    self.set('overlay', null);
  }));
};
DShape.prototype.drawPresets = function (start, end, firstReset, lastReset) {
  google.maps.event.trigger(this, 'drawing_presets');
  var self = this;
  firstReset();

  function bindPreset(p) {
    p.bindTo('map', self);
    p.bindTo('strokeColor', self);
    p.bindTo('strokeWeight', self);
    p.bindTo('fillColor', self);
    p.bindTo('fillOpacity', self);
  }

  var circle = new google.maps.Circle({center: start, radius: 0});
  var rect = new google.maps.Rectangle({bounds: new google.maps.LatLngBounds(start, start)});
  bindPreset(circle);
  bindPreset(rect);
  
  google.maps.event.addListenerOnce(circle, 'zindex_changed', function () {
    rect.set('zIndex', circle.get('zIndex') + 1);
  });
  var baseZIndex = 1000;
  circle.set('zIndex', baseZIndex);

  function updatePresets(event) {
    end = self.eventLatLng(event);

    if (google.maps.geometry && google.maps.geometry.spherical) {
      var radius = google.maps.geometry.spherical.computeDistanceBetween(start, end);
      circle.setRadius(radius);
    }

    if (start.lat() < end.lat()) {
      if (start.lng () < end.lng()) {
        sw = start;
        ne = end;
      } else {
        sw = new google.maps.LatLng(start.lat(), end.lng());
        ne = new google.maps.LatLng(end.lat(), start.lng());
      }
    } else {
      if (start.lng () < end.lng()) {
        sw = new google.maps.LatLng(end.lat(), start.lng());
        ne = new google.maps.LatLng(start.lat(), end.lng());
      } else {
        sw = end;
        ne = start;
      }
    }
    rect.setBounds(new google.maps.LatLngBounds(sw, ne));
  }

  var moveEar = google.maps.event.addDomListener(
    this.getMap().getDiv(), 'mousemove', updatePresets);

  var upEar = google.maps.event.addDomListenerOnce(
    this.getMap().getDiv(), 'mouseup', function (event) {
    updatePresets(event);

    google.maps.event.removeListener(moveEar);
    moveEar = null;
    upEar = null;

    function highlighter(shape) {
      return function () {
        shape.unbind('strokeColor');
        shape.set('strokeColor', '#aaffaa');
        shape.unbind('fillColor');
        shape.set('fillColor', '#aaffaa');
      };
    }

    function lowlighter(shape) {
      return function () {
        shape.bindTo('strokeColor', self);
        shape.bindTo('fillColor', self);
      };
    }

    setTimeout(function () {
      var lighters = new google.maps.MVCArray();
      lighters.push(google.maps.event.addListener(circle, 'mousemove', highlighter(circle)));
      lighters.push(google.maps.event.addListener(circle, 'mouseout', lowlighter(circle)));
      lighters.push(google.maps.event.addListener(rect, 'mousemove', highlighter(rect)));
      lighters.push(google.maps.event.addListener(rect, 'mouseout', lowlighter(rect)));

      function keep(k, trash) {
        trash.unbind('map');
        trash.setMap(null);

        google.maps.event.trigger(k, 'mouseout');
        lighters.forEach(function (x) {
          google.maps.event.removeListener(x);
        });

        k.unbind('map');
        k.setMap(null);
        self.set('overlay', k);

        google.maps.event.removeListener(keep0);
        google.maps.event.removeListener(keep1);
        google.maps.event.removeListener(cancelEar);
        lastReset();
        google.maps.event.trigger(self, 'draw_ended');
      }

      var keep0 = google.maps.event.addListenerOnce(circle, 'click', function () {
        keep(circle, rect);
      });
      var keep1 = google.maps.event.addListenerOnce(rect, 'click', function () {
        keep(rect, circle);
      });
      google.maps.event.trigger(self, 'draw_updated');

      if (circle.getRadius() == 0) {
        google.maps.event.trigger(rect, 'click');
      }

    }, 100);
  });

  var cancelEar = google.maps.event.addListenerOnce(self, 'draw_canceled', function () {
    circle.unbind('map');
    circle.setMap(null);
    rect.unbind('map');
    rect.setMap(null);

    if (moveEar) {
      google.maps.event.removeListener(moveEar);
    }
    if (upEar) {
      google.maps.event.removeListener(upEar);
    }
  });
};
DShape.prototype.start = function () {
  var self = this;
  if (self.get('overlay')) { 
    return false;
  }

  var beforeDraggable = this.getMap().get('draggable');
  this.getMap().set('draggable', false);

  var beforeCursor = this.getMap().getDiv().style.cursor;
  this.getMap().getDiv().style.cursor = 'crosshair';

  var beforeDoubleClickZoom = this.getMap().get('disableDoubleClickZoom');
  this.getMap().set('disableDoubleClickZoom', true);

  function resetMapAfterFirstAction() {
    self.getMap().set('draggable', beforeDraggable);
    self.getMap().set('disableDoubleClickZoom', beforeDoubleClickZoom);
  }

  function resetMapAfterLastAction() {
    self.getMap().getDiv().style.cursor = beforeCursor;
  }

  var div = this.getMap().getDiv();
  var dragStartEar = google.maps.event.addDomListenerOnce(
    div, 'mousedown', function (event) {
    var drag_start = self.eventPt(event);
    var dragMoveEar = google.maps.event.addDomListener(
      div, 'mousemove', function (event) {
      var drag_end = self.eventPt(event);
      var end = self.getProjection().fromContainerPixelToLatLng(drag_end);
      if (!self.samePoint(drag_start, drag_end)) {
        google.maps.event.removeListener(dragMoveEar);
        google.maps.event.removeListener(upEar);
        var start = self.getProjection().fromContainerPixelToLatLng(drag_start);
        self.drawPresets(start, end, resetMapAfterFirstAction, resetMapAfterLastAction);
      }
    });
    var upEar = google.maps.event.addDomListenerOnce(
      div, 'mouseup', function (event) {
      google.maps.event.removeListener(dragMoveEar);
      var drag_end = self.eventPt(event);
      var end = self.getProjection().fromContainerPixelToLatLng(drag_end);

      if (self.samePoint(drag_start, drag_end)) {
        self.drawPolygon(end, resetMapAfterFirstAction, resetMapAfterLastAction);
      }
    });
  });

  google.maps.event.addListenerOnce(self, 'draw_canceled', function () {
    google.maps.event.removeListener(dragStartEar);
    resetMapAfterFirstAction();
    resetMapAfterLastAction();
  });

  var keyEar = google.maps.event.addDomListenerOnce(document, 'keydown', function (event) {
    if (event.keyCode == 27) {
      google.maps.event.trigger(self, 'draw_canceled');
    }
  });
};
DShape.prototype.makeEditable_ = function () {
  google.maps.event.trigger(this.get('overlay'), 'shape_changed');
};
DShape.prototype.makeNoneditable_ = function () {
  function rmHandle(mkr) {
    mkr.unbind('map');
    mkr.setMap(null);
  }
  this.get('handles').solids.forEach(rmHandle);
  this.get('handles').gases.forEach(rmHandle);
};
