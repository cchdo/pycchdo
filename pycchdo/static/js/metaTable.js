function metaTable(table) {
  table.find('.header').dblclick(function () {
    var open = !$(this).data('open');
    $(this).data('open', open);
    table.find('> tbody > tr.meta, > tr.meta').each(function () {
      var row = $(this);
      if (row.data('open') != open) {
        row.click();
      }
    });
  });
  table.find('> tbody > tr.body, > tr.body').hide();
  table.find('> tbody > tr, > tr').each(function () {
    var prepend = '';
    if ($(this).hasClass('header')) {
      prepend = $('<th class="expander"></th>');
    } else {
      if (!$(this).hasClass('meta')) {
        prepend = $('<td class="expander"></td>');
      }
    }
    $(this).prepend(prepend);
  });
  var re_class = new RegExp('(mb-link\\w+)');
  table.find('> tbody > tr.meta, > tr.meta').each(function () {
    var row = $(this);
    var rowClass = re_class.exec(row.attr('class'));
    var body = table.find('.body.' + rowClass);

    if (body.length > 0) {
        $(this).prepend($('<td class="expander"></td>').append(
          $('<a href=""><div></div></a>')
            .click(function () { react(); return false; }))
          .css({cursor: 'pointer'}));
      row.click(react);
    } else {
      $(this).prepend($('<td class="expander"></td>'));
    }

    function open() {
      row.addClass('open');
      body.addClass('open').show('fast');
    }
    function close() {
      row.removeClass('open');
      body.removeClass('open').hide('fast');
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
    }

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
    if (table.hasClass('pre-expand')) {
      exa.click();
    }
  });
}
$('table.has-meta-bodies').each(function () { metaTable($(this)); });
