from .config import settings
from .models import ActionDecision, ActionRequest, ActionType

def evaluate_action(req: ActionRequest) -> ActionDecision:
    if req.action != ActionType.UPDATE_BUDGET:
        return ActionDecision(allowed=True, reason="policy_allowed")
    if req.current_budget is None or req.new_budget is None:
        return ActionDecision(allowed=False, reason="budget_current_and_new_required")
    if req.current_budget == 0 and req.new_budget > 0 and not req.approval_token:
        return ActionDecision(allowed=False, requires_approval=True, reason="budget_from_zero_requires_approval")
    if req.current_budget > 0:
        increase = ((req.new_budget - req.current_budget) / req.current_budget) * 100
        if increase > settings.max_budget_increase_pct and not req.approval_token:
            return ActionDecision(allowed=False, requires_approval=True, reason="budget_increase_above_autonomous_limit")
    return ActionDecision(allowed=True, reason="policy_allowed")
