import asyncio
from fastapi.testclient import TestClient

from app.main import app
from agentic.runtime.autonomous_team import build_team
from agentic.runtime.orchestrator import MissionRequest, execute_mission

client = TestClient(app)


class FakeRunResult:
    def __init__(self, last_agent, final_output):
        self.last_agent = last_agent
        self.final_output = final_output


def test_orchestrator_mirrors_real_agent_hooks_to_task_bus_contract():
    team = build_team(model='test-model')
    strategy = team.agents['marketing_strategist']
    market = team.agents['market_intelligence']
    published = []

    async def publish(payload):
        published.append(payload.copy())
        return payload

    async def fake_runner(agent, objective, max_turns, hooks):
        assert agent is team.chief
        assert objective == 'Diagnosticar oportunidade e definir estratégia'
        assert max_turns == 12
        await hooks.on_agent_start(None, team.chief)
        await hooks.on_agent_start(None, strategy)
        await hooks.on_handoff(None, strategy, market)
        await hooks.on_agent_start(None, market)
        return FakeRunResult(market, 'plano concluído')

    async def scenario():
        return await execute_mission(
            MissionRequest(
                mission_id='mission-test-1',
                objective='Diagnosticar oportunidade e definir estratégia',
                task_type='strategy',
                priority='high',
                max_turns=12,
            ),
            publish,
            team=team,
            runner_factory=fake_runner,
        )

    result = asyncio.run(scenario())
    assert result['status'] == 'completed'
    assert result['last_agent_id'] == 'market_intelligence'
    assert result['agents_touched'] == ['chief_ads_officer', 'marketing_strategist', 'market_intelligence']
    assert result['final_output'] == 'plano concluído'
    assert any(x['agent_id'] == 'chief_ads_officer' and x['operational_state'] == 'working' for x in published)
    assert any(x['agent_id'] == 'marketing_strategist' and x['operational_state'] == 'working' for x in published)
    assert any(x['agent_id'] == 'market_intelligence' and x['operational_state'] == 'working' for x in published)
    rests = [x['agent_id'] for x in published if x['operational_state'] == 'rest']
    assert set(rests) == {'chief_ads_officer', 'marketing_strategist', 'market_intelligence'}
    assert all(x['source'] == 'production' for x in published)


def test_mission_endpoint_requires_model_router_route():
    r = client.post('/v1/autonomy/missions/run', json={
        'objective': 'Analisar as campanhas atuais e definir próximos passos',
        'task_type': 'performance_review',
    })
    assert r.status_code == 503
    assert r.json()['detail']['reason'] == 'model_route_required'


def test_mission_and_vault_gateway_endpoints_are_registered():
    routes = {getattr(route, 'path', None) for route in app.routes}
    assert '/v1/autonomy/missions/run' in routes
    assert '/v1/model-gateway/chat/completions' in routes


def test_vault_gateway_requires_opaque_lease():
    r = client.post('/v1/model-gateway/chat/completions', json={'model': 'x', 'messages': []})
    assert r.status_code == 401
