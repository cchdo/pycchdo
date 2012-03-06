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

(function menuMods() {
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
  var menu = document.getElementById('cchdo_menu');
  var ul = menu.children[0];
  var openfns = (function toggleableMenu() {
    var expander = document.createElement('LI');
    expander.className = 'expander';
    var h1 = document.createElement('H1');
    var link = document.createElement('A');
    link.href = 'javascript:void(0);';
    h1.appendChild(link);
    expander.appendChild(h1);
    ul.appendChild(expander);

    function isOpen() {
      return has_class(ul, 'open');
    }

    function open(p) {
      if (p) {
        add_class(ul, 'open');
        link.innerHTML = 'close menu';
        link.title = 'Unpin';
      } else {
        remove_class(ul, 'open');
        link.innerHTML = 'open menu';
        link.title = 'Pin open';
      }
    }

    function toggle(event) {
      open(!isOpen());
      if (window.localStorage) {
        window.localStorage.setItem('menu_pin_acknowledged', '1');
      }
      if (event.stopPropagation) {
        event.stopPropagation();
      }
      return false;
    }

    var picdom = document.getElementById('picture');
    addEvent(expander, 'click', toggle);
    addEvent(picdom, 'click', function (event) {
      toggle(event);
    });
    addEvent(ul, 'click', function (event) {
      var target = eventTarget(event);
      if (target === ul || target.tagName == 'LI') {
        toggle(event);
      }
    });
    addEvent(document.body, 'click', function () {
      open(false);
    });
    open(false);

    function addFlasher() {
      addEventOnce(ul, 'mouseover', function () {
        add_class(expander, 'lightup');
        setTimeout(function () {
          remove_class(expander, 'lightup');
        }, 500);
      });
    }

    if (window.localStorage) {
      if (window.localStorage.getItem('menu_pin_acknowledged') != '1') {
        addFlasher();
      }
    } else {
      addFlasher();
    }
    return [open, isOpen];
  })();
  var open = openfns[0];
  var isOpen = openfns[1];
  (function tabableMenu() {
    function addfocusblur(e, limit) {
      var lis = [];
      var f = e;
      while (f !== limit) {
        if (f.tagName == 'LI') {
          lis.push(f);
        }
        f = f.parentNode;
      }
      var previousOpenness = false;
      addEvent(e, 'focus', function () {
        previousOpenness = isOpen();
        open(true);
        for (var i = 0; i < lis.length; i++) {
          add_class(lis[i], 'focus');
        }
        add_class(e, 'focus');
      });
      addEvent(e, 'blur', function () {
        open(previousOpenness);
        for (var i = 0; i < lis.length; i++) {
          remove_class(lis[i], 'focus');
        }
        remove_class(e, 'focus');
      });
    }
    function walkFor(root, tagname, callback) {
      for (var i = 0; i < root.children.length; i++) {
        walkFor(root.children[i], tagname, callback);
      }
      if (root.tagName == tagname) {
        callback(root);
      }
    }
    walkFor(ul, 'A', function (a) {
      addfocusblur(a, ul);
    });
  })();
})();
(function defaultFocus() {
  document.getElementById('query').focus();
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
    // FIXME Find a better way. Resize when detected image size change?
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
(function rotateBanner() {
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

  function rotator(domobjA, domobjB, num_banners, zs, delay, animateTime,
                   offset, height) {
    this.zs = defaultTo(zs, [100, 99]);
    this.delay = defaultTo(delay, 1000 * 10);
    this.animateTime = defaultTo(animateTime, 1000 * 3);

    this.offset = defaultTo(offset, 0);
    this.height = defaultTo(height, 125);

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

  rotator.prototype.o = function (x, s) {
    var shift = (s == this.styleA) ? (this.isA ? 0 : 1) : (this.isA ? 1 : 0);
    return Math.abs(Math.cos(Math.PI * (x + shift) / 2))
  };

  rotator.prototype.animate = function (next) {
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

  rotator.prototype._animateTarget = function() {
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

  rotator.prototype._doneAnimating = function (next) {
    this.isA = !this.isA;

    this.offset = next;
    if (this.offset <= this.minoffset) {
      this.offset = 0;
      next = -this.height;
    }
    if (window.sessionStorage) {
      window.sessionStorage.setItem('bannerOffset', this.offset);
    }
  };

  rotator.prototype.nextOffset = function () {
    return this.offset - this.height;
  };

  rotator.prototype.next = function () {
    this.animate(this.nextOffset());
  }

  rotator.prototype.start = function () {
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

  rotator.prototype.stop = function () {
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
    rotators.push(new rotator(a[0], a[1], 14, [100, 99], null, null, bannerOffset));
  }
  if (b[0] && b[1]) {
    rotators.push(new rotator(b[0], b[1], 14, [98, 97], null, null, bannerOffset));
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

  if (window.localStorage) {
    if (window.localStorage.getItem('bannerOff')) {
      return;
    }
  }
  startRotators();
})();
