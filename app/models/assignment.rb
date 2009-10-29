class Assignment < ActiveRecord::Base

   def before_update
      old_object = Assignment.find(self.id)
      change = false
      Assignment.column_names.each do |col_name|
         if col_name !~ /(history)|(manager)/ and old_object[:"#{col_name}"] != self[:"#{col_name}"]
            change = true
            old_val = old_object[:"#{col_name}"]
            new_val = self[:"#{col_name}"]
            now = Time.now
            t_now = now.strftime("%m/%d/%Y %I:%M")
            self.history << "#{t_now} #{col_name}: #{old_val} -> #{new_val}\n"
            self.changed = now.strftime("%Y-%m-%d")
            user = self.manager
         end
      end
      if change
         self.history << "Modified by #{user}\n\n "
      else
         self.manager = old_object.manager
      end
   end

   def before_create
      user = self.manager
      now = Time.now
      t_now = now.strftime("%m/%d/%Y %I:%M")
      self.history = "#{t_now} Created by #{user}\n"
      self.changed = now.strftime("%Y-%m-%d")
   end

   #def after_save
   #   record = AuditTrail.find(:first, :conditions => [" record_id = #{self.id} and time = #{self.changed}"])
   #   user = record[:user_id]
   #   self.history << "#{user}\n\n"
   #end

end
