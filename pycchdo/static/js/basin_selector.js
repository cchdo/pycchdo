/* http://engineeredweb.com/blog/09/12/preloading-images-jquery-and-javascript */
(function($) {
  var cache = [];
  // Arguments are image paths relative to the current page.
  $.preLoadImages = function() {
    var args_len = arguments.length;
    for (var i = args_len; i--;) {
      var cacheImage = document.createElement('img');
      cacheImage.src = arguments[i];
      cache.push(cacheImage);
    }
  }
})(jQuery)

$(function () {
  var img = $('#basin_selector_map img');
  var basepath = img.attr('src').slice(0, img.attr('src').indexOf('base'));

  function filename(basin) {
    return basepath + basin + '.png';
  }

  function swapin(basin) {
    img.attr('src', filename(basin));
  }

  var imgs = [];
  var basins = ['arctic', 'indian', 'pacific', 'atlantic', 'southern'];
  for (var i = 0; i < basins.length; i++) {
    var basin = basins[i];
    imgs.push(filename(basin));
  }
  jQuery.preLoadImages.apply(this, imgs);

  $('#basin_selector_map').mouseout(function () {
    swapin('base');
  });
  $('#basin_selector_map .hoverable.basin').each(function () {
    $(this).mouseover(function () {
      swapin(this.alt.toLowerCase());
    });
  });
});
