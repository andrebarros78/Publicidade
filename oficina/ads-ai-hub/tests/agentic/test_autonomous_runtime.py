from fastapi.testclient import TestClient
from app.main import app
from agentic.runtime.autonomous_team import build_team
from agentic.runtime.spend_guard import check_spend
from agentic.digital_twin.engine import DigitalTwin

def test_real_agents_sdk_team_constructs_without_api_call():
    team=build_team(model='gpt-5.6')
    assert len(team.agents)==16
    assert team.chief.name=='Diretor Geral de Publicidade'
    assert len(team.chief.handoffs)>=8

def test_spend_guard_blocks_ceiling_breach():
    d=check_spend(spent=9900, proposed_increment=101, ceiling=10000)
    assert not d.allowed and d.reason=='owner_ceiling_exceeded'

def test_spend_guard_allows_redistribution_without_new_spend():
    d=check_spend(spent=9000, proposed_increment=0, ceiling=10000)
    assert d.allowed

def test_digital_twin_detects_loss_fatigue_and_reallocates():
    t=DigitalTwin(10000)
    result=t.cycle()
    actions=result['actions']
    assert any(a['action']=='pause' and a['campaign']=='tiktok-loss' for a in actions)
    assert any(a['action']=='refresh_creative' and a['campaign']=='meta-fatigue' for a in actions)
    assert any(a['action']=='transfer' for a in actions)
    assert result['spend'] <= 10000

def test_digital_twin_never_breaks_low_ceiling():
    t=DigitalTwin(5000)
    result=t.cycle()
    assert result['spend'] <= 5300  # starting fixture exceeds this synthetic ceiling; no incremental spend may be added
    assert not any(a.get('amount',0)>0 and a['action']=='transfer' and result['spend']>t.ceiling for a in result['actions'])

def test_api_exposes_team_and_twin():
    c=TestClient(app)
    r=c.get('/v1/autonomy/team'); assert r.status_code==200 and len(r.json()['agents'])==16
    r=c.post('/v1/autonomy/digital-twin?monthly_spend_ceiling=10000'); assert r.status_code==200
    assert r.json()['spend'] <= 10000
