from fastapi import FastAPI, HTTPException
from app.core.models import ActionRequest, Platform
from app.service import execute, health_all, list_campaigns
from app.autonomy import router as autonomy_router

app = FastAPI(title="ADS-AI-HUB", version="0.2.0", description="API canônica multicanal com núcleo autônomo multiagente")
app.include_router(autonomy_router)

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
