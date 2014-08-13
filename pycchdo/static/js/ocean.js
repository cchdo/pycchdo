$(function () {
  var large = $('#map img');
  $('.meta .map').css('display', 'none');
  $('.meta').each(function () {
    var map = $(this).find('.map');
    $(this).mouseover(function () {
      large.attr('src', map.attr('src'));
    });
  });
  $('map area').each(function () {
    var a = $(this);
    var id = a.attr('id');
    var pieces = large.attr('src').split('/');
    var parts = String(pieces.slice(-1)).split('_');
    var name = [parts[0], '_', id, '.gif'].join('');
    var src = pieces.slice(0, -1).concat([name]).join('/');
    a.mouseover(function () {
      large.attr('src', src);
    });
  });
});
