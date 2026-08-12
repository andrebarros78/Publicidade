package ads.authz
default allow := false
allow if { input.action != "budget.update" }
allow if { input.action == "budget.update"; input.current_budget > 0; ((input.new_budget-input.current_budget)/input.current_budget)*100 <= 20 }
allow if { input.approval_token != "" }
