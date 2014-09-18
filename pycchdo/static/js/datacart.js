var page_df_info = {
  data_for: {},
  all: [],
  expocodes: []
};

function anyInCart(dfiles) {
  if (!dfiles) {
    return false;
  }
  for (var j = 0; j < dfiles.length; j++) {
    if (page_df_info[dfiles[j]].incart) {
      return true;
    }
  }
  return false;
}

function make_datacart_links(cart) {
  var file_links = document.getElementsByClassName("datacart-link-file-placeholder");
  // since we are changing the classNames of the nodes, we need to go through the nodelist in reverse
  for (var i = file_links.length -1; i >= 0; i--){
    var elm = file_links[i];
    var dobj = {};
    var dataid = elm.getAttribute('dataid');
    var datafname = elm.getAttribute('datafname');
    var expocode = elm.getAttribute('expocode');
    var data_key = cart.genKey(dataid, datafname);
    dobj.incart = cart.isKeyIn(data_key);
    elm.setAttribute('incart', dobj.incart);
    dobj.fname = datafname;
    dobj.expocode = expocode;
    if (!page_df_info.hasOwnProperty(dataid)){
      page_df_info[dataid] = dobj;
    }
    if (page_df_info.expocodes.indexOf(expocode) == -1){
      page_df_info.expocodes.push(expocode);
    }
    if (!page_df_info.data_for.hasOwnProperty(expocode)){
      page_df_info.data_for[expocode] = [];
    }
    if (page_df_info.data_for[expocode].indexOf(dataid) == -1){
      page_df_info.data_for[expocode].push(dataid);
    }
    if (page_df_info.all.indexOf(dataid) == -1){
      page_df_info.all.push(dataid);
    }
    var data_cart_icon = elm.getElementsByClassName("datacart-icon")[0];

    if (dobj.incart){
      data_cart_icon.textContent = 'Remove';
      elm.className = 'datacart-remove datacart-link';
      elm.setAttribute('title', 'Remove data from cart');
    }else{
      data_cart_icon.textContent = 'Add';
      elm.className = "datacart-add datacart-link";
      elm.setAttribute('title', 'Add data to cart');
    }
  }

  // Cruise results add/remove all link
  var cruise_links = document.getElementsByClassName("datacart-cruise-placeholder");
  for (var i = cruise_links.length -1; i >= 0; i--){ 
    var elm = cruise_links[i];
    var expocode = elm.getAttribute('expocode');
    var data_cart_icon = elm.getElementsByClassName('datacart-icon')[0];

    var any_in_cart = anyInCart(page_df_info.data_for[expocode]);
    if (any_in_cart){
      data_cart_icon.textContent = 'Remove All';
      elm.className = 'datacart-remove datacart-cruise datacart-link';
      elm.setAttribute('title', 'Remove all data from cart');
    } else {
      data_cart_icon.textContent = 'Add All';
      elm.className = 'datacart-add datacart-cruise datacart-link';
      elm.setAttribute('title', 'Add all data to cart');
    }
  }

  // Search results add/remove all link
  var results_links = document.getElementsByClassName("datacart-results-placeholder");
  for (var i = results_links.length -1; i >= 0; i--){
    var elm = results_links[i];
    var data_cart_icon = elm.getElementsByClassName('datacart-icon')[0];

    var any_in_cart = anyInCart(page_df_info.all);
    if (any_in_cart) {
      $(data_cart_icon).html('Remove All <span style="display:none" id="working">Working...</span>');
      elm.className = 'datacart-remove datacart-results datacart-link';
      elm.setAttribute('title', 'Remove all data from cart');
    } else {
      $(data_cart_icon).html('Add All <span style="display:none" id="working">Working...</span>');
      elm.className = 'datacart-add datacart-results datacart-link';
      elm.setAttribute('title', 'Add all data to cart');
    }
  }
}

function gen_datacart_download_form(cart, $){
  var files = [];
  cart.forEachKey(function(_, filepath, _) {
    files.push(filepath);
  });
  var form = $(
    '<form action="/datacart/download" method="post" class="tools">' + 
    '<input type="hidden" name="archive" value="'+files.join(',')+'">' +
    '<input type="submit" value="Download All Files" class="download">' +
    '</form>');
  form.append($('<input type="submit" value="Empty Datacart" class="clear">').click(function() {
    cart.empty();
    window.location.reload();
    return false;
  }));
  return form;
}

function gen_datacart_dl_page(cart, $){
  var dc = $(".datacart-dl .box_content");
  var dc_content = "<table>";
  var files = [];
  cart.forEachKey(function(expocode, filepath, filename) {
    files.push(filepath);
    dc_content += '<tr><td>' + 
    '<a href="/cruise/'+expocode +'">'+expocode+'</a></td>'+ 
    '<td>'+ filename + '</td>' +
    '<td><a href="javascript:;" class="datacart-link-file-placeholder" ' +
    'expocode="'+expocode+'" dataid="'+filepath+'" datafname="' + filename + '" ' + 
    'rel="nofollow"><div class="datacart-icon"></div></a>' +
    '</td></tr>';
  });
  dc_content += '</table>';
  if (files.length != 0){
    dc.html(dc_content);
    dc.prepend(gen_datacart_download_form(cart, $));
  }
}

