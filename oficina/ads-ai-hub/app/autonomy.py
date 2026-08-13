import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from agentic.runtime.team import posts, owner_controls
from agentic.digital_twin.engine import DigitalTwin

router = APIRouter(prefix='/v1/autonomy', tags=['autonomy'])
POLICY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'model-router-policy.json'


def model_policy():
    return json.loads(POLICY_PATH.read_text(encoding='utf-8'))


@router.get('/team')
def team():
    return {'agents':[p.__dict__ for p in posts()], 'controls':owner_controls()}


@router.get('/model-policy')
def get_model_policy():
    return model_policy()


@router.get('/model-route')
def get_model_route(system_primary: bool = Query(False), allow_paid: bool = Query(False)):
    policy = model_policy()
    if allow_paid and not policy['paid_auxiliaries_enabled']:
        raise HTTPException(status_code=409, detail='paid auxiliary routes are disabled by FREE-FIRST policy')
    if system_primary:
        return {
            'mode': policy['mode'],
            'selected': policy['system_primary'],
            'fallbacks': [],
        }
    providers = policy['agent_provider_order']
    if not providers:
        raise HTTPException(status_code=503, detail='no free agent provider route configured')
    return {
        'mode': policy['mode'],
        'selected': {'provider': providers[0], 'role': 'agent-free'},
        'fallbacks': [{'provider': p, 'role': 'agent-free'} for p in providers[1:]],
    }


@router.post('/digital-twin')
def digital_twin(monthly_spend_ceiling: float = Query(10000, ge=0)):
    twin=DigitalTwin(monthly_spend_ceiling)
    return twin.cycle()
