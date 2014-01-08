$(function() {
  function submissionsToolsChange() {
      window.location.href = window.location.origin + window.location.pathname + '?' +
        $.param({
          ltype: $('#submissions .tools [name=ltype]:radio:checked').val(),
          query: $('#submissions .tools #query').val(),
          sort: $('#submissions .tools [name=sort]:radio:checked').val()
        });
      return false;
  }
  $('#submissions .tools').submit(submissionsToolsChange);
  $('#submissions .tools :radio').change(submissionsToolsChange);
});
