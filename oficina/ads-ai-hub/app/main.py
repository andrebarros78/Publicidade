import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
from agents import AsyncOpenAI, OpenAIChatCompletionsModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.models import ActionRequest, Platform
from app.service import execute, health_all, list_campaigns
from app.autonomy import router as autonomy_router, visual_state
from app.finance import router as cockpit_router, init_finance_store
from app.ai_spend import router as ai_spend_router, init_ai_spend_store
from agentic.runtime.team import posts
from agentic.runtime.autonomous_team import build_team
from agentic.runtime.orchestrator import MissionConfigurationError, MissionRequest, execute_mission

app = FastAPI(title="ADS-AI-HUB", version="0.7.0", description="API canônica multicanal com núcleo autônomo, task bus realtime, orquestrador multiagente e broker de modelo ligado ao cofre")
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


class MissionModelRouteIn(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    lease_token: str = Field(min_length=16, max_length=256)


class MissionRunIn(BaseModel):
    objective: str = Field(min_length=3, max_length=12000)
    mission_id: str | None = Field(default=None, max_length=120)
    task_type: str = Field(default='ads_operation', min_length=1, max_length=120)
    priority: str = Field(default='normal', min_length=1, max_length=40)
    max_turns: int = Field(default=20, ge=1, le=100)
    model_route: MissionModelRouteIn | None = None


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


def vault_gateway_url() -> str:
    value = os.getenv('ADS_VAULT_MODEL_GATEWAY_URL', '').strip()
    if not value:
        raise MissionConfigurationError('ADS_VAULT_MODEL_GATEWAY_URL is not configured')
    return value


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

@app.post('/v1/model-gateway/chat/completions')
async def vault_model_gateway(request: Request):
    lease = request.headers.get('x-ads-vault-lease', '').strip()
    if not lease:
        raise HTTPException(status_code=401, detail='missing vault model lease')
    body = await request.json()
    if body.get('stream'):
        raise HTTPException(status_code=400, detail='vault model gateway accepts non-stream requests only')
    try:
        gateway = vault_gateway_url()
    except MissionConfigurationError as exc:
        raise HTTPException(status_code=503, detail={'reason': 'vault_model_gateway_not_configured', 'message': str(exc)}) from exc
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            gateway,
            json=body,
            headers={'x-ads-vault-lease': lease, 'accept': 'application/json', 'content-type': 'application/json'},
        )
    payload = response.json() if response.content else None
    return JSONResponse(status_code=response.status_code, content=payload)

@app.post("/v1/autonomy/missions/run")
async def run_mission(data: MissionRunIn):
    if data.model_route is None:
        raise HTTPException(status_code=503, detail={'reason': 'model_route_required', 'message': 'Mission must be routed through Model Router + Vault'})
    mission_id = data.mission_id or f"mission-{uuid.uuid4().hex[:12]}"
    request = MissionRequest(
        mission_id=mission_id,
        objective=data.objective,
        task_type=data.task_type,
        priority=data.priority,
        max_turns=data.max_turns,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://ads.internal') as internal_http:
        openai_client = AsyncOpenAI(
            api_key='vault-broker-opaque',
            base_url='http://ads.internal/v1/model-gateway',
            default_headers={'x-ads-vault-lease': data.model_route.lease_token},
            http_client=internal_http,
        )
        model = OpenAIChatCompletionsModel(model=data.model_route.model, openai_client=openai_client)
        team = build_team(model=model)
        try:
            result = await execute_mission(request, publish_agent_state, team=team)
        except MissionConfigurationError as exc:
            raise HTTPException(status_code=503, detail={'reason': 'agent_runtime_not_configured', 'message': str(exc)}) from exc
    return {
        **result,
        'model_route': {
            'provider': data.model_route.provider,
            'model': data.model_route.model,
            'source': 'model-router+vault-broker',
            'secret_transferred': False,
        },
    }

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
