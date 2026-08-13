import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix='/v1/autonomy/ai-spend', tags=['ai-spend'])


def _db_path() -> Path:
    value = os.getenv('ADS_AI_SPEND_DB', './data/ai-spend.sqlite3')
    return Path(value)


def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_ai_spend_store():
    with _connect() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ai_spend_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                agent TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                estimated_cost_brl REAL NOT NULL,
                actual_cost_brl REAL,
                status TEXT NOT NULL,
                reason TEXT
            )
        ''')
        conn.commit()


def auxiliary_budget_brl() -> float:
    return max(0.0, float(os.getenv('ADS_AUX_AI_MONTHLY_BUDGET_BRL', '0')))


def current_month_spend() -> float:
    init_ai_spend_store()
    prefix = datetime.now(timezone.utc).strftime('%Y-%m')
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(actual_cost_brl),0) AS total FROM ai_spend_events WHERE status='completed' AND created_at LIKE ?",
            (f'{prefix}%',),
        ).fetchone()
    return float(row['total'] or 0)


class SpendCheckIn(BaseModel):
    agent: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    estimated_cost_brl: float = Field(ge=0)
    auxiliary: bool = True


class SpendRecordIn(SpendCheckIn):
    actual_cost_brl: float = Field(ge=0)


def check_spend(data: SpendCheckIn):
    budget = auxiliary_budget_brl() if data.auxiliary else None
    spent = current_month_spend() if data.auxiliary else 0.0
    projected = spent + data.estimated_cost_brl
    allowed = True if not data.auxiliary else projected <= float(budget)
    return {
        'allowed': allowed,
        'mode': 'FREE-FIRST' if data.auxiliary and float(budget) == 0 else 'BUDGETED',
        'monthly_budget_brl': budget,
        'month_spend_brl': spent,
        'estimated_cost_brl': data.estimated_cost_brl,
        'projected_spend_brl': projected,
        'reason': None if allowed else 'auxiliary_ai_budget_exceeded',
        'agent': data.agent,
        'provider': data.provider,
        'model': data.model,
    }


@router.get('')
def state():
    return {
        'auxiliary_monthly_budget_brl': auxiliary_budget_brl(),
        'month_spend_brl': current_month_spend(),
        'free_first_enforced': auxiliary_budget_brl() == 0,
    }


@router.post('/check')
def preflight(data: SpendCheckIn):
    result = check_spend(data)
    if not result['allowed']:
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post('/record')
def record(data: SpendRecordIn):
    pre = check_spend(data)
    if not pre['allowed']:
        raise HTTPException(status_code=409, detail=pre)
    init_ai_spend_store()
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            'INSERT INTO ai_spend_events(created_at,agent,provider,model,estimated_cost_brl,actual_cost_brl,status,reason) VALUES(?,?,?,?,?,?,?,?)',
            (created_at, data.agent, data.provider, data.model, data.estimated_cost_brl, data.actual_cost_brl, 'completed', None),
        )
        conn.commit()
    return {'recorded': True, 'created_at': created_at, 'actual_cost_brl': data.actual_cost_brl}
