class TaskTracker < ActionController::Caching::Sweeper
   observe Assignment
   def after_update(record)
      log(record,"Update")
   end

   def after_create(record)
      log(record,"Create")
   end

   def after_destroy(record)
      log(record,"Destroy")
   end

   def log(record,event,user = controller.session[:user] )
      AuditTrail.create(:record_id =>record.id, :record_type => record.type.name, :event => event, :user_id => user, :time => record.changed)
   end
end
