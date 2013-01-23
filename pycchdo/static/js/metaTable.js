function metaTable() {
  var table = $(this);

  // Hide all the body rows
  table.find('> tbody > tr.body, > tr.body').hide();

  function attachExpanderArrow(expander, callback, title_expand, title_collapse) {
    var button = $('<a href="javascript:void(0);" title="' + title_expand + '"></a>');
    button.click(function() {
      if (button.attr('title') == title_expand) {
        button.attr('title', title_collapse);
      } else {
        button.attr('title', title_expand);
      }
    });
    button.click(callback);
    expander.append(button);
    return expander;
  }

  // When the header row is double clicked, toggle all rows
  var header = table.find('.header');
  header.dblclick(toggleAll);

  var batchOpen = false;
  function toggleAll() {
    var open = !header.data('open');
    header.data('open', open);
    if (open) {
      header.addClass('open');
    } else {
      header.removeClass('open');
    }

    batchOpen = true;
    table.find('> tbody > tr.meta, > tr.meta').each(function () {
      var row = $(this);
      if (row.data('open') != open) {
        row.click();
      }
    });
    batchOpen = false;
    return false;
  }

  var header_expander = $('<th class="expander"></th>');
  attachExpanderArrow(header_expander, toggleAll, 'Expand all', 'Collapse all');
  header.prepend(header_expander);

  // Prepend expander cells for each non-meta row
  table.find('> tbody > tr, > tr').each(function () {
    var prepend = '';
    var row = $(this);
    if (!row.hasClass('header')) {
      // Prepend in empty cell for all non-meta rows to keep alignment
      if (!row.hasClass('meta')) {
        prepend = $('<td class="expander"></td>');
      }
    }
    row.prepend(prepend);
  });
  var re_class = new RegExp('(mb-link\\w+)');
  table.find('> tbody > tr.meta, > tr.meta').each(function () {
    var row = $(this);
    var rowClass = re_class.exec(row.attr('class'));
    var body = table.find('.body.' + rowClass);

    var expander = $('<td class="expander"></td>');
    if (body.length > 0) {
      attachExpanderArrow(expander, react, 'Expand', 'Collapse').css({cursor: 'pointer'});
      row.click(function (event) {
        var tagname = event.target.tagName;
        if (tagname == 'TR' || tagname == 'TH' || tagname == 'TD') {
          react();
        }
      });
    }
    $(this).prepend(expander);

    function open() {
      row.addClass('open');
      var speed = 'fast';
      if (batchOpen) {
        speed = null;
      }
      body.addClass('open').show(speed);
    }
    function close() {
      row.removeClass('open');
      var speed = 'fast';
      if (batchOpen) {
        speed = null;
      }
      body.removeClass('open').hide(speed);
    }

    function check_focus_close() {
      setTimeout(close, 10);
    }

    function react() {
      row.data('open', !row.data('open'));
      if (row.data('open')) {
        open();
      } else {
        close();
      }
      return false;
    }

    // Make sure tabbing through focus elements will keep the row open
    var exa = row.find('.expander a');
    var focusable = row.find(':input')
      .add(body.find(':input'))
      .add(row.find('a'))
      .add(body.find('a'));

    if (focusable.length > 0) {
      var exa_focus = false;
      var input_focus = false;
      var opened = false;
      function react_focus() {
        setTimeout(function () {
          // Don't close while focus is being passed inside the same form.
          // Also don't close if focus has simply disappeared
          if (exa_focus || input_focus || $('*:focus').length == 0) {
            if (!opened) {
              open();
              opened = true;
            }
          } else {
            close();
            opened = false;
          }
        }, 0);
      }
      exa.focus(function () { exa_focus = true; react_focus(); });
      exa.blur(function () { exa_focus = false; react_focus(); });
      focusable.focus(function () { input_focus = true; react_focus(); });
      focusable.blur(function () { input_focus = false; react_focus(); });
      row.find(':input').click(function () { return false; });
    } else {
      exa.focus(open);
      exa.blur(close);
    }
  });

  if (table.hasClass('pre-expand')) {
    table.find('.header .expander a').click();
  }
}
$('table.has-meta-bodies').each(metaTable);
