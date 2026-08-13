from fastapi import FastAPI, HTTPException
from app.core.models import ActionRequest, Platform
from app.service import execute, health_all, list_campaigns
from app.autonomy import router as autonomy_router
from app.finance import router as cockpit_router, init_finance_store

app = FastAPI(title="ADS-AI-HUB", version="0.3.0", description="API canônica multicanal com núcleo autônomo multiagente e cockpit financeiro persistente")
app.include_router(autonomy_router)
app.include_router(cockpit_router)

@app.on_event("startup")
def startup_finance_store():
    init_finance_store()

@app.get("/health")
async def health(): return await health_all()

@app.get("/v1/platforms")
async def platforms(): return {"platforms":["meta","tiktok"]}

@app.get("/v1/campaigns/{platform}")
async def campaigns(platform: Platform): return await list_campaigns(platform)

@app.post("/v1/actions")
async def actions(req: ActionRequest):
    data = await execute(req)
    if not data["decision"]["allowed"]:
        raise HTTPException(status_code=409, detail=data)
    return data
