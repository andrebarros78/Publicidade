import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from agentic.runtime.team import posts, owner_controls
from agentic.digital_twin.engine import DigitalTwin

router = APIRouter(prefix='/v1/autonomy', tags=['autonomy'])
POLICY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'model-router-policy.json'


class ProviderReadiness(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    vault_level: Literal[1, 2]
    configured: bool
    validated: bool
    enabled: bool = True


class RouteEvaluationIn(BaseModel):
    system_primary: bool = False
    allow_paid: bool = False
    providers: list[ProviderReadiness] = Field(default_factory=list)


VISUAL_POSTS = {
    'chief_ads_officer': ('diretoria', 'director_desk', 'computer'),
    'marketing_strategist': ('strategy', 'strategy_desk', 'computer'),
    'market_intelligence': ('intelligence', 'market_station', 'computer'),
    'consumer_intelligence': ('intelligence', 'consumer_station', 'computer'),
    'product_portfolio': ('intelligence', 'portfolio_station', 'tablet'),
    'performance_scientist': ('performance', 'performance_station', 'computer'),
    'marketing_science': ('performance', 'mmm_station', 'computer'),
    'attribution_specialist': ('performance', 'attribution_station', 'computer'),
    'budget_allocator': ('budget', 'budget_station', 'computer'),
    'experiment_scientist': ('lab', 'experiment_station', 'tablet'),
    'creative_director': ('creative', 'creative_director_desk', 'tablet'),
    'copywriter': ('creative', 'copywriter_desk', 'computer'),
    'meta_media_buyer': ('paid_media', 'meta_station', 'computer'),
    'tiktok_media_buyer': ('paid_media', 'tiktok_station', 'computer'),
    'risk_guardian': ('risk', 'risk_station', 'tablet'),
    'ads_operations': ('operations', 'operations_station', 'computer'),
}


def model_policy():
    return json.loads(POLICY_PATH.read_text(encoding='utf-8'))


def asset_manifest():
    return model_policy().get('agency_3d_assets', {})


def approved_asset(agent_id: str):
    manifest = asset_manifest()
    asset = (manifest.get('assets') or {}).get(agent_id) or {}
    validation = asset.get('validation') or {}
    if asset.get('status') != 'approved' or validation.get('passed') is not True:
        return None
    if asset.get('rig_profile') != manifest.get('rig_profile'):
        return None
    model_url = asset.get('model_url')
    return asset if isinstance(model_url, str) and model_url.strip() else None


def _expected_level(system_primary: bool) -> int:
    return 1 if system_primary else 2


def _eligible(readiness: ProviderReadiness, expected_level: int) -> bool:
    return (
        readiness.vault_level == expected_level
        and readiness.configured
        and readiness.validated
        and readiness.enabled
    )


def evaluate_model_route(data: RouteEvaluationIn):
    policy = model_policy()
    if data.allow_paid and not policy['paid_auxiliaries_enabled']:
        raise HTTPException(status_code=409, detail='paid auxiliary routes are disabled by FREE-FIRST policy')

    expected_level = _expected_level(data.system_primary)
    readiness = {item.provider.lower(): item for item in data.providers}

    if data.system_primary:
        provider = str(policy['system_primary']['provider']).lower()
        item = readiness.get(provider)
        if not item or not _eligible(item, expected_level):
            raise HTTPException(status_code=503, detail={
                'reason': 'system_primary_provider_not_ready',
                'provider': provider,
                'required_vault_level': expected_level,
            })
        return {
            'mode': policy['mode'],
            'selected': policy['system_primary'],
            'fallbacks': [],
            'source': 'vault-readiness',
        }

    ordered = [str(p).lower() for p in policy['agent_provider_order']]
    eligible = [provider for provider in ordered if provider in readiness and _eligible(readiness[provider], expected_level)]
    if not eligible:
        raise HTTPException(status_code=503, detail={
            'reason': 'no_ready_free_agent_provider',
            'required_vault_level': expected_level,
        })

    return {
        'mode': policy['mode'],
        'selected': {'provider': eligible[0], 'role': 'agent-free'},
        'fallbacks': [{'provider': p, 'role': 'agent-free'} for p in eligible[1:]],
        'source': 'vault-readiness',
    }


@router.get('/team')
def team():
    return {'agents':[p.__dict__ for p in posts()], 'controls':owner_controls()}


@router.get('/asset-manifest')
def get_asset_manifest():
    manifest = asset_manifest()
    assets = manifest.get('assets') or {}
    return {
        **manifest,
        'assets': {
            agent_id: {
                'status': value.get('status', 'pending'),
                'model_url': value.get('model_url') if approved_asset(agent_id) else None,
                'rig_profile': value.get('rig_profile'),
                'validation': value.get('validation', {}),
            }
            for agent_id, value in assets.items()
        },
    }


@router.get('/visual-state')
def visual_state():
    """Canonical visual state consumed by the 3D office.

    Agents without a real task remain REST. A model URL is released only when
    the canonical asset manifest marks that GLB as approved and validated.
    """
    manifest = asset_manifest()
    rig_profile = manifest.get('rig_profile', 'ads-humanoid-v1')
    animation_contract = manifest.get('animation_contract', 'ads-agent-animation/v1')
    agents = []
    for post in posts():
        room, destination, tool = VISUAL_POSTS.get(post.id, ('rest', 'rest_seat', 'none'))
        asset = approved_asset(post.id)
        agents.append({
            'agent_id': post.id,
            'title': post.title,
            'operational_state': 'rest',
            'task_id': None,
            'task_type': None,
            'room': 'rest',
            'home_room': room,
            'destination': 'rest_seat',
            'work_destination': destination,
            'progress': 0,
            'priority': 'normal',
            'tool': 'none',
            'work_tool': tool,
            'model_url': asset.get('model_url') if asset else None,
            'asset_status': 'approved' if asset else 'pending',
            'rig_profile': rig_profile,
            'updated_at': None,
        })
    return {
        'contract_version': 'ads-agent-visual-state/v1',
        'asset_manifest_version': manifest.get('version'),
        'animation_contract': animation_contract,
        'rig_profile': rig_profile,
        'source': 'ads-ai-hub',
        'task_bus_connected': False,
        'agents': agents,
    }


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
            'source': 'policy-only',
        }
    providers = policy['agent_provider_order']
    if not providers:
        raise HTTPException(status_code=503, detail='no free agent provider route configured')
    return {
        'mode': policy['mode'],
        'selected': {'provider': providers[0], 'role': 'agent-free'},
        'fallbacks': [{'provider': p, 'role': 'agent-free'} for p in providers[1:]],
        'source': 'policy-only',
    }


@router.post('/model-route/evaluate')
def post_model_route_evaluate(data: RouteEvaluationIn):
    return evaluate_model_route(data)


@router.post('/digital-twin')
def digital_twin(monthly_spend_ceiling: float = Query(10000, ge=0)):
    twin=DigitalTwin(monthly_spend_ceiling)
    return twin.cycle()
