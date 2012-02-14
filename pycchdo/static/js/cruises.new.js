/* Basic strip-whitespace function. */
String.prototype.strip = function () {
  return this.replace((/^\s+/), '').replace((/\s+$/), '');
}
  
$(function init() {
  $(window).resize(function () {
    var h = $(this).height() - $('#cchdo_menu').outerHeight() - $('.boxed h1').outerHeight();
    $('.container').height(h);
  }).resize();
  
  var GM = google.maps;
  window.map = new GM.Map($('#map')[0], {
//    center: new GM.LatLng(32.8697, -117.2523),
    center: new GM.LatLng(0.0, 0.0),
    zoom: 2
  });
 
  var etopo_map_type = 'ETOPO';
  var cchdomt = new ETOPOMapType();
  map.mapTypes.set(etopo_map_type, cchdomt);
  map.setMapTypeId(etopo_map_type);

  map.set('mapTypeControlOptions', {
    mapTypeIds: [GM.MapTypeId.SATELLITE, etopo_map_type]
  });
 
  //var earth = new EarthMapType(map);
 
  //GM.event.addListener(earth, 'initialized', function (init) {
  //  if (init === false) {
  //    return;
  //  }
  //  // GoogleEarth overrides the mapTypeControlOptions so reset them here.
  //  map.set('mapTypeControlOptions', {
  //    mapTypeIds: map.get('mapTypeControlOptions').mapTypeIds + [earth.name]
  //  });
  //});
 
  var tooltip = new LatLngTooltip(map);
  new Graticule(map);
 
  var gbar = new window.jeremy.jGoogleBar(map, {});
  map.controls[GM.ControlPosition.BOTTOM_LEFT].push(gbar.container);
  
  // Set up note help
  var desc = $('#notes');
  if (!desc.val()) {
    var showing = false;
    var desc_help_trigger = desc.focus(function () {
      if (showing) {
        return;
      }
      showing = true;
      help = $('#notes-help');
      var close = $('<a href="javascript:void(0);">Dismiss</a>').css({'float': 'right'});
      close.click(function () {
        desc.unbind('click', desc_help_trigger);
        help.hide('fast').remove();
      });
      help.prepend(close);
      help.show('fast');
    });
  }
 
  var on_date_picker = false;
  $('#date_range_picker').hide().mousedown(function () {
    on_date_picker = true;
  }).mouseup(function () {
    on_date_picker = false;
  });
  var dates = $('.datepick.start,.datepick.end').datepicker({
    onSelect: function (selectedDate, inst) {
      var option = $(this).hasClass('start') ? 'minDate' : 'maxDate',
          date = $.datepicker.parseDate(inst.settings.dateFormat || $.datepicker._defaults.dateFormat, selectedDate, inst.settings);
          dates.not(this).datepicker('option', option, date);
      $('#attr_date_start').val($.map(dates, function (x) { return $.datepicker.formatDate('yy-mm-dd', $(x).datepicker('getDate')); }).join('/'));
    },
    defaultDate: "+3w",
    numberOfMonths: 1,
    showOtherMonths: true,
    selectOtherMonths: true
  });
  $('#attr_date_start').focus(function () {
    $('#date_range_picker').show('fast');
  }).blur(function () {
    if (on_date_picker) {
      $(this).change().focus();
      return false;
    }
    $('#date_range_picker').hide('fast');
  });
  
  function getDataURL(callback) {
    var self = this;
    try {
      var file = this.files[0];
      if (file) {
        var r = new FileReader();
        r.onload = function (e) {
          callback.call(self, e.target.result);
        };
        r.onerror = function (e) {
          callback.call(self, '');
        };
        r.readAsDataURL(file);
        return;
      }
    } catch (e) {
      callback.call(self, '');
    }
  }
  
  // Set up the Marker.
  function getContent() {
    var image = '';
    if ($(':file').val()) {
      var data = $(':file').data('dataurl');
      image = [
        '<p style="border: 1px solid black; border-left: none; ',
        'border-right: none;"><img src="',
        data ? data : '/static/cchdomap/images/cruise_start_icon.png',
        '" style="max-width: 100%;"></p>'].join('');
    }
    var infos = [];
    function addIfExists(label, val) {
      if (!val) {
        return;
      }
      infos.push(['<tr><td>', label, '</td><td>', val, '</td></tr>'].join(''));
    }
    addIfExists('Ports', $('#attr_ports').val());
    addIfExists('Programs', $('#attr_programs').val());
    addIfExists('Institutions', $('#attr_institutions').val());
    addIfExists('Contacts', $('#attr_contacts').val());
    addIfExists('Dates', $('#attr_date_start').val());
    addIfExists('Ship', $('#attr_ship').val());
    addIfExists('Country', $('#attr_country').val());
    return [
      '<div style="min-height: 130px">',
      '<h1>', $('#attr_expocode').val(), '</h1>',
      image,
      '<table>', infos.join(''), '</table>',
      '<p>', $('#attr_notes').val(), '</p>',
      '<p><a href="', $('#attr_link').val(), '">', $('#attr_link').val(), '</a></p>',
      '</div>'
    ].join('')
  }
  function infoWindowChanged() {
    INFO.setContent(getContent());
    INFO.open(MARKER.getMap(), MARKER);
  }
  
  var COORDINATES;
  var MARKER = new GM.Marker({position: new GM.LatLng(0, 0), map: map});
  var INFO = new GM.InfoWindow({content: getContent()});
  INFO.open(MARKER.getMap(), MARKER);
  GM.event.addListener(MARKER, 'click', infoWindowChanged);

  // TODO // Listen to changes in kml-image box and update the maps marker
  //$('#kml-image').change(function () {
  //  MARKER.setImage($(this).val());
  //});

  var polylineOptions = {
    strokeWeight: 3,
    strokeColor: '#aaffaa',
  };
  var drawingMgr = new GM.drawing.DrawingManager({
    drawingMode: GM.drawing.OverlayType.POLYLINE,
    drawingControl: true,
    drawingControlOptions: {
      drawingModes: [GM.drawing.OverlayType.POLYLINE]
    },
    polylineOptions: polylineOptions
  });
 
  function setupDrawState() {
    if (COORDINATES) {
      COORDINATES.setMap(null);
    }
    drawingMgr.setMap(map);
    GM.event.addListener(drawingMgr, 'polylinecomplete', function (pl) {
      COORDINATES = pl;
      COORDINATES.setEditable(true);
      setupPolyline(COORDINATES);
      drawingMgr.setMap(null);
    });
    return false;
  }

  $('#new_line').click(setupDrawState);

  function updateTrackFromPolyline(pl) {
    var buf = [];
    for (var vertex_index = 0, pt;
         vertex_index < pl.getPath().getLength();
         vertex_index++) {
      pt = pl.getPath().getAt(vertex_index);
      buf.push(pt.lng().toFixed(5) + ',' + pt.lat().toFixed(5));
    }
    $('#attr_track').val(buf.join('\n'));
  }

  function setupPolyline(pl) {
    function pathChanged() {
      if (MARKER) {
        MARKER.setPosition(pl.getPath().getAt(0));
      }
      updateTrackFromPolyline(pl);
    }
    GM.event.addListener(pl, 'path_changed', function () {
      var path = pl.getPath();
      GM.event.addListener(path, 'insert_at', pathChanged);
      GM.event.addListener(path, 'remove_at', pathChanged);
      GM.event.addListener(path, 'set_at', pathChanged);
      pathChanged();
    });
    GM.event.trigger(pl, 'path_changed');
  }
  
  function updatePolyline(latlngs) {
    if (latlngs.length < 2) {
      latlngs = [new GM.LatLng(0, 0), new GM.LatLng(0, 0)];
    }
    if (COORDINATES) {
      COORDINATES.setPath(latlngs);
      GM.event.trigger(COORDINATES, 'path_changed');
    } else {
      var opts = polylineOptions;
      opts.editable = true;
      opts.path = latlngs;
      opts.map = map;
      COORDINATES = new GM.Polyline(opts);
      setupPolyline(COORDINATES);
    }
  }
 
  $(':file').change(function () {
    // Try to preview image
    getDataURL.call(this, function (url) {
      if (url) {
        $(this).data('dataurl', url);
        infoWindowChanged();
      } else {
        $('#image-help').show('fast');
      }
    });
  });
  $('input[type=text], :file, textarea').change(infoWindowChanged);
  
  // Set up coords tooltip help
  var ctthelp = $('#track-help-tooltip').show();
  var close = $('<a href="javascript:void(0);">Dismiss</a>').css({'float': 'right'});
  close.click(function () {
    ctthelp.hide('fast').remove();
  });
  ctthelp.prepend(close);
 
  var isValidCoordinates = (function () {
    var lng_re = '[+-]?(?:1[0-7][0-9]|0?[1-9][0-9]|0{0,2}?[0-9])(\\.[0-9]*|\\.[0-9]+)?';
    var lat_re = '[+-]?(?:[1-8][0-9]|0?[0-9])(\\.[0-9]*|\\.[0-9]+)?';
    var full_re = ['^\\s*(', lng_re, ')(?:\\s*,\\s*|\\s+)(', lat_re, ')\\s*$'].join('');
    var lnglat_re = new RegExp(full_re);
 
    return function (coords) {
      for (var i = 0; i < coords.length; i += 1) {
        if (!lnglat_re.test(coords[i])) {
          return i;
        }
      }
      return true;
    }
  })();
 
  // Listen to changes in the coordinates box and try to update the Polyline
  $('#attr_track').change(function () {
    // Convert raw text into lines, skipping empty lines
    var coords = $('#attr_track').val().strip().split('\n');
    var newcoords = [];
    for (var i = 0; i < coords.length; i += 1) {
      var stripped = coords[i].strip();
      if (stripped) {
        newcoords.push(stripped);
      }
    }
    coords = newcoords;
 
    // check for un-coordinate-like stuff in the coordinates box.
    // if there is, turn it red and don't update.
    var errorline = isValidCoordinates(coords);
    if (isValidCoordinates(coords) !== true) {
      $('#attr_track').css('background', '#ffdddd');
      $('#track-help span').html(errorline + 1);
      $('#track-help').show('fast');
      return;
    }
  
    // clear the coordinates box background (no errors).
    $('#attr_track').css('background', '#ffffff');
    $('#track-help').hide('fast');
  
    // Change the polyline's points
    var bounds = new GM.LatLngBounds();
    var newcoords = [];
    for (var i = 0; i < coords.length; i += 1) {
      var x = coords[i];
      var pos = x.split(',');
      if (pos.length != 2) {
        pos = x.split(/\s+/);
      }
      var ll = new GM.LatLng(parseFloat(pos[1]), parseFloat(pos[0]))
      newcoords.push(ll);
      bounds = bounds.extend(ll);
    }
    updatePolyline(newcoords);
  
    // pan to show the new Polyline.
    map.panToBounds(bounds);
  }).change();
});
