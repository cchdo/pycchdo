function EMapOverlay(map) {
  this.setMap(map);
  map.set('emap_type', 'map');

  var self = this;
  google.maps.event.addListener(map, 'emap_type_changed', function () {
    if (map.get('emap_type') == 'map') {
      self.hide();
    } else {
      self.show();
    }
  });

  /* Set up graticules if defined */
  if (window.Graticule) {
  	this.set('overlay_graticules', new Graticule(map));
  	this.get('overlay_graticules').hide();
  }

  /* Hijack MVCObject's set command to notify when any MVCObject sets its "map" property. */
  google.maps.MVCObject.prototype.set = (function () {
    var setter = google.maps.MVCObject.prototype.set;
    return function (key, value) {
      var ret = setter.call(this, key, value);
      if (key == 'map') {
        google.maps.event.trigger(map, 'map_set', this, value);
      }
      return ret;
    }
  })();

  var map_earth = {};
  var earth_map = {};

  /* Duplicate map set events on earth */
  var default_maps_api_style = null;
  this._withEarth(function (ge) {
    var icon = ge.createIcon('');
    icon.setHref('http://maps.google.com/mapfiles/kml/paddle/red-circle.png');
    default_maps_api_style = ge.createStyle('default_maps_api_style');
    default_maps_api_style.getIconStyle().setIcon(icon);
    default_maps_api_style.getIconStyle().setScale(1.5);
  });

  google.maps.event.addListener(map, 'map_set', function (mvcobj, map) {
    if (mvcobj instanceof google.maps.Marker) {
      if (!mvcobj.get('clickable') && mvcobj.get('draggable') && !mvcobj.get('raiseOnDrag')) {
        // This seems to be an API marker for street view or cursor
        return;
      }
      self._withEarth(function (ge) {
        if (map) {
          var placemark = ge.createPlacemark('');
          var point = ge.createPoint('');
          var latlng = mvcobj.get('position');
          point.setLatLng(latlng.lat(), latlng.lng());
          placemark.setGeometry(point);
          if (mvcobj.getIcon()) {
            // TODO
          } else {
            placemark.setStyleSelector(default_maps_api_style);
          }
          ge.getFeatures().appendChild(placemark);
          map_earth[mvcobj] = placemark;
          earth_map[placemark] = mvcobj;
        } else {
          var earthobj = map_earth[mvcobj];
          ge.getFeatures().removeChild(earthobj);
          map_earth[mvcobj] = null;
          earth_map[earthobj] = null;
        }
      });
    } else {
      console.log(mvcobj, 'unhandled map set', map);
    }
  });
}
EMapOverlay.prototype = new google.maps.OverlayView();
EMapOverlay.prototype._withEarth = function (fn) {
  var self = this;
  // Retry every 50ms for ~10s.
  var retry = 200;
  (function () {
    var earth = self.get('earth_plugin');
    if (!earth && retry > 0) {
      retry -= 1;
      return setTimeout(arguments.callee, 50);
    }
    if (retry <= 0) {
      console.log('ERROR: No earth plugin object was found in a reasonable time frame.');
      return;
    }
    fn(earth);
  })();
};
EMapOverlay.prototype._initEarth = function (ge) {
	var self = this;
  this.set('earth_plugin', ge);
  ge.getWindow().setVisibility(true);
  ge.getOptions().setOverviewMapVisibility(true);
  ge.getOptions().setStatusBarVisibility(true);
  this.get('container_earth').childNodes[0].style.zIndex = 1001;
  this.get('container_earth').style.visibility = 'hidden';
  google.earth.addEventListener(ge.getWindow(), 'mouseout', function () {
    // TODO Mac OS X blur doesn't work
    ge.getWindow().blur();
  });

  /* Unify certain options for map and earth */
  google.maps.event.addListener(this, 'atmosphere_changed', function () {
    if (self.get('atmosphere')) {
      ge.getOptions().setAtmosphereVisibility(true);
    } else {
      ge.getOptions().setAtmosphereVisibility(false);
    }
  });
  google.maps.event.addListener(this, 'graticules_changed', function () {
    if (self.get('graticules')) {
      ge.getOptions().setGridVisibility(true);
      if (self.get('overlay_graticules')) {
        self.get('overlay_graticules').show();
      }
    } else {
      ge.getOptions().setGridVisibility(false);
      if (self.get('overlay_graticules')) {
        self.get('overlay_graticules').hide();
      }
    }
  });

  /* Duplicate earth mouse events on map */
  var win = ge.getWindow();
  var mousedown = false;
  function kmlme_to_me(kme) {
    return {latLng: new google.maps.LatLng(kme.getLatitude(), kme.getLongitude())};
  }
  google.earth.addEventListener(win, 'click', function (kmlmouseevent) {
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'click', kmlme_to_me(kmlmouseevent));
    }
  });
  google.earth.addEventListener(win, 'dblclick', function (kmlmouseevent) {
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'doubleclick', kmlme_to_me(kmlmouseevent));
    }
  });
  google.earth.addEventListener(win, 'mouseover', function (kmlmouseevent) {
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'mouseover', kmlme_to_me(kmlmouseevent));
    }
  });
  google.earth.addEventListener(win, 'mousedown', function (kmlmouseevent) {
    mousedown = true;
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'mousedown', kmlme_to_me(kmlmouseevent));
    }
  });
  google.earth.addEventListener(win, 'mouseup', function (kmlmouseevent) {
    mousedown = false;
    google.maps.event.trigger(map, 'mouseup', kmlme_to_me(kmlmouseevent));
  });
  google.earth.addEventListener(win, 'mouseout', function (kmlmouseevent) {
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'mouseout', kmlme_to_me(kmlmouseevent));
    }
  });
  google.earth.addEventListener(win, 'mousemove', function (kmlmouseevent) {
    if (kmlmouseevent.getDidHitGlobe()) {
      google.maps.event.trigger(map, 'mousemove', kmlme_to_me(kmlmouseevent));
      if (mousedown) {
        google.maps.event.trigger(map, 'drag');
      }
    }
  });

  //google.maps.event.addListener(map, 'click', function (e) {
  //  console.log('map clicked', e.latLng.lat(), e.latLng.lng());
  //});
  //google.maps.event.addListener(map, 'doubleclick', function (e) {
  //  console.log('map doubleclicked', e.latLng.lat(), e.latLng.lng());
  //});
  //google.maps.event.addListener(map, 'mouseover', function (e) {
  //  console.log('map mouseover', e.latLng.lat(), e.latLng.lng());
  //});
  //google.maps.event.addListener(map, 'mouseout', function (e) {
  //  console.log('map mouseout', e.latLng.lat(), e.latLng.lng());
  //});
  //google.maps.event.addListener(map, 'mousemove', function (e) {
  //  console.log('map mousemove', e.latLng.lat(), e.latLng.lng());
  //});
  //google.maps.event.addListener(map, 'drag', function () {
  //  console.log('map dragging');
  //});
  google.maps.event.trigger(this, 'initialized');
};
EMapOverlay.prototype.onAdd = function () {
  var self = this;
  var earthDiv = document.createElement('DIV');
  earthDiv.id = 'CONTAINER_EARTH';
  earthDiv.style.width = "100%";
  earthDiv.style.height = "100%";
  this.get('map').getDiv().childNodes[0].appendChild(earthDiv);
  this.set('container_earth', earthDiv);
  if (google.earth) {
    google.earth.createInstance(earthDiv, function (ge) {
      self._initEarth(ge);
    }, function (errorCode) {
      console.log('Unable to initialize Google Earth plugin:', errorCode);
    });
  } else {
    console.log('Why did you include this library?');
  }
};
EMapOverlay.prototype.onRemove = function () {
  this.get('map').getDiv().childNodes[0].removeChild(this.get('container_earth'));
};
EMapOverlay.prototype.draw = function () {
};
EMapOverlay.prototype.show = function () {
  /* Save and translate map state */
  var map_state = {};
  var ge = this.get('earth_plugin');
  var map = this.get('map');
  /* Prevent scrolling on map so plugin gets scrolling events */
  map_state.mapTypeId = map.getMapTypeId();
  map.setMapTypeId(google.maps.MapTypeId.SATELLITE);
  map_state.scrollwheel = map.get('scrollwheel');
  map.set('scrollwheel', false);

  if (map.get('zoomControl') != false) {
    var maps_earth_zoom_control_style = {};
    maps_earth_zoom_control_style[google.maps.ZoomControlStyle.LARGE] = ge.NAVIGATION_CONTROL_LARGE;
    maps_earth_zoom_control_style[google.maps.ZoomControlStyle.SMALL] = ge.NAVIGATION_CONTROL_SMALL;
    ge.getNavigationControl().setVisibility(ge.VISIBILITY_AUTO);
    var screenxy = ge.getNavigationControl().getScreenXY();
    screenxy.setXUnits(ge.UNITS_PIXELS);
    ge.getNavigationControl().setControlType(maps_earth_zoom_control_style[google.maps.ZoomControlStyle.LARGE]);
    if (map.get('zoomControl') == true) {
    	var opts = map.get('zoomControlOptions');
      if (opts) {
        ge.getNavigationControl().setControlType(maps_earth_zoom_control_style[opts.style]);
        // TODO also set position
      }
    }
  }

  var center = this.get('map').getCenter();
  var lookat = ge.createLookAt('');
  var range = Math.pow(2, 26 - this.get('map').getZoom());
  lookat.set(center.lat(), center.lng(), 0, ge.ALTITUDE_CLAMP_TO_GROUND, 0, 0, range);
  var flyToSpeed = ge.getOptions().getFlyToSpeed();
  ge.getOptions().setFlyToSpeed(ge.SPEED_TELEPORT);
  lookat.setRange(range);
  ge.getView().setAbstractView(lookat);
  ge.getOptions().setFlyToSpeed(flyToSpeed);
  this.get('container_earth').style.visibility = 'inherit';

  this.set('map_state', map_state);
};
EMapOverlay.prototype.hide = function () {
	var ge = this.get('earth_plugin');
  var lookat = ge.getView().copyAsLookAt(ge.ALTITUDE_CLAMP_TO_GROUND);
  var zoom = Math.round(26 - (Math.log(lookat.getRange()) / Math.log(2)));
  var range = Math.pow(2, 26 - zoom);

  var transition = false;
  var self = this;
  function afterTransition() {
    var center = new google.maps.LatLng(lookat.getLatitude(), lookat.getLongitude()); 

    var map = self.get('map');
    map.setZoom(zoom);
    map.panTo(center);

    var map_state = self.get('map_state');
    map.setMapTypeId(map_state.mapTypeId);
    map.set('scrollwheel', map_state.scrollwheel);
    if (transition) {
      google.earth.removeEventListener(ge.getView(), 'viewchangeend', arguments.callee);
    }
    self.get('container_earth').style.visibility = 'hidden';
  }
  if (lookat.getHeading() != 0 || lookat.getTilt() != 0 || range != lookat.getRange()) {
    lookat.setRange(range);
    lookat.setHeading(0);
    lookat.setTilt(0);
    transition = true;
    google.earth.addEventListener(ge.getView(), 'viewchangeend', afterTransition);
    var flyToSpeed = ge.getOptions().getFlyToSpeed();
    ge.getOptions().setFlyToSpeed(4.5);
    ge.getView().setAbstractView(lookat);
    ge.getOptions().setFlyToSpeed(flyToSpeed);
  } else {
    afterTransition();
  }
};

