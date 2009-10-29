module SearchHelper

  def checkbox_for(id, name, file)
    if file
      return "<input name=\"checkbox_#{id}\" value=\"#{file.FileName}\" type='checkbox' /><a href=\"http://cchdo.ucsd.edu#{file.FileName}\">#{name}</a><br /><p class='date'>#{file.LastModified.strftime("%a %F %X%z")}</p>"
    else
      return ''
    end
  end
end