function Cart() {
  this.prefix = 'cchdo_datacart';
  this.sep = '|';
  this.datacart_cart = $('#datacart_status');
  this.datacart_count = this.datacart_cart.find('.count');
  this.syncCount();
}
Cart.prototype = new Object();
Cart.prototype.isKey = function(key) {
  return key.indexOf(this.prefix + this.sep) == 0;
};
Cart.prototype.genKey = function(filepath, filename) {
  return [this.prefix, filepath, filename].join(this.sep);
};
Cart.prototype.isKeyIn = function(key) {
  return key in localStorage;
};
Cart.prototype.addKey = function(key, expocode) {
  localStorage[key] = expocode;
}
Cart.prototype.removeKey = function(key) {
  delete localStorage[key];
}
Cart.prototype.forEachKey = function(lambda) {
  for (var i = 0; i < localStorage.length; i++) {
    var key = localStorage.key(i);
    if (this.isKey(key)) {
      var parts = key.split(this.sep);
      var expocode = localStorage[key];
      var filepath = parts[1];
      var filename = parts[2];
      lambda.call(this, expocode, filepath, filename);
    }
  }
};
Cart.prototype.getCount = function () {
  var count = 0;
  this.forEachKey(function(_, _, _) {
    count++;
  });
  return count;
};
Cart.prototype.setCount = function (count) {
  this.datacart_count.html(count);
  if (count > 0) {
    this.datacart_cart.removeClass('hidden');
  } else {
    this.datacart_cart.addClass('hidden');
  }
};
Cart.prototype.syncCount = function () {
  this.setCount(this.getCount());
};
Cart.prototype.empty = function () {
  if (!window.confirm("This will remove everything in the datacart and cannot be undone")) {
    return;
  }
  var keys = [];
  for (var i = 0; i < localStorage.length; i++) {
    var key = localStorage.key(i);
    if (this.isKey(key)) {
      keys.push(key);
    }
  }
  for (var i = 0; i < keys.length; i++) {
    delete localStorage[keys[i]];
  }
};

jQuery(function($) {
  function supports_html5_storage() {
    try {
      return 'localStorage' in window && window['localStorage'] !== null;
    } catch (e) {
      return false;
    }
  }

  if (!supports_html5_storage()){
    return;
  }

  var cart = new Cart();

  // Generate the datacart results page
  if (window.location.pathname.split('/')[1] == 'datacart.html') {
    // This must occur before make_datacart_links due to use of placeholders
    gen_datacart_dl_page(cart, $);
  }

  make_datacart_links(cart, $);

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
  function toggleDatacartResults(link) {
    $('#working').show('fast');
    window.setTimeout(function(e){
      if (link.hasClass('datacart-remove')){
        $('.datacart-remove:not(.datacart-cruise, .datacart-results) .datacart-icon').click();
        var cruiseIcons = $('.datacart-cruise.datacart-remove .datacart-icon');
        if (cruiseIcons.length > 0) {
          setIconAdd(cruiseIcons);
        }
        setIconAdd(link);
      } else{
        $('.datacart-add:not(.datacart-cruise, .datacart-results) .datacart-icon').click();
        var cruiseIcons = $('.datacart-cruise.datacart-add .datacart-icon');
        if (cruiseIcons.length > 0) {
          setIconRemove(cruiseIcons);
        }
        setIconRemove(link);
      }
      $('#working').hide('fast');
    }, 0);
  }
  function setCruiseDataFiles(icon, link) {
    var expocode = link.attr('expocode');
    var icons = null;
    var files = link.parents('.dataset').children('.formats-sections');
    if (link.hasClass('datacart-remove')){
      setIconAdd(icon);
      icons = $('.datacart a[expocode="'+expocode+'"][incart="true"] .datacart-icon', files);
    } else{
      setIconRemove(icon);
      icons = $('.datacart a[expocode="'+expocode+'"][incart!="true"] .datacart-icon', files)
    }
    icons.click();
  }

  // For every datacart button that is clicked
  $('body').delegate('.datacart-icon:not(.datacart-cart)', 'click', function(e) {
    var icon = $(this);
    var link = icon.closest('.datacart-link');
    // For the search results datacart
    if (link.hasClass('datacart-results')) {
      toggleDatacartResults(link);
      return true;
    }
    // For cruise dataset all button
    if (link.hasClass('datacart-cruise')) {
      setCruiseDataFiles(icon, link);
      return true;
    }
    // For individual cruise data files
    var expocode = link.attr('expocode');
    var dataid = link.attr('dataid');
    var datafname = link.attr('datafname');
    var data_key = cart.genKey(dataid, datafname);
    if (link.attr('incart') == 'true'){
      setIconAdd(icon);
      cart.removeKey(data_key);
      link.attr('incart', 'false');
      page_df_info[dataid].incart = false;
    } else {
      cart.addKey(data_key, expocode);
      setIconRemove(icon);
      link.attr('incart', 'true');
      page_df_info[dataid].incart = true;
    }

    // Update multi-edit links to reflect status of affectable files
    var cruiseLink = $('.datacart-cruise[expocode=' + expocode +'] .datacart-icon');
    if (cruiseLink.length > 0) {
      if (anyInCart(page_df_info.data_for[expocode])) {
        setIconRemove(cruiseLink);
      } else {
        setIconAdd(cruiseLink);
      }
    }

    var resultsLink = $('.datacart-results .datacart-icon');
    if (resultsLink.length > 0) {
      if (anyInCart(page_df_info.all)) {
        setIconRemove(resultsLink);
      } else {
        setIconAdd(resultsLink);
      }
    }

    cart.syncCount();
    return false;
  });
});
