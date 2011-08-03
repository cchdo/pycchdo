// Rotate banner
new (function () {
  var styleA = null,
      styleB = null,
      isA = true,
      delay = 1000 * 6,
      animateTime = 1000 * 3,
      zs = [99, 100];

  var offset = 0,
      height = 125,
      minoffset = -height * 1;

  function _(domobjA, domobjB, num_banners) {
    if (delay <= animateTime) {
      console.log("Don't do that!");
      return;
    }
    styleA = domobjA.style;
    styleB = domobjB.style;
    minoffset = -height * num_banners;
    setOpacity(0, styleB);
    start();

    var bgSize = ['100% ', num_banners * 100, '%'].join('');
    styleA.backgroundSize = bgSize;
    styleB.backgroundSize = bgSize;
  };  

  function nextOffset() {
    return offset - height;
  }

  function setOffset(s, x) {
    s.backgroundPosition = ['0 ', x, 'px'].join('');
  }

  function setOpacity(x, s) {
    s.opacity = x;
    s.filter = ['alpha(opacity=', x * 100, ')'].join('');
  }

  function o(x, s) {
    var shift = (s == styleA) ? (isA ? 0 : 1) : (isA ? 1 : 0);
    return Math.abs(Math.cos(Math.PI * (x + shift) / 2))
  }

  function animate(next) {
    var startTime = new Date();

    /* Bit of a race condition when animation starts before one finishes. Not
     usually a problem. */

    if (isA) {
      setOffset(styleB, next);
    } else {
      setOffset(styleA, next);
    }

    (function () {
      var elapsed = new Date() - startTime,
          ratio = Math.min(elapsed / animateTime, 1);

      setOpacity(o(ratio, styleA), styleA);
      setOpacity(o(ratio, styleB), styleB);

      if (elapsed < animateTime) {
        setTimeout(arguments.callee, animateTime / 50);
      } else {
        if (isA) {
          isA = false;
          styleB.zIndex = zs[1];
          styleA.zIndex = zs[0];
        } else {
          isA = true;
          styleA.zIndex = zs[1];
          styleB.zIndex = zs[0];
        }
        offset = next;
        if (offset <= minoffset) {
          offset = 0;
          next = -height;
        }
      }
    })();
  }

  function start() {
    var timer = null;
    (function () {
      if (timer) {
        clearTimeout(timer);
        animate(nextOffset());
      }
      timer = setTimeout(arguments.callee, delay);
    })();
  }

  return _;
})()(document.getElementById('bannerA'), document.getElementById('bannerB'), 14);
