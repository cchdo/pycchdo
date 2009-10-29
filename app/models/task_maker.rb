class TaskMaker < ActionMailer::Base

   def receive(email)
      #		Property Name		DB name
      properties = {	"expocode"	 	=> :ExpoCode,
         "project" 		=> :project,
         "current status" 	=> :current_status,
         "assign to" 		=> :cchdo_contact,
         "data contact" 		=> :data_contact,
         "action" 		=> :action,
         "parameter" 		=> :parameter,
         "notes" 		=> :notes,
         "priority" 		=> :priority,
         "deadline" 		=> :deadline,
         "manager"		=> :manager,
         #		"last changed"		=> :changed, # don't touch. let Assignment model do this
      "complete"		=> :complete}

      assignment = {}

      #properties.each_value do |prop|
      #	assignment[prop] = ""
      #end

      # Yield assignment hash with each property's db name mapped to the payload.
      email.body.each do |line|
         possProp, payload = line.split(":")
         possProp.downcase! # For consistency
         if payload
            payload.strip!
         end
         properties.keys.each do |property|
            if possProp.include?(property)
               assignment[properties[property]] = payload
               break
            end
         end
      end
      #		assignment[properties["manager"]] = email.from

      # Actually make the task and save it
      task = Assignment.new(assignment)
      task.save
   end
end