var EMapControl = (function () {
  function _(map, overlay, opts) {
    var self = this;

    if (!opts) {
      opts = {};
    }

    if (!opts.position) {
      opts.position = google.maps.ControlPosition.RIGHT_TOP;
    }

    var controlDiv = document.createElement('DIV');
    controlDiv.id = 'EMAPCONTROL';
    this.set('container', controlDiv);
    controlDiv.style.zIndex = 1002;
    map.controls[opts.position].push(controlDiv);

    var controlUI = document.createElement('DIV');
    controlUI.selectable = 'false';
    controlDiv.appendChild(controlUI);

    var controlText = document.createElement('DIV');
    controlText.style.background = "url('/images/cchdomap/emap_controls.png') repeat-y 0 100%";
    controlText.style.height = '30px';
    controlText.style.width = '40px';
    controlText.style.cursor = 'pointer';
    controlUI.appendChild(controlText);

    google.maps.event.addListener(map, 'emap_type_changed', function () {
    	if (map.get('emap_type') == 'map') {
        controlText.style.backgroundPosition = '0 100%';
      } else {
        self.get('container').style.zIndex = overlay.get('container_earth').childNodes[0].style.zIndex + 1;
        controlText.style.backgroundPosition = '0 0';
      }
    });
    google.maps.event.addDomListener(controlUI, 'click', function () {
      if (map.get('emap_type') == 'map') {
        map.set('emap_type', 'earth');
      } else {
        map.set('emap_type', 'map');
      }
    });
  }
  _.prototype = new google.maps.MVCObject();
  return _;
})();
