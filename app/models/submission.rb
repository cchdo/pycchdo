class Submission < ActiveRecord::Base
   validates_format_of :name,
   :with => /^\w[\w\,\s\.]+$/,
   :message => ""

   validates_format_of :institute,
   :with => /^[\w\@\,\:\-\/_\s\.]+$/,
   :message => ""

   validates_format_of :Country,
   :with => /^\w+$/,
   :message => ""

   validates_format_of :public,
   :with => /^\w[a-zA-Z\s-]+$/,
   :message => ""


   validates_format_of :email,
   :with => /^\w[\w\-\.]+\@[\w\-\.]+$/,
   :message => ""

   validates_format_of :file,
   :with => /^[\w\_\.\/\-]+$/,
   :message => "Bad file name"

   #validates_format_of :file_name,
   #                     :with => /^[\w\_\.\/]+$/,
   #                     :message => ""

   #validates_format_of :file,
   #                     :with => /^\/Library\/WebServer\/Documents\/cchdo\/public\/submissions\/[\w_]+\/\w+\.\w+$/,
   #                     :message => ""
end
