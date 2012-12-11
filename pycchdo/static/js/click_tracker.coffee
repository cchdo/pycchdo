$ ->
  $(document).click((event)->
    if event.target.nodeName == 'A'
      classes = $(event.target).attr("class")
      expocode = $(event.target).parent().attr('expocode') || undefined
      fileType = $(event.target).parent().parent().parent().attr('class') || undefined
      string = '{"expocode":"'+ expocode+'", "file_type":"'+ fileType+'"}'
      if expocode
        $.ajax
          url: 'http://localhost:5000/'
          type: 'POST'
          dataType: 'json'
          crossDomain: true
          data: string
          success: (response)->
          error: ->
          timeout: 500000
  )
