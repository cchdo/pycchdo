(function rotateBanner() {
  if (window.localStorage) {
    var picdom = document.getElementById('picture');
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

    var clickthresh = 2000;
    var then;
    picdom.addEventListener('mousedown', function () {
      then = new Date();
    }, false);
    picdom.addEventListener('mouseup', function () {
      var now = new Date();
      if (now - then >= clickthresh) {
        toggleBanner();
      }
    }, false);
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

  function rotator(domobjA, domobjB, num_banners, zs, delay, animateTime, offset, height) {
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
      this.styleA[supportTransition] = 'opacity ' + this.animateTime / 1000 + 's linear';
      this.styleB[supportTransition] = 'opacity ' + this.animateTime / 1000 + 's linear';
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

  rotator.prototype.start = function () {
    var self = this;
    var timer = null;
    self.shouldStop = false;
    (function () {
      if (timer) {
        clearTimeout(timer);
        if (!self.shouldStop) {
          self.animate(self.nextOffset());
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
(function menuMods() {
  var menu = document.getElementById('cchdo_menu');
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
      e.onfocus = function () {
        for (var i = 0; i < lis.length; i++) {
          add_class(lis[i], 'focus');
        }
      };
      e.onblur = function () {
        for (var i = 0; i < lis.length; i++) {
          remove_class(lis[i], 'focus');
        }
      };
    }
    function walkFor(root, tagname, callback) {
      for (var i = 0; i < root.children.length; i++) {
        walkFor(root.children[i], tagname, callback);
      }
      if (root.tagName == tagname) {
        callback(root);
      }
    }
    walkFor(menu, 'A', function (a) {
      addfocusblur(a, menu);
    });
  })();
  (function toggleableMenu() {
    var ul = menu.children[0];
    var expander = document.createElement('LI');
    var h1 = document.createElement('H1');
    var link = document.createElement('A');
    link.className = 'expander';
    link.href = 'javascript:void(0);';
    h1.appendChild(link);
    expander.appendChild(h1);
    ul.appendChild(expander);

    function open(p) {
      if (p) {
        remove_class(ul, 'open');
        link.innerHTML = 'open menu';
        link.title = 'Pin open';
      } else {
        add_class(ul, 'open');
        link.innerHTML = 'close menu';
        link.title = 'Unpin';
      }
    }

    var toggleClosed = true;

    var hoverThresh = 500,
        leaveThresh = 350;

    var hoverTime;
    menu.onmouseover = function () {
      hoverTime = setTimeout(function () {
        open(false);
      }, hoverThresh);
    };
    menu.onmouseout = function () {
      clearTimeout(hoverTime);
    };

    var leaveTime;
    ul.onmouseout = function () {
      leaveTime = setTimeout(function () {
        if (toggleClosed) {
          open(true);
        }
      }, leaveThresh);
    };
    ul.onmouseover = function () {
      clearTimeout(leaveTime);
    };

    function toggle() {
      toggleClosed = has_class(ul, 'open');
      clearTimeout(hoverTime);
      clearTimeout(leaveTime);
      open(toggleClosed);
      if (event.stopPropagation) {
        event.stopPropagation();
      }
      return false;
    }

    expander.onclick = toggle;
    open(true);
  })();
})();
(function imgmap() {
  // Adapted from http://home.comcast.net/~urbanjost/semaphore.html
  // Matthew Shen 2012

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

    if (this._width == cwidth && this._height == cheight) {
      return;
    }

    var ratio = cwidth / this._width;
    _map(function () {
      var area = this[0];
      var coords = this[1];
      var scaled = _map(function () { return Math.round(this * ratio); },
                        coords);
      area.coords = scaled.join(',');
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
    im.resize();
    ims.push(im);
  }
})();
(function mobileToggle() {
  var links = document.getElementsByTagName('link');
  var mobile_css = [];
  for (var i = 0; i < links.length; i++) {
    var link = links[i];
    if (links[i].className == 'mobile') {
      mobile_css.push(link);
      link.data_href = link.href;
    }
  }
  var link_mobile = document.getElementById('screensize-mobile');
  var link_full = document.getElementById('screensize-full');
  link_mobile.onclick = function () {
    for (var i = 0; i < mobile_css.length; i++) {
      var link = mobile_css[i];
      link.href = link.data_href;
      if (link.media == 'handheld') {
        link.media = 'all,handheld';
      }
    }
    if (window.sessionStorage) {
      window.sessionStorage.removeItem('pin_large_screen');
    }
    return false;
  };
  link_full.onclick = function () {
    for (var i = 0; i < mobile_css.length; i++) {
      var link = mobile_css[i];
      link.href = '';
      if (link.media == 'all,handheld') {
        link.media = 'handheld';
      }
    }
    if (window.sessionStorage) {
      window.sessionStorage.setItem('pin_large_screen', '1');
    }
    return false;
  };
  if (window.sessionStorage) {
    if (window.sessionStorage.getItem('pin_large_screen') == '1') {
      link_full.onclick();
    } else {
      link_mobile.onclick();
    }
  }
})();
