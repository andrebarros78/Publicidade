import httpx
from app.adapters.base import AdsAdapter
from app.core.config import settings
from app.core.models import ActionRequest, ActionType

class MetaAdapter(AdsAdapter):
    @property
    def configured(self) -> bool:
        return bool(settings.meta_token and settings.meta_account_id)

    async def health(self):
        return {"platform":"meta","configured":self.configured,"mode":"dry-run" if settings.dry_run else "live"}

    async def list_campaigns(self):
        if settings.dry_run or not self.configured:
            return {"data":[],"dry_run":True,"configured":self.configured}
        account = settings.meta_account_id.removeprefix("act_")
        url = f"https://graph.facebook.com/{settings.meta_graph_version}/act_{account}/campaigns"
        params = {"access_token":settings.meta_token,"fields":"id,name,status,effective_status,daily_budget,lifetime_budget","limit":100}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def execute(self, req: ActionRequest):
        if settings.dry_run or not self.configured:
            return {"simulated":True,"action":req.action,"object_id":req.object_id}
        payload = {"access_token":settings.meta_token}
        if req.action == ActionType.PAUSE_CAMPAIGN:
            payload["status"] = "PAUSED"
        elif req.action == ActionType.ACTIVATE_CAMPAIGN:
            payload["status"] = "ACTIVE"
        elif req.action == ActionType.UPDATE_BUDGET:
            payload["daily_budget"] = str(int(req.new_budget * 100))
        url = f"https://graph.facebook.com/{settings.meta_graph_version}/{req.object_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, data=payload)
            r.raise_for_status()
            return r.json()
