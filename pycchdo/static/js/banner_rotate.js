// Rotate banner
(function () {
  if (window.localStorage) {
    var clickcount = 0;
    var clickthresh = 3;
    var clicklast = new Date();
    var picdom = document.getElementById('picture');
    var ok = document.createElement('DIV');
    ok.innerHTML = '';
    ok.style.color = 'red';
    ok.style.font = '3em monospace';
    ok.style.position = 'relative';
    ok.style.textShadow = 'white 0 0 0.5em';
    ok.style.zIndex = 101;
    picdom.appendChild(ok);
    picdom.addEventListener('click', function () {
      var now = new Date();
      if (now - clicklast < 300) {
      console.log('+');
        clickcount++;
      } else {
        clickcount = 0;
      }
      clicklast = now;
      if (clickcount >= clickthresh) {
        var rot = window.localStorage.getItem('bannerOff') !== null;
        if (rot) {
          window.localStorage.removeItem('bannerOff');
        } else {
          window.localStorage.setItem('bannerOff', '1');
        }
        ok.innerHTML = '<p>rotation ' + (rot ? 'on' : 'off') + '; please reload the page</p>';
        clickcount = 0;
      }
    }, false);
    if (window.localStorage.getItem('bannerOff')) {
      return;
    }
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
    (function () {
      if (timer) {
        clearTimeout(timer);
        self.animate(self.nextOffset());
      }
      timer = setTimeout(arguments.callee, self.delay);
    })();
  };

  var bannerOffset = 0;
  if (window.sessionStorage) {
    bannerOffset = window.sessionStorage.getItem('bannerOffset');
  }
  var a = [document.getElementById('bannerA'), document.getElementById('bannerB')];
  var b = [document.getElementById('bannerC'), document.getElementById('bannerD')];
  if (a[0] && a[1]) {
    new rotator(a[0], a[1], 14, [100, 99], null, null, bannerOffset).start();
  }
  if (b[0] && b[1]) {
    new rotator(b[0], b[1], 14, [98, 97], null, null, bannerOffset).start();
  }
})();

/** XXX quick links for staff pages */
(function () {
  var div = document.createElement('DIV');
  var div_s = div.style;
  div_s.position = 'absolute';
  div_s.left = 0;
  div_s.bottom = 0;
  div_s.opacity = 0.1;
  div_s.fontSize = '1.5em';
  div_s['-webkit-transition'] = 'opacity .3s ease';

  function link(href, text) {
    var link = document.createElement('A');
    link.href = href;
    link.appendChild(document.createTextNode(text));
    link.style.textDecoration = 'none';
    return link;
  }

  div.appendChild(link('/staff', String.fromCharCode(9731)));
  div.appendChild(link('/staff/submissions', String.fromCharCode(9732)));
  div.appendChild(link('/staff/moderation', String.fromCharCode(9733)));

  document.body.appendChild(div);

  div.addEventListener('mouseover', function () {
    div_s.opacity = 1;
  }, false);

  div.addEventListener('mouseout', function () {
    div_s.opacity = 0.1;
  }, false);
})();
