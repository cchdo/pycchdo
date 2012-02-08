$('.boxed').each(function () {
  $(this).resizable({
    alsoResize: $(this).find('.box_content')});
});

$('.participant_row input').live('change', function () {
  var row = $(this).parents('tr');
  if (row[0] != $('.participant_row:last')[0]) {
    return;
  }
  var id = Number(row.attr('class').replace('participant_row', '').trim());
  var new_id = String(id + 1);
  var new_row = row.clone();
  new_row.attr('class', row.attr('class').replace(String(id), new_id));
  new_row.find('input').each(function () {
    $(this).attr('name', $(this).attr('name').replace(String(id), new_id));
    $(this).val('');
  });
  $(row).after(new_row);
});
