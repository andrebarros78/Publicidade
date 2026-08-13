import os
import pytest
from fastapi.testclient import TestClient
from agents.stream_events import AgentUpdatedStreamEvent

from app.main import app
from agentic.runtime.autonomous_team import build_team
from agentic.runtime.orchestrator import MissionRequest, execute_mission

client = TestClient(app)


class FakeStreamResult:
    def __init__(self, events, last_agent, final_output):
        self._events = events
        self.last_agent = last_agent
        self.final_output = final_output

    async def stream_events(self):
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_orchestrator_mirrors_real_agent_changes_to_task_bus_contract():
    team = build_team(model='test-model')
    strategy = team.agents['marketing_strategist']
    market = team.agents['market_intelligence']
    events = [AgentUpdatedStreamEvent(new_agent=strategy), AgentUpdatedStreamEvent(new_agent=market)]
    published = []

    async def publish(payload):
        published.append(payload.copy())
        return payload

    def fake_runner(agent, objective, max_turns):
        assert agent is team.chief
        assert objective == 'Diagnosticar oportunidade e definir estratégia'
        assert max_turns == 12
        return FakeStreamResult(events, market, 'plano concluído')

    result = await execute_mission(
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

    assert result['status'] == 'completed'
    assert result['last_agent_id'] == 'market_intelligence'
    assert result['agents_touched'] == ['chief_ads_officer', 'marketing_strategist', 'market_intelligence']
    assert result['final_output'] == 'plano concluído'
    assert published[0]['agent_id'] == 'chief_ads_officer'
    assert published[0]['operational_state'] == 'working'
    assert any(x['agent_id'] == 'marketing_strategist' and x['operational_state'] == 'working' for x in published)
    assert any(x['agent_id'] == 'market_intelligence' and x['operational_state'] == 'working' for x in published)
    rests = [x['agent_id'] for x in published if x['operational_state'] == 'rest']
    assert set(rests) == {'chief_ads_officer', 'marketing_strategist', 'market_intelligence'}
    assert all(x['source'] == 'production' for x in published)


def test_mission_endpoint_requires_runtime_model_configuration(monkeypatch):
    monkeypatch.delenv('ADS_AGENT_MODEL', raising=False)
    r = client.post('/v1/autonomy/missions/run', json={
        'objective': 'Analisar as campanhas atuais e definir próximos passos',
        'task_type': 'performance_review',
    })
    assert r.status_code == 503
    assert r.json()['detail']['reason'] == 'agent_runtime_not_configured'


def test_mission_endpoint_is_registered():
    routes = {getattr(route, 'path', None) for route in app.routes}
    assert '/v1/autonomy/missions/run' in routes
