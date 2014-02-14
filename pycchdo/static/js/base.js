// usage: log('inside coolFunc', this, arguments);
// paulirish.com/2009/log-a-lightweight-wrapper-for-consolelog/
window.log = function(){
  log.history = log.history || [];   // store logs to an array for reference
  log.history.push(arguments);
  if(this.console) {
   arguments.callee = arguments.callee.caller;
   var newarr = [].slice.call(arguments);
   (typeof console.log === 'object' ? log.apply.call(console.log, console, newarr) : console.log.apply(console, newarr));
  }
};
// make it safe to use console.log always
(function(b){function c(){}for(var d="assert,count,debug,dir,dirxml,error,exception,group,groupCollapsed,groupEnd,info,log,timeStamp,profile,profileEnd,time,timeEnd,trace,warn".split(","),a;a=d.pop();){b[a]=b[a]||c}})((function(){try
{console.log();return window.console;}catch(err){return window.console={};}})());

function addEvent(obj, evt, fn) {
  if (obj.addEventListener) {
    obj.addEventListener(evt, fn, false);
  } else if (obj.attachEvent) {
    obj.attachEvent('on' + evt, fn);
  }
}
function removeEvent(obj, evt, fn) {
  if (obj.removeEventListener) {
    obj.removeEventListener(evt, fn, false);
  } else if (obj.attachEvent) {
    obj.detachEvent('on' + evt, fn);
  }
}
function addEventOnce(obj, evt, fn) {
  function wrapper() {
    fn.call(this, this.arguments);
    removeEvent(obj, evt, wrapper);
  }
  addEvent(obj, evt, wrapper);
}
function eventTarget(e) {
  var target;
  if (!e) {
    var e = window.event;
  }
  if (e.target) {
    target = e.target;
  } else if (e.srcElement) {
    target = e.srcElement;
  }
  return target;
}

function has_class(e, c) {
  return e.className.indexOf(c) >= 0;
}
function add_class(e, c) {
  if (!has_class(e, c)) {
    e.className = e.className + ' ' + c;
  }
}
function remove_class(e, c) {
  e.className = e.className.replace(new RegExp(' ' + c, 'g'), '');
}

