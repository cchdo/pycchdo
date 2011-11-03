(function ($) {
  var popupsblocked = false;
  var blockingdialog_lock = false;

  var autopopid_next = 0;
  function autopopid() {
    autopopid_next += 1;
    return autopopid_next;
  }

  function joinOpts(opts) {
    var a = [];
    for (var k in opts) {
      a.push(k + '=' + opts[k]);
    }
    return a.join(',');
  }

  function getWindowNWSE(win) {
    if (!win) {
      win = window;
    }
    var top = win.screenY || win.screenTop;
    var left = win.screenX || win.screenLeft;
    // TODO Chrome counts the location bar and tabs into the window height
    return {
      x0: top, y0: left,
      x1: left + $(win).width(),
      y1: top + $(win).height()
    };
  }

  $.fn.autoPopDialog = function (opts) {
    if (!opts) {
      opts = {};
    }
    var popout_callback = function () {};
    var popin_callback = function () {};
    if (opts.popout_callback) {
      popout_callback = opts.popout_callback;
      delete opts.popout_callback;
    }
    if (opts.popin_callback) {
      popin_callback = opts.popin_callback;
      delete opts.popin_callback;
    }

    opts.dragStart = function (event, ui) {
      watchingDrag = true;
    };
    opts.drag = function (event, ui) {
      if (!watchingDrag) {
        return;
      }
      if (lastOffset != null) {
        if (lastOffset.left == ui.offset.left &&
            lastOffset.top == ui.offset.top) {
          var widget = dialog.dialog('widget');
          var maxX = $(window).width() - widget.width();
          var maxY = $(window).height() - widget.height();

          var direction = '';
          if (lastOffset.left <= 0) {
            direction = 'left';
          } else if (lastOffset.top <= 0) {
            direction = 'up';
          } else if (lastOffset.left >= maxX) {
            direction = 'right';
          } else if (lastOffset.top >= maxY) {
            direction = 'down';
          }
          popOut(direction, event);
        }
      }
      lastOffset = ui.offset;
    };
    opts.dragStop = function (event, ui) {
      watchingDrag = false;
    };

    var dialog = this.dialog(opts);

    // Detect dragging a dialog window out of window
    var watchingDrag = false;
    var lastOffset = null;

    var popped = false;
    var poppedchildren = null;

    var popcorn = null;
    var popcornid = 'autopop_' + autopopid();

    function startCheckingForPopin() {
      function pointInside(pts, x, y) {
        return pts.x0 <= x && x <= pts.x1 && pts.y0 <= y && y <= pts.y1;
      }
      (function () {
        if (!popcorn || !popped) {
          return;
        }
        var winpts = getWindowNWSE();
        var poppts = getWindowNWSE(popcorn);
        var popX = poppts.x0;
        var popY = poppts.y0;
        var popXX = poppts.x1;
        var popYY = poppts.y1;

        // Check if all of pop's points are inside
        var nwin = pointInside(winpts, popX, popY);
        var nein = pointInside(winpts, popXX, popY);
        var sein = pointInside(winpts, popXX, popYY);
        var swin = pointInside(winpts, popX, popYY);

        if (nwin && nein && sein && swin) {
          popIn(popX - winpts.x0, popY - winpts.y0);
        }

        setTimeout(arguments.callee, 100);
      })();
    }

    function popOut(direction, event) {
      if (popped) {
        return;
      }
      popped = true;

      var winpts = getWindowNWSE();

      var widget = dialog.dialog('widget').position();
      var x = event.screenX;
      var y = event.screenY;

      if (direction == 'left') {
        x = winpts.x0;
      } else if (direction == 'up') {
      } else if (direction == 'right') {
      } else if (direction == 'down') {
        x = winpts.x0 + widget.left;
      }

      popcorn = window.open('', popcornid, joinOpts({
        toolbar: 0,
        location: 0,
        width: dialog.width(),
        height: dialog.height(),
        top: y,
        left: x
      }));

      if (!popcorn) {
        // Safari blocked popup
        return;
      }

      // Check for Chrome blocking
      setTimeout(function () {
        if (popcorn.innerHeight == 0) {
          popupsblocked = true;
          popIn(null, null, true);

          if (!blockingdialog_lock) {
            blockingdialog_lock = true;
            $("<div><p>The table was prevented from popping into a separate window.</p>" + 
              "<p>It's likely that popups are being blocked.</p></div>").dialog({
              modal: true,
              title: "I wish I could do that for you!",
              buttons: {"Ok": function () {
                $(this).dialog('close');
                blockingdialog_lock = false;
              }}
            });
          }
        } else {
          startCheckingForPopin();
        }
      }, 500);

      dialog.dialog('widget').hide();

      var doc = popcorn.document;

      $(doc).ready(function () {
        // XXX HACK Firefox prep document. I know it's weird.
        doc.write();
        doc.close();

        // XXX Bug in JQuery. Chrome $().unload() does not bind correctly but onunload does.
        popcorn.onunload = popIn;

        doc.title = dialog.dialog('option', 'title');

        // Transfer all script and style resources over to the child too. This
        // is kludgy but it works.
        var loc = window.location;
        var dochead = $('head', doc);
        dochead
          .append($('<base href="' + loc.protocol + '//' + loc.host + '" />', doc))
          .append($('<link rel="icon" type="image/x-icon" href="favicon.ico" />', doc));
        $('link').each(function () {
          if (this.rel == 'stylesheet') {
            $(['<link href="', this.href, '" rel="stylesheet" type="text/css" ',
               'media="screen" />'].join(''), doc)
              .appendTo(dochead);
          }
        });

        var docbody = $('body', doc);
        poppedchildren = dialog.children().detach().appendTo(docbody);

        popout_callback.call(docbody);
      });
    }

    function popIn(x, y, show) {
      if (!popped) {
        return;
      }
      popped = false;

      var unpopable = null;
      if (popcorn && popcorn.document && popcorn.document.body) {
        unpopable = $(popcorn.document.body).children();
      } else {
        unpopable = poppedchildren;
      }
      unpopable.detach().appendTo(dialog);

      dialog.dialog('widget').show();
      if (typeof x == "number" && typeof y == "number") {
        dialog.dialog('option', 'position', [y, x]);
      } else {
        if (!show) {
          // Since this popin is from the window closing, also close the dialog.
          // This is unless told not to (blocked popup popin).
          dialog.dialog('close');
        }
      }

      if (!popcorn.closed) {
        popcorn.close();
      }

      popin_callback.call();
    }
  };
})(jQuery);
