import os
from pathlib import Path

from fastapi.testclient import TestClient

TMP_DB = Path('/tmp/ads-finance-test.sqlite3')
os.environ['ADS_FINANCE_DB'] = str(TMP_DB)
if TMP_DB.exists():
    TMP_DB.unlink()

from app.main import app

client = TestClient(app)


def test_empty_cockpit_is_explicitly_not_ready():
    r = client.get('/v1/cockpit')
    assert r.status_code == 200
    data = r.json()
    assert data['ready'] is False
    assert data['financial'] is None


def test_snapshot_persists_and_computes_roas_and_mix():
    r = client.post('/v1/cockpit/financial-snapshot', json={
        'budget_authorized': 10000,
        'spend': 4000,
        'revenue': 24000,
        'meta_spend': 3000,
        'tiktok_spend': 1000,
        'currency': 'BRL',
        'source': 'test',
    })
    assert r.status_code == 201
    state = client.get('/v1/cockpit').json()
    assert state['ready'] is True
    assert state['financial']['budget_authorized'] == 10000
    assert state['financial']['spend'] == 4000
    assert state['financial']['revenue'] == 24000
    assert state['financial']['roas'] == 6.0
    assert state['platform_mix'] == {'meta': 0.75, 'tiktok': 0.25}


def test_guard_rejects_spend_above_owner_budget():
    r = client.post('/v1/cockpit/financial-snapshot', json={
        'budget_authorized': 1000,
        'spend': 1200,
        'revenue': 2000,
        'meta_spend': 1200,
        'tiktok_spend': 0,
        'currency': 'BRL',
        'source': 'test',
    })
    assert r.status_code == 409


def test_guard_rejects_platform_sum_above_total_spend():
    r = client.post('/v1/cockpit/financial-snapshot', json={
        'budget_authorized': 5000,
        'spend': 1000,
        'revenue': 4000,
        'meta_spend': 900,
        'tiktok_spend': 500,
        'currency': 'BRL',
        'source': 'test',
    })
    assert r.status_code == 409


def test_recent_decisions_are_persistent():
    r = client.post('/v1/cockpit/decisions', json={
        'agent': 'budget_allocator',
        'action': 'hold',
        'reason': 'sandbox validation',
        'payload': {'amount': 0},
    })
    assert r.status_code == 201
    state = client.get('/v1/cockpit').json()
    assert state['decisions'][0]['agent'] == 'budget_allocator'
    assert state['decisions'][0]['payload']['amount'] == 0
