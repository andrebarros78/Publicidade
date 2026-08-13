from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_policy_is_free_first_and_replaceable():
    r = client.get('/v1/autonomy/model-policy')
    assert r.status_code == 200
    body = r.json()
    assert body['mode'] == 'FREE-FIRST'
    assert body['system_primary']['provider'] == 'openai'
    assert body['system_primary']['replaceable'] is True
    assert body['paid_auxiliaries_enabled'] is False
    assert body['provider_lock_in'] is False


def test_system_primary_route_selects_openai():
    r = client.get('/v1/autonomy/model-route?system_primary=true')
    assert r.status_code == 200
    assert r.json()['selected']['provider'] == 'openai'


def test_agent_route_prefers_first_free_provider_and_has_failover():
    r = client.get('/v1/autonomy/model-route')
    assert r.status_code == 200
    body = r.json()
    assert body['selected']['provider'] == 'groq'
    assert len(body['fallbacks']) >= 1
    assert all(x['role'] == 'agent-free' for x in body['fallbacks'])


def test_paid_auxiliary_route_is_blocked():
    r = client.get('/v1/autonomy/model-route?allow_paid=true')
    assert r.status_code == 409