(function menuMods() {
  var menu_expand_ack = 'menu_expand_acknowledged';
  var menu_prefer_arrows = 'menu_prefer_arrows';

  function Expander() {
    this.li = document.createElement('LI');
    this.li.className = 'reverse expander';
    this.h1 = document.createElement('H1');
    this.link = document.createElement('A');
    this.link.href = 'javascript:void(0);';
    this.h1.appendChild(this.link);
    this.li.appendChild(this.h1);
  }
  Expander.prototype.open = function(p) {
    if (p) {
      this.link.title = 'Collapse';
    } else {
      this.link.title = 'Expand';
    }
  };
  Expander.prototype.element = function() {
    return this.li;
  };

  function ExpanderMore() {
    this.li = document.createElement('LI');
    this.li.className = 'reverse expander more';
    this.h1 = document.createElement('H1');
    this.link = document.createElement('A');
    this.link.href = 'javascript:void(0);';
    this.h1.appendChild(this.link);
    this.li.appendChild(this.h1);
  }
  ExpanderMore.prototype.open = function(p) {
    if (p) {
      this.link.title = 'Collapse';
      this.link.innerHTML = 'Less';
    } else {
      this.link.title = 'Expand';
      this.link.innerHTML = 'More';
    }
  };
  ExpanderMore.prototype.element = function() {
    return this.li;
  };

  var menuArrows = true;
  if (window.localStorage) {
    menuArrows = window.localStorage.getItem(menu_prefer_arrows) == '1';
  }

  var menu = document.getElementById('cchdo_menu');
  var ul = menu.children[0];
  var openfns = (function toggleableMenu() {
    var expanders = [];
    var children = ul.children;

    if (menuArrows) {
      for (var i = children.length - 1; i >= 0; i--) {
        var child = children[i];
        if (has_class(child, 'expandable')) {
          var expander = new Expander();
          expanders.push(expander);
          if (i == children.length - 1) {
            ul.appendChild(expander.element());
          } else {
            ul.insertBefore(expander.element(), children[i + 1]);
          }
        }
      }
      addEvent(expanders[expanders.length - 1], 'dblclick', function(event) {
        if (window.localStorage) {
          if (window.localStorage.getItem(menu_prefer_arrows) != '1') {
            window.localStorage.setItem(menu_prefer_arrows, '1');
          } else {
            window.localStorage.setItem(menu_prefer_arrows, '1');
          }
        }
      });
    } else {
      var expander = new ExpanderMore();
      expanders.push(expander);
      ul.appendChild(expander.element());
    }

    function isOpen() {
      return has_class(ul, 'open');
    }

    function open(predicate) {
      if (predicate) {
        add_class(ul, 'open');
      } else {
        remove_class(ul, 'open');
      }
      for (var i = 0; i < expanders.length; i++) {
        expanders[i].open(predicate);
      }
    }

    function toggle(event) {
      open(!isOpen());
      if (window.localStorage) {
        window.localStorage.setItem(menu_expand_ack, '1');
      }
      if (event.stopPropagation) {
        event.stopPropagation();
      }
      return false;
    }

    var picdom = document.getElementById('picture');
    addEvent(picdom, 'click', toggle);
    addEvent(ul, 'click', function(event) {
      var target = eventTarget(event);
      if (target === ul || 
          target.tagName == 'LI' ||
          (target.tagName == 'A' && target.href == 'javascript:void(0);')) {
        toggle(event);
      }
    });
    addEvent(document.body, 'click', function() {
      open(false);
    });
    open(false);

    if (!window.localStorage ||
        window.localStorage.getItem(menu_expand_ack) != '1') {
      addEventOnce(ul, 'mouseover', function() {
        for (var i = 0; i < expanders.length; i++) {
          add_class(expanders[i].element(), 'lightup');
          setTimeout(function() {
            for (var i = 0; i < expanders.length; i++) {
              remove_class(expanders[i].element(), 'lightup');
            }
          }, 500);
        }
      });
    }
    return [open, isOpen];
  })();
  var open = openfns[0];
  var isOpen = openfns[1];
  (function tabableMenu() {
    function walkFor(root, tagname, callback) {
      for (var i = 0; i < root.children.length; i++) {
        walkFor(root.children[i], tagname, callback);
      }
      if (root.tagName == tagname) {
        callback(root);
      }
    }
    function Menu(root) {
      this.root = root;
      this.openWhenEntered = null;
      this.cancelOpen = false;
      this.delayOpenInProgress = false;

      var self = this;
      walkFor(root, 'A', function (a) {
        self.addItem(a);
      });
    }
    Menu.prototype.isInMenu = function(elem) {
      var node = elem;
      while (node !== document.body) {
        if (elem === this.root) {
          return true;
        }
        elem = elem.parentNode;
      }
      return false;
    };
    Menu.prototype.delayedOpen = function() {
      var self = this;
      if (this.delayOpenInProgress) {
        return;
      }
      setTimeout(function() {
        self.delayOpenInProgress = false;
        if (self.cancelOpen) {
          self.cancelOpen = false;
          return;
        }
        open(self.openWhenEntered);
        self.openWhenEntered = null;
      }, 0);
      this.delayOpenInProgress = true;
    };
    Menu.prototype.addItem = function(a) {
      new Item(a, this);
    };

    function Item(e, menu) {
      this.e = e;
      this.menu = menu;
      this.lis = [];
      var f = e;
      while (f !== menu.root) {
        if (f.tagName == 'LI') {
          this.lis.push(f);
        }
        f = f.parentNode;
      }

      var self = this;
      addEvent(e, 'focus', function () {
        menu.cancelOpen = true;
        if (menu.openWhenEntered === null) {
          menu.openWhenEntered = isOpen();
        }
        open(true);
        self.setFocus(true);
      });
      addEvent(e, 'blur', function () {
        self.setFocus(false);
        menu.delayedOpen();
      });
    }
    Item.prototype.setFocus = function(on) {
      if (on) {
        func = add_class;
      } else {
        func = remove_class;
      }
      for (var i = 0; i < this.lis.length; i++) {
        func(this.lis[i], 'focus');
      }
      func(this.e, 'focus');
    };

    var menu = new Menu(ul);
  })();
})();
(function imgmap_mobile_toggle() {
  // Adapted from http://home.comcast.net/~urbanjost/semaphore.html
  function _map(lambda, list) {
    var newlist = [];
    for (var i = 0; i < list.length; i++) {
      var x = list[i];
      newlist.push(lambda.call(x));
    }
    return newlist;
  }

  function natural_width(img) {
    return img.naturalWidth ? img.naturalWidth : img.width;
  };
  function natural_height(img) {
    return img.naturalHeight ? img.naturalHeight : img.height;
  };
  function curr_width(img) {
    return img.width;
  };
  function curr_height(img) {
    return img.height;
  };

  function ResizableImgMap(img, map) {
    this.map = map;
    this.img = img;

    this._width = natural_width(this.img);
    this._height = natural_height(this.img);

    this._coords = [];

    var areas = this.map.children;
    for (var i = 0; i < areas.length; i++) {
      var area = areas[i];
      var coords = _map(function () { return Number(this); },
                        area.coords.split(','));
      this._coords.push([area, coords]);
    }
  }

  // Check image dimensions and resize the map appropriately
  ResizableImgMap.prototype.resize = function () {
    var cwidth = curr_width(this.img);
    var cheight = curr_height(this.img);

    var ratio = cwidth / this._width;
    if (!isFinite(ratio) || ratio == 0) {
      return;
    }
    _map(function () {
      var area = this[0];
      var coords = this[1];
      var scaled = _map(function () { return Math.round(this * ratio); },
                        coords);
      var coordstr = scaled.join(',');
      area.coords = coordstr;
    }, this._coords);
  };

  // Detect all images with maps; wrap and resize them.
  var ims = [];
  var imgs = document.getElementsByTagName('img');
  var img_maps = {};
  for (var i = 0; i < imgs.length; i++) {
    var img = imgs[i];
    if (img.useMap) {
      img_maps[img.useMap.slice(1)] = img;
    }
  }
  var maps = document.getElementsByTagName('map');
  for (var i = 0; i < maps.length; i++) {
    var map = maps[i];
    var img = img_maps[map.name];

    var im = new ResizableImgMap(img, map);
    ims.push(im);
  }
  function resizeImgMaps() {
    // Breathe for half a second so the style settles
    // TODO Find a better way to resize. perhaps when image size changes?
    setTimeout(function () {
      _map(function () { this.resize(); }, ims);
    }, 500);
  }

// mobileToggle
  var links = document.getElementsByTagName('link');
  var mobile_links = [];
  var mobile_meta = null;
  for (var i = 0; i < links.length; i++) {
    var link = links[i];
    if (link.className == 'mobile') {
      mobile_links.push(link);
      link.data_href = link.href;
    }
  }
  var metas = document.getElementsByTagName('meta');
  for (var i = 0; i < metas.length; i++) {
    var meta = metas[i];
    if (meta.className == 'mobile') {
      mobile_meta = meta;
      mobile_meta.data_content = mobile_meta.content;
      break;
    }
  }

  var link_mobile = document.getElementById('screensize-mobile');
  var link_full = document.getElementById('screensize-full');
  function clickLinkMobile() {
    for (var i = 0; i < mobile_links.length; i++) {
      var link = mobile_links[i];
      link.href = link.data_href;
      if (link.media == 'handheld') {
        link.media = 'all,handheld';
      }
    }
    if (mobile_meta) {
      mobile_meta.content = mobile_meta.data_content;
    }
    if (window.sessionStorage) {
      window.sessionStorage.removeItem('pin_large_screen');
    }
    resizeImgMaps();
    return false;
  }
  addEvent(link_mobile, 'click', clickLinkMobile);
  function clickLinkFull() {
    for (var i = 0; i < mobile_links.length; i++) {
      var link = mobile_links[i];
      link.href = '';
      if (link.media == 'all,handheld') {
        link.media = 'handheld';
      }
    }
    if (mobile_meta) {
      mobile_meta.content = '';
    }
    if (window.sessionStorage) {
      window.sessionStorage.setItem('pin_large_screen', '1');
    }
    resizeImgMaps();
    return false;
  }
  addEvent(link_full, 'click', clickLinkFull);
  addEvent(window, 'load', function () {
    if (window.sessionStorage) {
      var pin_large_screen = window.sessionStorage.getItem('pin_large_screen');
      if (pin_large_screen == '1') {
        clickLinkFull();
      } else if (pin_large_screen == '0') {
        clickLinkMobile();
      }
    } else {
      resizeImgMaps();
    }
  });
})();
var bannerControl = (function rotateBanner() {
  if (window.localStorage) {
    var picdom = document.getElementById('picture');
    picdom.className += ' unselectable';
    var ok = document.createElement('DIV');
    ok.innerHTML = '';
    ok.style.color = 'red';
    ok.style.font = '3em monospace';
    ok.style.position = 'relative';
    ok.style.textShadow = 'white 0 0 0.5em';
    ok.style.zIndex = 101;
    picdom.appendChild(ok);

    function toggleBanner() {
      var rot = window.localStorage.getItem('bannerOff') !== null;
      if (rot) {
        window.localStorage.removeItem('bannerOff');
        startRotators();
      } else {
        window.localStorage.setItem('bannerOff', '1');
        stopRotators();
      }
      ok.innerHTML = '<p>rotation ' + (rot ? 'on' : 'off') + '</p>';
      setTimeout(function () {
        ok.innerHTML = '';
      }, 500);
      clickcount = 0;
    }

    var dragthresh = 500;
    var start;
    addEvent(picdom, 'mousedown', function (event) {
      start = event.clientX;
    });
    addEvent(picdom, 'mouseup', function (event) {
      if (Math.abs(event.clientX - start) >= dragthresh) {
        toggleBanner();
      }
    });
    addEvent(picdom, 'touchstart', function (event) {
      if (event && event.changedTouches && event.changedTouches.length > 0) {
        start = event.changedTouches[0].clientX;
      }
    });
    addEvent(picdom, 'touchmove', function (event) {
      if (event && event.changedTouches && event.changedTouches.length > 0) {
        end = event.changedTouches[0].clientX;
        if (Math.abs(end - start) < dragthresh) {
          event.preventDefault();
        }
      }
    });
    addEvent(picdom, 'touchend', function (event) {
      if (event && event.changedTouches && event.changedTouches.length > 0) {
        end = event.changedTouches[0].clientX;
        if (Math.abs(end - start) >= dragthresh) {
          toggleBanner();
        }
      }
    });
  }

  var supportTransition = (function () {
    // https://gist.github.com/373874
    var renderers = "Webkit Moz Ms O".split(' ');
    var body = document.body || document.documentElement,
        style = body.style;
    for (var i = 0; i < renderers.length; i++) {
      var s = renderers[i] + 'Transition';
      if (style[s] !== undefined) {
        return s;
      }
    }
    if (style.transition !== undefined) {
      return 'transition';
    }
    return null;
  })();

  function setOffset(s, x) {
    s.backgroundPosition = ['0 ', x, 'px'].join('');
  }

  function setOpacity(s, x) {
    s.opacity = x;
    s.filter = ['alpha(opacity=', x * 100, ')'].join('');
  }

  function defaultTo(x, d) {
    if (x) {
      return x;
    }
    return d;
  }

  function setZ(s, v) {
    s.zIndex = v;
  }

  function Rotator(domobjA, domobjB, num_banners, zs, delay, animateTime,
                   offset, height) {
    this.zs = defaultTo(zs, [100, 99]);
    this.delay = defaultTo(delay, 1000 * 10);
    this.animateTime = defaultTo(animateTime, 1000 * 3);

    this.height = defaultTo(height, 125);
    this.offset = defaultTo(offset, 0) * -this.height;

    // If the difference is less than ~100ms there will be jumps and flickers
    // due to asynchronicity of animation
    var diff = 100;
    if (this.delay < this.animateTime + diff) {
      this.animateTime = this.delay - diff;
    }
    this.isA = true;

    this.domA = domobjA;
    this.domB = domobjB;
    this.styleA = domobjA.style;
    this.styleB = domobjB.style;
    this.minoffset = -this.height * num_banners;
    setOpacity(this.styleB, 0);
    setOffset(this.styleA, this.offset);
    setOffset(this.styleB, this.offset);

    setZ(this.styleA, this.zs[0]);
    setZ(this.styleB, this.zs[1]);

    var bgSize = ['100% ', num_banners * 100, '%'].join('');
    this.styleA.backgroundSize = bgSize;
    this.styleB.backgroundSize = bgSize;

    if (supportTransition) {
      this.styleA[supportTransition] = 
        'opacity ' + this.animateTime / 1000 + 's linear';
      this.styleB[supportTransition] =
        'opacity ' + this.animateTime / 1000 + 's linear';
    }
  }

  Rotator.prototype.o = function (x, s) {
    var shift = (s == this.styleA) ? (this.isA ? 0 : 1) : (this.isA ? 1 : 0);
    return Math.abs(Math.cos(Math.PI * (x + shift) / 2))
  };

  Rotator.prototype.animate = function (next) {
    /* Bit of a race condition when animation starts before one finishes. Not
     usually a problem. */

    if (this.isA) {
      setOffset(this.styleB, next);
    } else {
      setOffset(this.styleA, next);
    }

    var self = this;

    if (supportTransition) {
      setTimeout(function () { self._doneAnimating(next); }, self.animateTime);
      this._animateTarget();
      return;
    }

    var startTime = new Date();
    (function () {
      var elapsed = new Date() - startTime,
          ratio = Math.min(elapsed / self.animateTime, 1);

      setOpacity(self.styleA, self.o(ratio, self.styleA));
      setOpacity(self.styleB, self.o(ratio, self.styleB));

      if (elapsed < self.animateTime) {
        setTimeout(arguments.callee, self.animateTime / 45);
      } else {
        self._animateTarget();
        self._doneAnimating(next);
      }
    })();
  };

  var className = ' showing';

  Rotator.prototype._animateTarget = function() {
    if (this.isA) {
      setOpacity(this.styleA, 0);
      setOpacity(this.styleB, 1);
      setZ(this.styleA, this.zs[0]);
      setZ(this.styleB, this.zs[1]);
      this.domA.className += className;
      this.domB.className = this.domB.className.replace(className, '');
    } else {
      setOpacity(this.styleB, 0);
      setOpacity(this.styleA, 1);
      setZ(this.styleB, this.zs[0]);
      setZ(this.styleA, this.zs[1]);
      this.domB.className += className;
      this.domA.className = this.domA.className.replace(className, '');
    }
  };

  Rotator.prototype._doneAnimating = function (next) {
    this.isA = !this.isA;

    this.offset = next;
    if (this.offset <= this.minoffset) {
      this.offset = 0;
      next = -this.height;
    }
    if (window.sessionStorage) {
      window.sessionStorage.setItem('bannerOffset', this.offset / -this.height);
    }
  };

  Rotator.prototype.nextOffset = function () {
    return this.offset - this.height;
  };

  Rotator.prototype.next = function () {
    this.animate(this.nextOffset());
  }

  Rotator.prototype.start = function () {
    var self = this;
    var timer = null;
    self.shouldStop = false;
    (function () {
      if (timer) {
        clearTimeout(timer);
        if (!self.shouldStop) {
          self.next();
        }
      }
      if (!self.shouldStop) {
        timer = setTimeout(arguments.callee, self.delay);
      }
    })();
  };

  Rotator.prototype.stop = function () {
    this.shouldStop = true;
  };

  var bannerOffset = 0;
  if (window.sessionStorage) {
    bannerOffset = window.sessionStorage.getItem('bannerOffset');
  }
  var a = [document.getElementById('bannerA'), document.getElementById('bannerB')];
  var b = [document.getElementById('bannerC'), document.getElementById('bannerD')];
  var rotators = [];
  if (a[0] && a[1]) {
    rotators.push(new Rotator(a[0], a[1], 14, [100, 99], null, null, bannerOffset));
  }
  if (b[0] && b[1]) {
    rotators.push(new Rotator(b[0], b[1], 14, [98, 97], null, null, bannerOffset));
  }

  function startRotators() {
    for (var i = 0; i < rotators.length; i++) {
      rotators[i].start();
    }
  }

  function stopRotators() {
    for (var i = 0; i < rotators.length; i++) {
      rotators[i].stop();
    }
  }

  startRotators();
  if (window.localStorage && window.localStorage.getItem('bannerOff')) {
    stopRotators();
  }
  return [toggleBanner, startRotators, stopRotators];
})();
(function easter() {
  if (window.localStorage) {
    var egg = document.createElement('DIV');
    egg.style.float = 'right';
    egg.style.width = '1em';
    egg.style.textAlign = 'right';
    egg.style.color = '#DDDDDD';
    egg.style.cursor = 'pointer';
    egg.innerHTML = '&sigma;';
    document.getElementById('gfooter').appendChild(egg);

    var basket = document.createElement('DIV');
    basket.id = 'easterEggBasket';
    basket.style.position = 'absolute';
    basket.style.padding = '2em';
    basket.style.bottom = '0';
    basket.style.right = '0';
    basket.style.zIndex = 999;
    basket.style.background = 'rgba(0, 0, 0, 0.8)';
    basket.style.display = 'none';
    basket.style.textAlign = 'center';
    var bunny = document.createElement('DIV');
    bunny.style.width = '25em';
    bunny.style.textAlign = 'left';
    bunny.style.margin = '0 auto';
    bunny.style.color = '#FFFFFF';
    basket.appendChild(bunny);
    document.getElementById('gfooter').appendChild(basket);

    addEvent(egg, 'click', function(event) {
      if (basket.style.display == 'none') {
        basket.style.display = 'block';
      } else {
        basket.style.display = 'none';
      }
    });

    function addToggle(elem, text, toggle) {
      var d = document.createElement('DIV');
      var tog = 'easter_' + toggle;
      var check = document.createElement('INPUT');
      check.type = 'checkbox';
      check.id = tog;
      var label = document.createElement('LABEL');
      label.htmlFor = tog;
      label.innerHTML = text;
      d.appendChild(check);
      d.appendChild(document.createTextNode(' '));
      d.appendChild(label);
      elem.appendChild(d);

      if (window.localStorage.getItem(toggle) == '1') {
        check.checked = 'checked';
      } else {
        check.checked = '';
      }
      addEvent(check, 'change', function() {
        if (check.checked == '') {
          window.localStorage.removeItem(toggle);
        } else {
          window.localStorage.setItem(toggle, '1');
        }
      });
    }

    addToggle(bunny, 'Prefer arrows on menu instead of "More"', 'menu_prefer_arrows');
    addToggle(bunny, 'Freeze the banner image', 'bannerOff');

    var d = document.createElement('DIV');
    var selid = 'easter_bannerOffset';
    var sel = document.createElement('SELECT');
    var opt = document.createElement('OPTION');
    sel.appendChild(opt);
    for (var i = 0; i < 14; i++) {
      var opt = document.createElement('OPTION');
      opt.innerHTML = i;
      sel.appendChild(opt);
    }
    sel.id = selid;
    var label = document.createElement('LABEL');
    label.htmlFor = selid;
    label.innerHTML = 'Start on banner #';
    d.appendChild(label);
    d.appendChild(document.createTextNode(' '));
    d.appendChild(sel);
    bunny.appendChild(d);

    var key = 'bannerOffset';
    if (window.sessionStorage.getItem(key)) {
      sel.value = window.sessionStorage.getItem(key);
    }
    addEvent(sel, 'change', function() {
      if (sel.value == '') {
        window.sessionStorage.removeItem(key);
      } else {
        window.sessionStorage.setItem(key, sel.value);
      }
    });

    var apply = document.createElement('BUTTON');
    apply.innerHTML = 'Apply/refresh page';
    basket.appendChild(apply);
    addEvent(apply, 'click', function() {
      window.location.reload();
    });

    var close = document.createElement('A');
    close.style.color = '#FFFFFF';
    close.style.position = 'absolute';
    close.style.display = 'block';
    close.style.top = '1em';
    close.style.right = '1em';
    close.href = 'javascript:void(0)';
    close.innerHTML = 'x';
    basket.appendChild(close);
    addEvent(close, 'click', function() {
      basket.style.display = 'none';
    });
  }
})();
