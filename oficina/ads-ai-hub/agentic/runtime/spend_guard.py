from dataclasses import dataclass

@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    reason: str
    projected_monthly_spend: float
    ceiling: float

def check_spend(*, spent: float, proposed_increment: float, ceiling: float) -> SpendDecision:
    if min(spent, proposed_increment, ceiling) < 0:
        return SpendDecision(False, 'negative_value', spent + proposed_increment, ceiling)
    projected = spent + proposed_increment
    if projected > ceiling + 1e-9:
        return SpendDecision(False, 'owner_ceiling_exceeded', projected, ceiling)
    return SpendDecision(True, 'within_owner_ceiling', projected, ceiling)
