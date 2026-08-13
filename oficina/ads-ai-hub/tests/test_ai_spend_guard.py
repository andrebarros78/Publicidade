import os
from pathlib import Path

from fastapi.testclient import TestClient

TMP_DB = Path('/tmp/ads-ai-spend-test.sqlite3')
os.environ['ADS_AI_SPEND_DB'] = str(TMP_DB)
os.environ['ADS_AUX_AI_MONTHLY_BUDGET_BRL'] = '0'
if TMP_DB.exists():
    TMP_DB.unlink()

from app.main import app

client = TestClient(app)


def test_free_first_starts_with_zero_auxiliary_budget():
    r = client.get('/v1/autonomy/ai-spend')
    assert r.status_code == 200
    body = r.json()
    assert body['auxiliary_monthly_budget_brl'] == 0
    assert body['month_spend_brl'] == 0
    assert body['free_first_enforced'] is True


def test_zero_cost_auxiliary_call_is_allowed():
    r = client.post('/v1/autonomy/ai-spend/check', json={
        'agent': 'market_intelligence',
        'provider': 'qwen',
        'model': 'free-route',
        'estimated_cost_brl': 0,
        'auxiliary': True,
    })
    assert r.status_code == 200
    assert r.json()['allowed'] is True


def test_any_positive_auxiliary_cost_is_blocked_at_zero_budget():
    r = client.post('/v1/autonomy/ai-spend/check', json={
        'agent': 'copywriter',
        'provider': 'paid-provider',
        'model': 'premium-model',
        'estimated_cost_brl': 0.01,
        'auxiliary': True,
    })
    assert r.status_code == 409
    assert r.json()['detail']['reason'] == 'auxiliary_ai_budget_exceeded'


def test_primary_system_call_is_not_subject_to_auxiliary_zero_ceiling():
    r = client.post('/v1/autonomy/ai-spend/check', json={
        'agent': 'chief_ads_officer',
        'provider': 'openai',
        'model': 'system-primary',
        'estimated_cost_brl': 0.01,
        'auxiliary': False,
    })
    assert r.status_code == 200
    assert r.json()['allowed'] is True
