(function() {
  $(function() {
    return $(document).click(function(event) {
      var classes, expocode, fileType, string;
      if (event.target.nodeName === 'A') {
        classes = $(event.target).attr("class");
        expocode = $(event.target).parent().attr('expocode') || void 0;
        fileType = $(event.target).parent().parent().parent().attr('class') || void 0;
        string = '{"expocode":"' + expocode + '", "file_type":"' + fileType + '"}';
        if (expocode) {
          return $.ajax({
            url: 'http://localhost:5000/',
            type: 'POST',
            dataType: 'json',
            crossDomain: true,
            data: string,
            success: function(response) {},
            error: function() {},
            timeout: 500000
          });
        }
      }
    });
  });
}).call(this);
