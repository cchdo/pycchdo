class FileSubmitted < ActionMailer::Base

   def confirm(submission)
      @subject    =  "File submitted by #{submission.name}"
      @body['submission']       = submission
      @recipients = submission.email,'fieldsjustin@gmail.com'#,'cchdo@googlegroups.com'
      @from       = ''
      @sent_on    = Time.now
      @headers    = {}
   end
end
