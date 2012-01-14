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

var CCHDO = {
  BASIN_MAP: {
    prefix: '/static/img/maps/basin_selector/',
    images: [
      'arctic_f2.jpg','pacific_f4.jpg','atlantic_f4.jpg',
      'cchdo_search_basin_r3_c2_f4.jpg','cchdo_search_basin_r3_c3_f4.jpg',
      'atlantic_f6.jpg','cchdo_search_basin_r2_c5_f4.jpg',
      'indian_f4.jpg','cchdo_search_basin_r3_c2_f6.jpg','southern_f2.jpg'
    ]
  }
};

function swapImage() {
  var a = arguments;
  var swapped = [];
  for (var i = 0; i < a.length - 1; i += 2) {
    var x = $('#' + a[i])[0];
    if (x != null) {
      swapped.push(x);
      if (!$(x).data('osrc')) {
        $(x).data('osrc', x.src);
      }
      x.src = CCHDO.BASIN_MAP.prefix + a[i + 1];
    }
  }
  $(window).data('swappedImages', swapped);
}
function swapImgRestore() {
  var a = $(window).data('swappedImages');
  if (!a) { return ;}
  for (var i = 0; i < a.length; i += 1) {
    var x = a[i];
    var osrc = $(x).data('osrc');
    if (!osrc) {
      continue;
    }
    x.src = osrc;
  }
}

$(function () {
  var imgs = CCHDO.BASIN_MAP.images;
  for (var i = 0; i < imgs.length; i += 1) {
    imgs[i] = CCHDO.BASIN_MAP.prefix + imgs[i];
  }
  jQuery.preLoadImages.apply(this, imgs);
  $('#basin_map').mouseout(function () {
    swapImgRestore();
  });
  var lastHl = null;
  $('.hoverable.basin').each(function () {
    $(this).mouseover(function () {
      if (lastHl != $(this)[0].className) {
        swapImgRestore();
      } else {
        return;
      }
      if ($(this).hasClass('atlantic')) {
        swapImage(
          'atlantic','atlantic_f6.jpg',
          'cchdo_search_basin_r2_c5','cchdo_search_basin_r2_c5_f4.jpg');
      } else if ($(this).hasClass('indian')) {
        swapImage(
          'indian','indian_f4.jpg',
          'cchdo_search_basin_r3_c2','cchdo_search_basin_r3_c2_f6.jpg');
      } else if ($(this).hasClass('pacific')) {
        swapImage(
          'pacific','pacific_f4.jpg',
          'atlantic','atlantic_f4.jpg',
          'cchdo_search_basin_r3_c2','cchdo_search_basin_r3_c2_f4.jpg',
          'cchdo_search_basin_r3_c3','cchdo_search_basin_r3_c3_f4.jpg');
      } else if ($(this).hasClass('arctic')) {
        swapImage('arctic','arctic_f2.jpg');
      } else if ($(this).hasClass('southern')) {
        swapImage('southern','southern_f2.jpg');
      }
    });
  });
});
