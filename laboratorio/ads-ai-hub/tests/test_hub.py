from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get('/health'); assert r.status_code == 200
    b = r.json(); assert b['status'] == 'ok'; assert b['dry_run'] is True; assert len(b['platforms']) == 2

def test_platforms():
    r = client.get('/v1/platforms'); assert r.status_code == 200; assert set(r.json()['platforms']) == {'meta','tiktok'}

def test_meta_campaigns_sandbox():
    r = client.get('/v1/campaigns/meta'); assert r.status_code == 200; assert r.json()['dry_run'] is True

def test_tiktok_campaigns_sandbox():
    r = client.get('/v1/campaigns/tiktok'); assert r.status_code == 200; assert r.json()['dry_run'] is True

def test_pause_simulated():
    r = client.post('/v1/actions', json={'platform':'meta','action':'campaign.pause','object_id':'123'}); assert r.status_code == 200; assert r.json()['result']['upstream']['simulated'] is True

def test_large_budget_requires_approval():
    r = client.post('/v1/actions', json={'platform':'tiktok','action':'budget.update','object_id':'abc','current_budget':100,'new_budget':150}); assert r.status_code == 409; assert r.json()['detail']['decision']['requires_approval'] is True

def test_large_budget_with_approval():
    r = client.post('/v1/actions', json={'platform':'tiktok','action':'budget.update','object_id':'abc','current_budget':100,'new_budget':150,'approval_token':'owner-approved'}); assert r.status_code == 200
