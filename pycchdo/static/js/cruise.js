$(function () {
  // Make every box user resizable
  $('.boxed').each(function () {
    $(this).resizable({
      alsoResize: $(this).find('.box_content')});
  });

  var id_ac_cache = {};
  function nameIdToSource(list) {
    var source = [];
    $.each(list, function (i, x) {
      source.push({label: x.name, value: x.id});
    });
    return source;
  }
  function acSource(key, url, source_processor, callback) {
    var source = id_ac_cache[key];
    if (source) {
      callback(source);
    } else {
      $.get(url, function (xs) {
        source = source_processor(xs);
        id_ac_cache[key] = source;
        callback(source);
      });
    }
  }

  function autocompleteSource(callback) {
    var source = $(this).autocomplete('option', 'source');
    if ($.isFunction(source)) {
      source = id_ac_cache[key];
    }
    $.each(source, callback);
  }
  function findInAutocomplete(current) {
    var label = null;
    if (!current) {
      current = $(this).val();
    }
    autocompleteSource.call(this, function (i, v) {
      if (v.value == current) {
        label = v.label;
        return false;
      }
    });
    if (label === null) {
      if (current) {
        label = '?';
      } else {
        label = '';
      }
    }
    return label;
  }

  // Participant row autocomplete
  function addACToParticipantRow(row) {
    var role = $('.role input', row);
    role.autocomplete({
      minLength: 0,
      source: ['Chief Scientist', 'Participant'],
      change: function () {
        $(this).trigger('change');
      }
    });

    function addAC(input, preview) {
      input.autocomplete({
        minLength: 0,
        source: [],
        focus: function (event, ui) {
          preview.html(ui.item.label);
        },
        select: function (event, ui) {
          $(this).autocomplete('option', 'change').call(this);
        },
        change: function (event, ui) {
          var label = null;
          if (!ui || !ui.item) {
            label = findInAutocomplete.call(this);
          } else {
            label = ui.item.label;
          }

          preview.html(label);
          $(this).trigger('change');
        }
      });
    }

    $('span.preview', row).remove();

    var person = $('.person input', row);
    var personPreview = $('<span/>', {'class': 'preview'}).css({
      'vertical-align': 'middle',
      'font-size': '1.1em'
    }).insertAfter(person);
    addAC(person, personPreview);
    acSource('person', '/people.json', nameIdToSource, function (source) {
      person.autocomplete('option', 'source', source);
    });

    var institution = $('.institution input', row);
    var institutionPreview = $('<span/>', {'class': 'preview'}).css({
      'vertical-align': 'middle',
      'font-size': '1.1em'
    }).insertAfter(institution);
    addAC(institution, institutionPreview);
    acSource('institutions', '/institutions.json', nameIdToSource,
             function (source) {
      institution.autocomplete('option', 'source', source);
    });
  }
  $('.participant_row').each(function () {
    addACToParticipantRow($(this));
  });

  // Participant row editing
  // Insert a new row if the row being edited is the last row.
  function newParticipantRow(last_row) {
    var id = Number(last_row.attr('class').replace('participant_row', '').trim());
    var new_id = String(id + 1);
    id = String(id);
    var new_row = last_row.clone();
    new_row.attr('class', last_row.attr('class').replace(id, new_id));
    new_row.find('input').each(function () {
      $(this).val('').attr('name', $(this).attr('name').replace(id, new_id));
    });
    addACToParticipantRow(new_row);
    return new_row;
  }
  function participantRowIsEmpty(row) {
    var some = false;
    $('input', row).each(function () {
      if ($(this).val() != '') {
        some = true;
        return false;
      }
    });
    return !some;
  }
  $('.participant_row input').live('change', function () {
    var row = $(this).parents('tr');
    var last_row = $('.participant_row:last');

    if (participantRowIsEmpty(row)) {
      var nextRow = row.next();
      if (nextRow.is(last_row)) {
        last_row.remove();
        var prevRow = row.prev();
        while (participantRowIsEmpty(prevRow)) {
          row.remove();
          row = prevRow;
          prevRow = row.prev();
        }
      }
    } else {
      if (row.is(last_row)) {
        last_row.after(newParticipantRow(last_row));
      }
    }
  });

  (function () {
    function split(val) {
      return val.split(/,\s*/);
    }

    function extractLast(term) {
      return split(term).pop();
    }

    var key = '';

    var value = $('#edit_attr input[name=value]');
    var preview = null;
    var inputs = {
      text: value,
      dt: $('<input name="value" type="datetime" placeholder="date time">'),
      id: $(
        '<input name="value" type="text" placeholder="id">').css('width', '6em'),
      url: $('<input name="value" type="url" placeholder="link">'),
      idlist: $('<input name="value" type="text" placeholder="ids">')
    };
    var previews = {
      id: $('<span/>').css({
        'font-size': '1.1em',
        'margin-left': '0.5em',
        'vertical-align': 'middle'
      }),
      idlist: $('<span/>').css({
        'font-size': '1.1em',
        'vertical-align': 'middle'
      }),
    };

    var cruise = {};
    $.get(window.location + '.json', function (data) {
      cruise = data;
    });

    inputs.dt.datepicker({'dateFormat': 'yy-mm-dd'});
    function initInputDt() {
      var defaultDate = null;
      if (key == 'date_start') {
        if (cruise.date_start) {
          defaultDate = new Date(cruise.date_start);
        }
      } else if (key == 'date_end') {
        if (cruise.date_end) {
          defaultDate = new Date(cruise.date_end);
        }
      }
      if (defaultDate) {
        inputs.dt.datepicker('setDate', defaultDate);
      }
    }

    inputs.id.autocomplete({
      minLength: 0,
      source: [],
      focus: function (event, ui) {
        previews.id.html(ui.item.label);
      },
      select: function (event, ui) {
        $(this).autocomplete('option', 'change').call(this);
      },
      change: function (event, ui) {
        var label = null;
        if (!ui || !ui.item) {
          label = findInAutocomplete.call(this);
        } else {
          label = ui.item.label;
        }
        previews.id.html(label);
      }
    });
    function set_id_ac(source) {
      inputs.id.autocomplete('option', 'source', source);

      if (cruise) {
        var id = null;
        if (key == 'country') {
          if (cruise.country) {
            id = cruise.country.id;
          }
        } else if (key == 'ship') {
          if (cruise.ship) {
            id = cruise.ship.id;
          }
        }
        inputs.id.val(id);
        inputs.id.autocomplete('option', 'change').call(inputs.id);
      }
    }
    function initInputId() {
      if (key == 'country') {
        acSource('country', '/countries.json', nameIdToSource, set_id_ac);
      } else if (key == 'ship') {
        acSource('ship', '/ships.json', nameIdToSource, set_id_ac);
      } else {
        set_id_ac(source);
      }
    }

    inputs.idlist
    // don't navigate away from the field on tab when selecting an item
    .bind('keydown', function (event) {
      if (event.keyCode === $.ui.keyCode.TAB &&
          $(this).data('autocomplete').menu.active) {
        event.preventDefault();
      }
    })
    .focus(function () {
      var values = split($(this).val());
      if ($(this).val()) {
        values.push('');
      }
      $(this).val(values.join(','));
    })
    .blur(function () {
      var values = split($(this).val());
      values.pop();
      $(this).val(values.join(','));
    })
    .autocomplete({
      minLength: 0,
      source: function (request, response) {
        try {
          response($.ui.autocomplete.filter(
            id_ac_cache[key], extractLast(request.term)
          ));
        } catch (e) {
          response(id_ac_cache[key]);
        }
      },
      focus: function (event, ui) {
        // prevent value insert on focus
        return false;
      },
      select: function (event, ui) {
        var self = $(this);
        var terms = split(self.val());
        terms.pop();
        terms.push(ui.item.value);
        // placeholder to get trailing separator
        terms.push('');
        self.val(terms.join(','));
        self.autocomplete('option', 'change').call(self);
        return false;
      },
      change: function (event, ui) {
        var self = this;
        var labels = [];
        $.each(split($(this).val()), function (i, e) {
          if (e) {
            labels.push(findInAutocomplete.call(self, e));
          }
        });
        previews.idlist.html(labels.join(', '));
      }
    });
    function set_idlist_ac(source) {
      id_ac_cache[key] = source;

      if (cruise) {
        var ids = [];
        if (key == 'collections') {
          if (cruise.collections) {
            ids = $.map(cruise.collections, function (c, i) {
              return c.id;
            });
          }
        } else if (key == 'institutions') {
          if (cruise.institutions) {
            ids = $.map(cruise.institutions, function (i, j) {
              return i.id;
            });
          }
        }
        inputs.idlist.val(ids.join(','));
      }
      inputs.idlist.autocomplete('option', 'change').call(inputs.idlist);
    }
    function initInputIdList() {
      if (key == 'collections') {
        acSource(key, '/collections.json', function (xs) {
          var source = [];
          $.each(xs, function (i, c) {
            $.each(c.names, function (j, name) {
              source.push({label: name, value: c.id});
            });
          });
          return source;
        }, set_idlist_ac);
      } else if (key == 'institutions') {
        acSource('institutions', '/institutions.json',
                nameIdToSource, set_idlist_ac);
      } else {
        set_idlist_ac(source);
      }
    }

    $('#edit_attr select').change(function () {
      var option = $('option:selected', this);
      var optgroup = option.parent('optgroup');
      var type = optgroup.attr('label');
      key = option.val();

      if (type == 'Datetime') {
        type = 'dt';
        initInputDt();
      } else if (type.slice(0, 2) == 'ID') {
        if (type == 'ID List') {
          type = 'idlist';
          initInputIdList();
        } else {
          type = 'id';
          initInputId();
        }
      } else if (key == 'link') {
        type = 'url';
      } else {
        type = 'text';
      }

      var newValue = inputs[type];
      var newPreview = previews[type];
      if (newValue !== value) {
        newValue.insertAfter(value);
        value.detach();
        value = newValue;
        if (preview) {
          preview.detach();
          preview = null;
        }
        if (newPreview && newPreview !== preview) {
          newPreview.insertAfter(value);
          preview = newPreview;
        }
      }
    }).change();
  })();

  (function plotCruiseTrack() {
    if (window.CCHDO.cruise.track) {
      var mapdiv = $('#plot_map').css({height: 300, width: '78.5%'});
      var coordstr = $('#plot textarea').css({height: mapdiv.outerHeight(), width: '19.5%'});

      var opts = {
        zoom: 2,
        center: new google.maps.LatLng(0, 0),
        scrollwheel: false,
        streetViewControl: false,
        mapTypeId: google.maps.MapTypeId.TERRAIN
      };
      var map = new google.maps.Map(mapdiv[0], opts);
      new Graticule(map);

      var track = CCHDO.cruise.track;
      var path = $.map(track.coordinates, function (c) {
        return new google.maps.LatLng(c[1], c[0]);
      });
      var bounds = new google.maps.LatLngBounds();
      $.each(path, function (i, p) {
        bounds.extend(p);
      });
      map.fitBounds(bounds);

      var track_line = new google.maps.Polyline({
        //editable: true,
        map: map,
        path: path,
        strokeColor: '#FF4444'
      });

      function pathFromString(s) {
        var coords = s.split('\n');
        return $.map(coords, function (coord) {
          var lnglat = coord.split(', '); 
          return new google.maps.LatLng(lnglat[1], lnglat[0]);
        });
      }

      function stringFromPath(p) {
        return $.map(p.getArray(), function (c) {
          return c.lng().toFixed(4) + ', ' + c.lat().toFixed(4);
        }).join('\n');
      }

      function updateStringFromPolyline() {
        coordstr.val(stringFromPath(track_line.getPath()));
      }

      var track_line_path = track_line.getPath();
      google.maps.event.addListener(
        track_line_path, 'insert_at', updateStringFromPolyline);
      google.maps.event.addListener(
        track_line_path, 'remove_at', updateStringFromPolyline);
      google.maps.event.addListener(
        track_line_path, 'set_at', updateStringFromPolyline);

      coordstr.change(function () {
        track_line.setPath(pathFromString($(this).val()));
      });
    }
  })();
});
