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
  var img = $('#ocean_selector_map img');
  var basepath = img.attr('src').slice(0, img.attr('src').indexOf('base'));

  function filename(ocean) {
    return basepath + ocean + '.png';
  }

  function swapin(ocean) {
    img.attr('src', filename(ocean));
  }

  var imgs = [];
  var oceans = ['arctic', 'indian', 'pacific', 'atlantic', 'southern'];
  for (var i = 0; i < oceans.length; i++) {
    var ocean = oceans[i];
    imgs.push(filename(ocean));
  }
  jQuery.preLoadImages.apply(this, imgs);

  $('#ocean_selector_map').mouseout(function () {
    swapin('base');
  });
  $('#ocean_selector_map .hoverable.ocean').each(function () {
    $(this).mouseover(function () {
      swapin(this.alt.toLowerCase());
    });
  });
});
