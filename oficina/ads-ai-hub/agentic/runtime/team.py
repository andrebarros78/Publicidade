from dataclasses import dataclass
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class AgentPost:
    id: str
    title: str
    reports_to: str
    primary: str
    autonomy: str
    secondary: str | None = None

def load_registry():
    return json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))

def posts():
    return [AgentPost(**a) for a in load_registry()["agents"]]

def owner_controls():
    return {
        "owner_defines": ["monthly_spend_ceiling", "currency", "hard_business_constraints"],
        "system_owns": ["strategy","channel_mix","campaign_structure","audiences","creatives","experiments","budget_distribution","optimization","pause_scale_decisions","measurement","reporting"],
        "never_autonomous": ["increase_owner_spend_ceiling","change_payment_method","change_account_ownership","irreversible_asset_deletion"]
    }
