function PanedMap(dom, map) {
  this._on = false;
  this._open = false;

  this._root = dom;
  this._map = map;

  this._content = document.createElement('DIV');
  this._content.className = 'pane-content unselectable';
  this._root.appendChild(this._content);

  $(this._content).disableSelection();

  this._handle = document.createElement('DIV');
  this._handle.className = 'pane-handle unselectable clickable right';
  this._root.insertBefore(this._handle, this._root.firstChild);

  var self = this;
  $(this._handle).css('visibility', 'hidden').click(function () {
    self._open = !self._open;
    self.redraw();
  });

  var paneWidth;
  function checkPaneScrolling() {
    var newPaneWidth = self._paneWidth();
    if (newPaneWidth != paneWidth) {
      self.redraw();
    }
    paneWidth = newPaneWidth;
  }

  $(this._content).scroll(checkPaneScrolling);
}

PanedMap.prototype._paneWidth = function () {
  var contentChild = $(this._content).children()[0];
  var paneWidth = $(contentChild).outerWidth();

  if ($(contentChild).height() > $(this._content).height()) {
    // Account for scrollbar
    paneWidth += 15;
  }
  return paneWidth;
};

PanedMap.prototype.redraw = function () {
  var rootHeight = $(this._root).outerHeight();
  var rootWidth = $(this._root).outerWidth();
  var paneWidth = this._paneWidth();
  var mapWidth = rootWidth - paneWidth;

  var self = this;

  function resizedMap() {
    google.maps.event.trigger(self._map, 'resize');
  }

  function closePane() {
    $(self._content).animate({width: 0}, function () {
      $(this).css('visibility', 'hidden')
    });
    $(self._map.getDiv()).animate({'left': 0, width: rootWidth}, resizedMap);
    $(self._handle).animate({left: 0}).removeClass('left').addClass('right');
  }

  $(self._map.getDiv()).height(rootHeight);

  if (this._on) {
    $(this._handle).css({top: $(this._handle).height() / 4, visibility: 'visible'});

    if (this._open) {
      $(this._content).css('visibility', 'visible').animate({width: paneWidth});
      $(this._map.getDiv()).animate({'left': paneWidth, width: mapWidth}, resizedMap);
      $(this._handle).animate({left: paneWidth}).removeClass('right').addClass('left');
    } else {
      closePane();
    }
  } else {
    closePane();
    $(this._handle).css('visibility', 'hidden');
  }
};

PanedMap.prototype.setPaneContent = function (dom) {
  var previous = this._content.firstChild;
  if (previous) {
    this._content.removeChild(previous);
  }
  this._content.appendChild(dom);
  return previous;
};

PanedMap.prototype.setOn = function (on) {
  this._on = on;
  this.redraw();
  return this;
};

PanedMap.prototype.setOpen = function (open) {
  this._open = open;
  this.redraw();
  return this;
};

