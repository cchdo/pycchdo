/*
Dependencies:
  JQuery >=1.4
  google.maps v3
*/
function trackToPolyline(geojson_ls) {
  var p = new google.maps.Polyline();
  var path = new google.maps.MVCArray();
  $.each(geojson_ls.coordinates, function (i, lnglat) {
    path.push(new google.maps.LatLng(lnglat[1], lnglat[0]));
  });
  p.setPath(path);
  return p;
}

$(function () {
  var GM = google.maps;

  var etopo_map_type = 'ETOPO';
  var map = new GM.Map($('#map')[0], {
    center: new GM.LatLng(0, -160),
    mapTypeId: GM.MapTypeId.SATELLITE,
    mapTypeControlOptions: {mapTypeIds: []},
    streetViewControl: false,
    overviewMapControl: true,
    zoom: 1
  });

  var cchdomt = new ETOPOMapType();
  map.mapTypes.set(etopo_map_type, cchdomt);
  map.setMapTypeId(etopo_map_type);

  new Graticule(map);

  var years_cruises = {};

  var select = (function () {
    var last;
    var last_year;
    return function (year) {
      var image = ['images/homemaps/seahunt', year, '.jpg'].join('');
      if (last_year && last_year != year) {
        last.removeClass('active');
        var cruises = years_cruises['y' + last_year];
        cruises.main.set('map', null);
      }
      $(this).addClass('active');
      last = $(this);
      last_year = year;

      var cruises = years_cruises['y' + year];
      cruises.main.set('map', map);
    };
  })();

  var years_list = $('#years-list');

  $.get('/cruises.json?pending_years=y', function (years) {
    $.each(years, function (i, year) {
      var url = ['/search/results?query=date_start:', year].join('');
      var url_json = ['/search/results.json?query=date_start:', year].join('');

      $.get(url_json, function (search) {
        var cruises = search['results'];
        var tracks = {main: new google.maps.MVCObject()};

        $.each(cruises, function (i, cruise) {
          if (!cruise.track) {
            return;
          }
          var polyline = trackToPolyline(cruise.track);
          polyline.setOptions({strokeColor: '#ffff00'});
          polyline.bindTo('map', tracks.main);
          google.maps.event.addListener(polyline, 'mouseover', function () {
            polyline.setOptions({strokeColor: '#ffaa00', zIndex: 1});
          });
          google.maps.event.addListener(polyline, 'mouseout', function () {
            polyline.setOptions({strokeColor: '#ffff00', zIndex: null});
          });
          google.maps.event.addListener(polyline, 'click', function () {
            window.location.href = cruise.obj_url;
          });
        });

        years_cruises['y' + year] = tracks;
        if (i == 0) {
          $('#searching').hide('fast').remove();
          li.mouseover();
        }
      }, 'json');
      
      var li = $(['<li><a href="', url, '">', year, '</a></li>'].join(''))
        .appendTo(years_list)
        .mouseover(function () {
          select.call(this, year);
        });
    });
  }, 'json');
});
