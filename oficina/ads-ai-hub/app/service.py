from app.adapters.meta import MetaAdapter
from app.adapters.tiktok import TikTokAdapter
from app.core.config import settings
from app.core.models import ActionRequest, ActionResult, Platform
from app.core.policy import evaluate_action
from app.finance import cockpit_state
from app.autonomy import model_policy

adapters = {Platform.META: MetaAdapter(), Platform.TIKTOK: TikTokAdapter()}

async def health_all():
    return {
        "service": "ads-ai-hub",
        "version": "0.3.0",
        "status": "ok",
        "environment": settings.environment,
        "dry_run": settings.dry_run,
        "platforms": [await a.health() for a in adapters.values()],
        "cockpit": cockpit_state(),
        "model_router": model_policy(),
    }

async def list_campaigns(platform: Platform):
    return await adapters[platform].list_campaigns()

async def execute(req: ActionRequest):
    decision = evaluate_action(req)
    if not decision.allowed:
        return {"decision": decision.model_dump(mode="json"), "result": None}
    upstream = await adapters[req.platform].execute(req)
    result = ActionResult(
        accepted=True,
        dry_run=settings.dry_run,
        platform=req.platform,
        action=req.action,
        object_id=req.object_id,
        upstream=upstream,
    )
    return {"decision": decision.model_dump(mode="json"), "result": result.model_dump(mode="json")}
