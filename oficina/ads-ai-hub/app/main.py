import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.core.models import ActionRequest, Platform
from app.service import execute, health_all, list_campaigns
from app.autonomy import router as autonomy_router, visual_state
from app.finance import router as cockpit_router, init_finance_store
from app.ai_spend import router as ai_spend_router, init_ai_spend_store
from agentic.runtime.team import posts

app = FastAPI(title="ADS-AI-HUB", version="0.5.0", description="API canônica multicanal com núcleo autônomo, cockpit financeiro, AI Spend Guard e task bus realtime")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"], allow_credentials=False)
app.include_router(autonomy_router)
app.include_router(cockpit_router)
app.include_router(ai_spend_router)

_event_sequence = 0
_event_subscribers = set()
_agent_task_state = {}
_valid_agent_ids = {p.id for p in posts()}


class AgentTaskStateIn(BaseModel):
    agent_id: str
    operational_state: str
    task_id: str | None = None
    task_type: str | None = None
    room: str | None = None
    destination: str | None = None
    progress: float = Field(default=0, ge=0, le=100)
    priority: str = 'normal'
    tool: str | None = None
    source: str = 'production'


def _next_event_sequence():
    global _event_sequence
    _event_sequence += 1
    return _event_sequence


def _event_frame(event, payload, sequence):
    return f"id: {sequence}\nevent: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _live_visual_state():
    state = visual_state()
    state['task_bus_connected'] = True
    state['task_bus_source'] = 'production-only'
    for agent in state['agents']:
        live = _agent_task_state.get(agent['agent_id'])
        if not live:
            continue
        for key in ('operational_state','task_id','task_type','room','destination','progress','priority','tool','occurred_at'):
            if key in live:
                target = 'updated_at' if key == 'occurred_at' else key
                agent[target] = live[key]
    return state


async def publish_agent_state(payload):
    sequence = _next_event_sequence()
    event = {'event': 'agent_state_changed', 'sequence': sequence, 'occurred_at': datetime.now(timezone.utc).isoformat(), **payload}
    _agent_task_state[event['agent_id']] = event
    for queue in list(_event_subscribers):
        try: queue.put_nowait(event)
        except asyncio.QueueFull: pass
    return event


@app.on_event("startup")
def startup_stores():
    init_finance_store(); init_ai_spend_store()

@app.get("/health")
async def health(): return await health_all()

@app.get("/v1/platforms")
async def platforms(): return {"platforms":["meta","tiktok"]}

@app.get("/v1/campaigns/{platform}")
async def campaigns(platform: Platform): return await list_campaigns(platform)

@app.post("/v1/autonomy/task-state")
async def task_state(data: AgentTaskStateIn):
    if data.agent_id not in _valid_agent_ids:
        raise HTTPException(status_code=404, detail='unknown agent_id')
    if data.source != 'production':
        raise HTTPException(status_code=409, detail='simulation cannot drive canonical agency state')
    event = await publish_agent_state(data.model_dump())
    return {'accepted': True, 'event': event}

@app.get("/v1/autonomy/task-state")
async def current_task_state():
    return {'connected': True, 'source': 'production-only', 'sequence': _event_sequence, 'agents': _agent_task_state}

@app.get("/v1/autonomy/events")
async def autonomy_events(request: Request):
    queue = asyncio.Queue(maxsize=256); _event_subscribers.add(queue)
    async def stream():
        try:
            sequence = _next_event_sequence()
            yield _event_frame('snapshot', {'event':'snapshot','sequence':sequence,'occurred_at':datetime.now(timezone.utc).isoformat(),'visual_state':_live_visual_state()}, sequence)
            while True:
                if await request.is_disconnected(): break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _event_frame(event['event'], event, event['sequence'])
                except asyncio.TimeoutError:
                    sequence = _next_event_sequence()
                    yield _event_frame('heartbeat', {'event':'heartbeat','sequence':sequence,'occurred_at':datetime.now(timezone.utc).isoformat()}, sequence)
        finally:
            _event_subscribers.discard(queue)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control':'no-cache','Connection':'keep-alive','X-Accel-Buffering':'no'})

@app.post("/v1/actions")
async def actions(req: ActionRequest):
    data = await execute(req)
    if not data['decision']['allowed']:
        raise HTTPException(status_code=409, detail=data)
    return data
