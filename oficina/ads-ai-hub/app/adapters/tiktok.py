import httpx
from app.adapters.base import AdsAdapter
from app.core.config import settings
from app.core.models import ActionRequest, ActionType

class TikTokAdapter(AdsAdapter):
    @property
    def configured(self) -> bool:
        return bool(settings.tiktok_token and settings.tiktok_advertiser_id)

    def headers(self):
        return {"Access-Token":settings.tiktok_token,"Content-Type":"application/json"}

    async def health(self):
        return {"platform":"tiktok","configured":self.configured,"mode":"dry-run" if settings.dry_run else "live"}

    async def list_campaigns(self):
        if settings.dry_run or not self.configured:
            return {"data":{"list":[]},"dry_run":True,"configured":self.configured}
        url = f"{settings.tiktok_api_base}/campaign/get/"
        params = {"advertiser_id":settings.tiktok_advertiser_id,"page_size":100}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self.headers(), params=params)
            r.raise_for_status()
            return r.json()

    async def execute(self, req: ActionRequest):
        if settings.dry_run or not self.configured:
            return {"simulated":True,"action":req.action,"object_id":req.object_id}
        if req.action in {ActionType.PAUSE_CAMPAIGN, ActionType.ACTIVATE_CAMPAIGN}:
            url = f"{settings.tiktok_api_base}/campaign/status/update/"
            op = "DISABLE" if req.action == ActionType.PAUSE_CAMPAIGN else "ENABLE"
            payload = {"advertiser_id":settings.tiktok_advertiser_id,"campaign_ids":[req.object_id],"operation_status":op}
        else:
            url = f"{settings.tiktok_api_base}/campaign/update/"
            payload = {"advertiser_id":settings.tiktok_advertiser_id,"campaign_id":req.object_id,"budget":req.new_budget}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=self.headers(), json=payload)
            r.raise_for_status()
            return r.json()
