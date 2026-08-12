from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

class Platform(StrEnum):
    META = "meta"
    TIKTOK = "tiktok"

class ActionType(StrEnum):
    PAUSE_CAMPAIGN = "campaign.pause"
    ACTIVATE_CAMPAIGN = "campaign.activate"
    UPDATE_BUDGET = "budget.update"

class ActionRequest(BaseModel):
    platform: Platform
    action: ActionType
    object_id: str = Field(min_length=1)
    current_budget: float | None = Field(default=None, ge=0)
    new_budget: float | None = Field(default=None, ge=0)
    approval_token: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class ActionDecision(BaseModel):
    allowed: bool
    requires_approval: bool = False
    reason: str

class ActionResult(BaseModel):
    accepted: bool
    dry_run: bool
    platform: Platform
    action: ActionType
    object_id: str
    upstream: dict[str, Any] = Field(default_factory=dict)
