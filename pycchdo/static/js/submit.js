$(document).ready(function () {
  var files = $('#dfiles');
  var remove_button = $('<input type="button" title="Remove" value="Remove">');
  var fsel= files.find('p :file');
  var file_list = $('<ol></ol>').appendTo(files);

  function renumber() {
    file_list.find(':file').each(function (i, x) {
      $(this).attr('name', 'files[' + i + ']');
    });
  }

  function remove() {
    $(this).parent().hide('fast', function () {
      $(this).remove();
      renumber();
    });
  }

  function noop(e) {
    e.preventDefault();
    return false;
  }

  files.on('change', 'p :file', function () {
    if ($(this).val() == null || $(this).val() == '') {
      return;
    }

    var f = $(this);
    var p = f.parent();
    var c = f.clone();
    f.click(noop);
    file_list.prepend(
      $('<li></li>').append(f).
        append(remove_button.clone().click(remove)).
        hide().show('fast'));
    p.append(c);
    renumber();
  });
});
