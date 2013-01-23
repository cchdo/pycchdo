$(function () {
  function dateToYYYYmmdd(d) {
    var month = d.getMonth() + 1;
    if (month < 10) {
      month = '0' + month;
    }
    var day = d.getDay();
    if (day < 10) {
      day = '0' + day;
    }
    return d.getFullYear() + '-' + month + '-' + day;
  }
  var timeglider = $('<div id="timeglider"></div>');
  var timeline = $('<div id="timeline"><h3><a href="#">Timeline</a></h3></div>');
  timeline.prependTo($('.box_content'));
  timeline.accordion({
    collapsible: true
  });
  timeglider.appendTo(timeline);
  timeglider.height(200);
  timeline.accordion({active: false});

  var datatable = $('<table id="datatable"/>');
  datatable.hide().appendTo($('body'));
  datatable.addClass('timeline-table');
  datatable.attr('title', 'Cruises');
  datatable.attr('description', 'Cruises by time');
  datatable.attr('initial_zoom', '34');

  datatable.append($(
    '<tr>' + 
    '<th class="tg-startdate">start date</th>' +
    '<th class="tg-enddate">end date</th>' +
    '<th class="tg-title">title</th>' +
    '<th class="tg-description">description</th>' +
    '<th class="tg-icon">icon</th>' +
    '<th class="tg-importance">importance</th>' +
    '<th class="tg-link">link</th>' +
    '</tr>'));

  var json_url = window.location.href.replace('results.html', 'results.json');
  $.get(json_url, function (data) {
    var results = data.results;
    var dates = [];
    var cruises = [];
    $.each(results, function (i, cruise) {
      if (cruises.indexOf(cruise.id) > -1) {
        return;
      }
      dates.push(new Date(cruise.date_start));
      dates.push(new Date(cruise.date_end));
      var tr = $('<tr/>');
      tr.append($('<td/>').html(cruise.date_start));
      tr.append($('<td/>').html(cruise.date_end));
      tr.append($('<td/>').html(cruise.expocode));
      tr.append($('<td/>').html(cruise.id));
      tr.append($('<td/>'));
      tr.append($('<td/>').html(i + 40));
      tr.append($('<td/>').html(cruise.obj_url));
      datatable.append(tr);
      cruises.push(cruise.id);
    });

    dates = $.grep(dates, function (x) {
      return x && x.getTime && !isNaN(x.getTime());
    });
    if (dates) {
      var sumdates = 0;
      $.each(dates, function (i, x) { sumdates += x.getTime(); });
      var avgdate = new Date(Math.floor(sumdates / dates.length));
      datatable.attr('focus_date', dateToYYYYmmdd(avgdate));
    } else {
      datatable.attr('focus_date', dateToYYYYmmdd(new Date()));
    }

    timeglider.timeline({
      data_source: '#datatable',
      min_zoom: 20,
      max_zoom: 50,
      display_zoom_level: false
    });
  }, 'json');
});
