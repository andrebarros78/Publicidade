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


def test_asset_manifest_contract_is_present():
    r = client.get('/v1/autonomy/asset-manifest')
    assert r.status_code == 200
    body = r.json()
    assert body['version'] == 'ads-agency-3d-assets/v1'
    assert body['rig_profile'] == 'ads-humanoid-v1'
    assert body['animation_contract'] == 'ads-agent-animation/v1'
    assert 'Walk' in body['required_animations']
    assert 'Use_Computer' in body['required_animations']
    assert 'Hips' in body['required_bones']
    assert body['limits']['max_file_mb'] > 0


def test_visual_state_does_not_release_unapproved_assets():
    r = client.get('/v1/autonomy/visual-state')
    assert r.status_code == 200
    body = r.json()
    assert body['asset_manifest_version'] == 'ads-agency-3d-assets/v1'
    assert len(body['agents']) == 16
    assert all(agent['model_url'] is None for agent in body['agents'])
    assert all(agent['asset_status'] == 'pending' for agent in body['agents'])


def test_system_primary_route_selects_openai():
    r = client.get('/v1/autonomy/model-route?system_primary=true')
    assert r.status_code == 200
    assert r.json()['selected']['provider'] == 'openai'
    assert r.json()['source'] == 'policy-only'


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


def test_vault_readiness_blocks_unvalidated_system_primary():
    r = client.post('/v1/autonomy/model-route/evaluate', json={
        'system_primary': True,
        'providers': [
            {'provider': 'openai', 'vault_level': 1, 'configured': True, 'validated': False, 'enabled': True},
        ],
    })
    assert r.status_code == 503
    assert r.json()['detail']['reason'] == 'system_primary_provider_not_ready'


def test_vault_readiness_requires_level_one_for_system_primary():
    r = client.post('/v1/autonomy/model-route/evaluate', json={
        'system_primary': True,
        'providers': [
            {'provider': 'openai', 'vault_level': 2, 'configured': True, 'validated': True, 'enabled': True},
        ],
    })
    assert r.status_code == 503


def test_vault_readiness_selects_first_validated_free_agent_and_fallbacks():
    r = client.post('/v1/autonomy/model-route/evaluate', json={
        'providers': [
            {'provider': 'groq', 'vault_level': 2, 'configured': True, 'validated': False, 'enabled': True},
            {'provider': 'qwen', 'vault_level': 2, 'configured': True, 'validated': True, 'enabled': True},
            {'provider': 'glm', 'vault_level': 2, 'configured': True, 'validated': True, 'enabled': True},
            {'provider': 'deepseek', 'vault_level': 2, 'configured': True, 'validated': True, 'enabled': False},
        ],
    })
    assert r.status_code == 200
    body = r.json()
    assert body['source'] == 'vault-readiness'
    assert body['selected']['provider'] == 'qwen'
    assert [item['provider'] for item in body['fallbacks']] == ['glm']


def test_vault_readiness_returns_503_when_no_agent_provider_is_ready():
    r = client.post('/v1/autonomy/model-route/evaluate', json={
        'providers': [
            {'provider': 'groq', 'vault_level': 2, 'configured': True, 'validated': False, 'enabled': True},
        ],
    })
    assert r.status_code == 503
    assert r.json()['detail']['reason'] == 'no_ready_free_agent_provider'
