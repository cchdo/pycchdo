// coopted from html5-boilerplate
// make it safe to use console.log always
(function(b){function c(){}for(var d="assert,clear,count,debug,dir,dirxml,error,exception,firebug,group,groupCollapsed,groupEnd,info,log,memoryProfile,memoryProfileEnd,profile,profileEnd,table,time,timeEnd,timeStamp,trace,warn".split(","),a;a=d.pop();){b[a]=b[a]||c}})((function(){try
{console.log();return window.console;}catch(err){return window.console={};}})());

function getKey(key) {
  return key ? key.keyCode : event.keyCode;
}
Array.prototype.compare = function(testArr) {
  if (this.length != testArr.length) return false;
    for (var i = 0; i < testArr.length; i++) {
      if (this[i].compare) { 
        if (!this[i].compare(testArr[i])) return false;
      }
    if (this[i] !== testArr[i]) return false;
  }
  return true;
}
/* http://snipplr.com/view/799/get-url-variables/ */
function getUrlVars(){
  var hashes = window.location.href.slice(
    window.location.href.indexOf('?') + 1).split('&'),
      hash;
  var vars = {};
  for (var i = 0; i < hashes.length; i += 1) {
    hash = hashes[i].split('=');
    vars[hash[0]] = hash[1];
  }
  return vars;
}
function init() {
  var urlvars = getUrlVars();
  function handleData(data) {
    $('#status img').remove();
    if (!data) {
      $('#status').html('No data received.');
    } else if (data.error) {
      $('#status').html(data.error);
    } else {
      load(data.data);
    }
  }
  if (urlvars['autoopen']) {
    $.ajax({
      url: $('form').attr('action'),
      type: 'POST',
      data: {
        autoopen: decodeURIComponent(urlvars['autoopen']),
        csrf_param: $('meta[name=csrf-param]').attr('content'),
        csrf_token: $('meta[name=csrf-token]').attr('content')
      },
      dataType: 'json',
      beforeSubmit: function () {
        $('#status').html('Autoopening ' + urlvars['autoopen'] +
                          '<img src="/static/cchdomap/images/rotate.gif" />');
      },
      success: handleData,
      error: function (xhr, textStatus, errorThrown) {
        $('#status').html('An error occurred while loading the file.');
        console.log(xhr, textStatus, errorThrown);
      }
    });
  }
  try {
    $('form').ajaxForm({
      beforeSubmit: function () {
        $('#status').html('<img src="/static/cchdomap/images/rotate.gif" />');
      },
      success: handleData,
      error: function (xhr, textStatus, errorThrown) {
        $('#status').html('An error occurred while loading the file.');
        console.log(xhr, textStatus, errorThrown);
      },
      type: 'POST',
      dataType: 'json',
      iframe: true
    });
  } catch (e) {
    console.log('you fail', e);
  }
  $('#file').change(function () {
    $('form').submit();
  });
}
function load(data) {
  var currentRow = -1;
  var currentStation = -1;

  var GV = google.visualization;
  var data_table = new GV.DataTable(data, 0.6);

  (function initToolBox() {
    function openPropertyPropertyWindow() {
      var selectX = $('<select></select>')
        .append($('<option></option>'));
      var properties = [];
      for (var i=0;i<data_table.getNumberOfColumns();i++){ properties.push(data_table.getColumnLabel(i)); }
      properties = properties.sort();
      for (var i=0; i < properties.length; i++) {
        selectX.append($('<option>'+properties[i]+'</option>'));
      }
      var selectY = selectX.clone();
      var plotXYDiv = $('<div id="plot-xy"></div>').css('height', '200px');
      var plotwindow = $('<div></div>')
        .dialog({title: 'Property-Property', width: 500, minHeight: 500, show: 'slide'})
        .append('<h1>Please choose two parameters to plot:</h1>')
        .append($('<label>X</label>')).append(selectX)
        .append($('<label>Y</label>')).append(selectY).append($('<br />'))
        .append(plotXYDiv);
      var plotXYView = new GV.DataView(data_table);
      var plotXYChart = new CCHDO.vis.Plot(plotXYDiv[0]);
      var plotXYChartOpts = {height: '400px', width: '450px', invertY: true, gridColor: '#000',
        pointColor: new CCHDO.vis.Gradient({0: "#f00", 1000: "#fa0", 2000: "#fff", 3000: "#0f0", 6000: "#00f"})};
      $('select', plotwindow).change(function() {
        var propx = selectX.val();
        var propy = selectY.val();
        if (propx != '' && propy != '') {
          plotXYView.setColumns(getValuesFromKeys(label_to_colno, propx, propy));
          plotXYChart.draw(plotXYView, plotXYChartOpts);
        }
      });
    }

    function openTableWindow() {
      var width = $(window).width();
      var height = $(window).height();
      var tableDiv = $('<div></div>').css({'width': width, 'height': height});
      var tableWindow = $('<div></div>')
        .dialog({title: 'Table', width: width, height: height, show: 'slide'})
        .append(tableDiv);
      var tableView = new GV.DataView(data_table);
      var tableTable = new GV.Table(tableDiv[0]);
      var tableTableOpts = {width: '100%', height: '100%'};
      tableTable.draw(tableView, tableTableOpts);
    }

    var plotbutton = $('<input type="button" value="Property-Property" />')
      .css({'background-color': '#eee',
         'border': '1px solid #aaa',
         'cursor': 'pointer'})
      .click(openPropertyPropertyWindow);
    var tablebutton = $('<input type="button" value="Data Table" />')
      .css({'background-color': '#eee',
         'border': '1px solid #aaa',
         'cursor': 'pointer'})
      .click(openTableWindow);
    var toolbox = $('<div></div>')
      .append($('<h2>Plots</h2>'))
      .append($('<ul></ul>')
        .append($('<li></li>').append(plotbutton))
        .append($('<li></li>').append(tablebutton))
      )
      .dialog({
        beforeClose: function () { return false; },
        minWidth: 100,
        minHeight: 100,
        position: ['right', 'top']
      });
  })();

  function colnoToLabel(datatable) {
    var hash = {};
    for (var i=0; i<datatable.getNumberOfColumns(); i++) {
      hash[i] = datatable.getColumnLabel(i);
    }
    return hash;
  }

  var colno_to_label = colnoToLabel(data_table);

  function invert_one_to_one(hash) {
    var newhash = {};
    for (var i in hash) {
      newhash[hash[i]] = parseInt(i, 10);
    }
    return newhash;
  }

  function getValuesFromKeys(hash) {
    var vals = [];
    var keys = arguments;
    for (var i=1; i<keys.length; i++) {
      vals.push(hash[keys[i]]);
    }
    return vals;
  }

  function difference(seta, setb) {
    var diff = seta.slice();
    $.each(setb, function() {
      var index = $.inArray(Number(this), diff);
      if (index > -1) {
        diff.splice(index, 1);
      }
    });
    return diff;
  }

  var label_to_colno = invert_one_to_one(colno_to_label);

  var chartView = new GV.DataView(data_table);
  chartView.setColumns([label_to_colno['STNNBR'], label_to_colno['CTDPRS']]);

  var gradient = new CCHDO.vis.Gradient({0: "#f00", 1000: "#fa0", 2000: "#fff", 3000: "#0f0", 6000: "#00f"});

  var chart = new CCHDO.vis.Plot($('#chart')[0]);
  var chartOpts = {height: '400px', width: '1049px', invertY: true, depthGraph: true,
    pointColor: gradient};
  chart.draw(chartView, chartOpts);

  var legend = new CCHDO.vis.Legend($('#legend')[0]);
  var legendView = new GV.DataView(data_table);
  legendView.setColumns([label_to_colno['CTDPRS']]);
  var legendOpts = {
    numGradations: 15,
    gradient: gradient
  };
  legend.draw(legendView, legendOpts);

  var mapView = new GV.DataView(data_table);
  mapView.setColumns(getValuesFromKeys(label_to_colno, 'LATITUDE', 'LONGITUDE', 'SECT_ID', 'EXPOCODE', 'STNNBR', 'CASTNO', '_DATETIME', 'DEPTH'));
  function uniquifyMapView(view) {
    var dupRows = [];
    var currVals = [];
    for (var i=0; i<view.getNumberOfRows(); i++) {
      var next = [];
      for (var j=0; j<view.getNumberOfColumns(); j++) {
        next.push(view.getValue(i, j));
      }
      if (!currVals.compare(next)) {
        currVals = next;
      } else {
        dupRows.push(i);
      }
    }
    view.hideRows(dupRows);
  }
  uniquifyMapView(mapView);

  var map = new CCHDO.vis.Map($('#map')[0]);
  var mapOpts = {
    mapType: G_SATELLITE_MAP,
    mapOpts: {mapTypes: [G_PHYSICAL_MAP, G_SATELLITE_MAP, G_SATELLITE_3D_MAP]},
    setupMap: function(m) {
      m.setUIToDefault();
      m.enableContinuousZoom();
      m.enableScrollWheelZoom();
      m.addOverlay(new Grat());
    },
    polyline: {color: '#0f0', weight: 3, opacity: 0.9, opts: {clickable: false, geodesic: true, mouseOutTolerance: 1}},
    infoWindowHook: function(row, marker, data) {
      var str = '<ul style="margin-top: -0.5em; font-size: smaller; line-height: 1.2em;">';
      str += '<li><strong>Lat, Lng</strong> '+marker.getLatLng().toString()+'</li>';
      for (var i = this.geocoder ? 0 : 2; i<this.data.getNumberOfColumns(); i++) {
        str += '<li><strong>'+this.data.getColumnLabel(i)+'</strong> '+
               this.data.getValue(row, i)+'</li>';
      }
      str += '</ul>';
      return str;
    }
  };
  map.draw(mapView, mapOpts);

  var stationView = new GV.DataView(data_table);
  stationView.setColumns(getValuesFromKeys(label_to_colno,
    'SECT_ID', 'STNNBR', 'CASTNO', 'SAMPNO', 'BTLNBR', 'LATITUDE', 'LONGITUDE', '_DATETIME', 'DEPTH'));
  var stationOpts = {allowHtml: true};
  var station = new GV.Table($('#station')[0]);

  var observationView = new GV.DataView(data_table);
  var colnos = []; $.each(label_to_colno, function() { colnos.push(Number(this)); });
  observationView.setColumns(difference(colnos, getValuesFromKeys(label_to_colno,
    'SECT_ID', 'STNNBR', 'CASTNO', 'SAMPNO', 'BTLNBR', 'LATITUDE', 'LONGITUDE', '_DATETIME', 'DEPTH')));
  var observation = new GV.Table($('#observation')[0]);
  var observationOpts = {allowHtml: true, width: '100%'};

  function setRowVisible(row) {
    row = Math.max(0, row);
    row = Math.min(row, data_table.getNumberOfRows());
    if (currentRow == row) {return;}
    currentRow = row;
    var stnnbrcol = label_to_colno['STNNBR'];
    var stnnbr = data_table.getValue(row, stnnbrcol);

    var dataRows = data_table.getFilteredRows([{column: stnnbrcol, value: stnnbr}]);
    stationView.setRows([row]);
    station.draw(stationView, stationOpts);
    station.setSelection([{row: stationView.getViewRowIndex(row)}]);

    observationView.setRows([row]);
    observation.draw(observationView, observationOpts);
    observation.setSelection([{row: observationView.getViewRowIndex(row)}]);

    map.setSelection([{row: mapView.getViewRowIndex(dataRows[0])}]);

    chart.setSelection([{row: chartView.getViewRowIndex(row), col: label_to_colno['CTDPRS']}]);

    legend.setSelection([{row: data_table.getValue(row, label_to_colno['CTDPRS'])}]);

    currentStation = stnnbr;
  }

  function setStationVisible(stnnbr) {
    if (currentStation == stnnbr) {return;}
    var stnnbrcol = label_to_colno['STNNBR'];
    var dataRows = data_table.getFilteredRows([{column: stnnbrcol, value: stnnbr}]);
    setRowVisible(dataRows[0]);
  }

  GV.events.addListener(map, 'select', function() {
    var selection = this.getSelection();
    for (var i in selection) {
      var selectedrow = mapView.getTableRowIndex(selection[i].row);
      setRowVisible(selectedrow);
    }
  });

  GV.events.addListener(chart, 'select', function() {
    var selection = this.getSelection();
    for (var i in selection) {
      var selectedrow = chartView.getTableRowIndex(selection[i].row);
      setRowVisible(selectedrow);
    }
  });

  function findPrevStationStartRow(dt, r) {
    var stncol = label_to_colno['STNNBR'];
    var currStation = dt.getValue(r, stncol);
    for (var i=r; i>0; i--) {
      if (dt.getValue(i, stncol) != currStation) { return i; }
    }
    return 0;
  }

  function findNextStationStartRow(dt, r) {
    var stncol = label_to_colno['STNNBR'];
    var currStation = dt.getValue(r, stncol);
    for (var i=r; i<dt.getNumberOfRows(); i++) {
      if (dt.getValue(i, stncol) != currStation) { return i; }
    }
    return dt.getNumberOfRows()-1;
  }

  function findPrevCastStartRow(dt, r) {
    var stncol = label_to_colno['STNNBR'];
    if (r-1 < 0) { return r; }
    var currStation = dt.getValue(r, stncol);
    if (dt.getValue(r-1, stncol) != currStation) { return r; }
    return r-1;
  }

  function findNextCastStartRow(dt, r) {
    var stncol = label_to_colno['STNNBR'];
    if (r+1 == dt.getNumberOfRows()) { return r; }
    var currStation = dt.getValue(r, stncol);
    if (dt.getValue(r+1, stncol) != currStation) { return r; }
    return r+1;
  }

  $(document).keydown(function (e) {
    switch (getKey(e)) {
      case 37: setRowVisible(findPrevStationStartRow(data_table, currentRow)); return false;
      case 38: setRowVisible(findPrevCastStartRow(data_table, currentRow)); return false;
      case 39: setRowVisible(findNextStationStartRow(data_table, currentRow)); return false;
      case 40: setRowVisible(findNextCastStartRow(data_table, currentRow)); return false;
      default: console.log('unbound keypress', getKey(e)); break;
    }
  });

  setRowVisible(0);
}
google.setOnLoadCallback(init);

