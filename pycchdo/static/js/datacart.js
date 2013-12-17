jQuery(function($) {
  // Don't instrument the datacart download list page. That requires removing
  // list elements and changing page logic.
  if (window.location.pathname.split('/')[0] == 'datacart') {
    return;
  }
  var datacart_cart = $('#datacart_status');
  var datacart_count = datacart_cart.find('.count');

  function getCartCount() {
    return parseInt(datacart_count.html());
  }
  function setCartCount(count) {
    datacart_count.html(count);
    if (count > 0) {
      datacart_cart.removeClass('hidden');
    } else {
      datacart_cart.addClass('hidden');
    }
  }

  // Make cart disappear if it is empty
  setCartCount(getCartCount());

  function setIconAdd(icon) {
    var link = icon.closest('.datacart-link');
    link.removeClass('datacart-remove').addClass('datacart-add');
    link.attr('title', link.attr('title').replace('Remove', 'Add').replace('from', 'to'));
    icon.html(icon.html().replace('Remove', 'Add'));
  }
  function setIconRemove(icon) {
    var link = icon.closest('.datacart-link');
    link.removeClass('datacart-add').addClass('datacart-remove');
    link.attr('title', link.attr('title').replace('Add', 'Remove').replace('to', 'from'));
    icon.html(icon.html().replace('Add', 'Remove'));
  }

  $('body').delegate('.datacart-icon:not(.datacart-cart)', 'click', function() {
    var icon = $(this);
    var link = icon.closest('.datacart-link');
    if (link.hasClass('datacart-results')) {
      return true;
    }
    var parser = document.createElement("A");
    parser.href = link.attr('href');
    var adder;
    if (link.hasClass('datacart-add')) {
      parser.pathname = parser.pathname.replace("remove", "add");
      adder = true;
    } else if (link.hasClass('datacart-remove')) {
      parser.pathname = parser.pathname.replace("add", "remove");
      adder = false;
    } else {
      return;
    }
    $.get(parser.href, function(data) {
      setCartCount(data.cart_count);
      if (adder) {
        setIconRemove(icon);
      } else {
        setIconAdd(icon);
      }
      if (link.hasClass('datacart-cruise')) {
        // change all the icons for the cruise's files
        var dclinks = link.parents('.datacart-cruise-links');
        var formats_sections = dclinks.siblings('.formats-sections');
        if (formats_sections.length == 0) {
          formats_sections = dclinks.parents('tr').find('.formats-sections');
        }
        formats_sections.find('.datacart-icon').each(function() {
          if (adder) {
            setIconRemove($(this));
          } else {
            setIconAdd($(this));
          }
        });
      } else {
        var list = link.closest('.formats-sections');
        var links = list.find('.datacart-link');
        var alladd = true;
        var allremove = true;
        links.each(function() {
          alladd = alladd && $(this).hasClass('datacart-add');
          allremove = allremove && $(this).hasClass('datacart-remove');
        });
        if (alladd || allremove) {
          var cruiseicon = list.siblings('.datacart-cruise-links').find('.datacart-icon');
          if (alladd) {
            setIconAdd(cruiseicon);
          } else if (allremove) {
            setIconRemove(cruiseicon);
          }
        }
      }
    });
    return false;
  });
});
