import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.core.models import ActionRequest, Platform
from app.service import execute, health_all, list_campaigns
from app.autonomy import router as autonomy_router, visual_state
from app.finance import router as cockpit_router, init_finance_store
from app.ai_spend import router as ai_spend_router, init_ai_spend_store

app = FastAPI(title="ADS-AI-HUB", version="0.4.0", description="API canônica multicanal com núcleo autônomo, cockpit financeiro persistente e AI Spend Guard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.include_router(autonomy_router)
app.include_router(cockpit_router)
app.include_router(ai_spend_router)

_event_sequence = 0
_event_subscribers = set()


def _next_event_sequence():
    global _event_sequence
    _event_sequence += 1
    return _event_sequence


def _event_frame(event, payload, sequence):
    return f"id: {sequence}\nevent: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def publish_agent_state(payload):
    sequence = _next_event_sequence()
    event = {
        "event": "agent_state_changed",
        "sequence": sequence,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    for queue in list(_event_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    return sequence


@app.on_event("startup")
def startup_stores():
    init_finance_store()
    init_ai_spend_store()

@app.get("/health")
async def health(): return await health_all()

@app.get("/v1/platforms")
async def platforms(): return {"platforms":["meta","tiktok"]}

@app.get("/v1/campaigns/{platform}")
async def campaigns(platform: Platform): return await list_campaigns(platform)

@app.get("/v1/autonomy/events")
async def autonomy_events(request: Request):
    queue = asyncio.Queue(maxsize=256)
    _event_subscribers.add(queue)

    async def stream():
        try:
            sequence = _next_event_sequence()
            yield _event_frame("snapshot", {
                "event": "snapshot",
                "sequence": sequence,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "visual_state": visual_state(),
            }, sequence)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _event_frame(event["event"], event, event["sequence"])
                except asyncio.TimeoutError:
                    sequence = _next_event_sequence()
                    yield _event_frame("heartbeat", {
                        "event": "heartbeat",
                        "sequence": sequence,
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                    }, sequence)
        finally:
            _event_subscribers.discard(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })

@app.post("/v1/actions")
async def actions(req: ActionRequest):
    data = await execute(req)
    if not data["decision"]["allowed"]:
        raise HTTPException(status_code=409, detail=data)
    return data
