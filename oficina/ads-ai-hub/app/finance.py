from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/cockpit", tags=["cockpit"])

DB_PATH = Path(os.getenv("ADS_FINANCE_DB", "storage/ads-finance.sqlite3"))


class FinancialSnapshotIn(BaseModel):
    budget_authorized: float = Field(ge=0)
    spend: float = Field(ge=0)
    revenue: float = Field(ge=0)
    meta_spend: float = Field(default=0, ge=0)
    tiktok_spend: float = Field(default=0, ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    source: str = Field(default="manual_or_connector", min_length=1, max_length=80)


class DecisionIn(BaseModel):
    agent: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_finance_store() -> None:
    with closing(_connect()) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS financial_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              captured_at TEXT NOT NULL,
              budget_authorized REAL NOT NULL CHECK (budget_authorized >= 0),
              spend REAL NOT NULL CHECK (spend >= 0),
              revenue REAL NOT NULL CHECK (revenue >= 0),
              meta_spend REAL NOT NULL DEFAULT 0 CHECK (meta_spend >= 0),
              tiktok_spend REAL NOT NULL DEFAULT 0 CHECK (tiktok_spend >= 0),
              currency TEXT NOT NULL,
              source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cockpit_decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              agent TEXT NOT NULL,
              action TEXT NOT NULL,
              reason TEXT,
              payload_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        con.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_snapshot(data: FinancialSnapshotIn) -> dict[str, Any]:
    if data.spend > data.budget_authorized:
        raise ValueError("spend cannot exceed authorized budget")
    if data.meta_spend + data.tiktok_spend > data.spend + 0.01:
        raise ValueError("platform spend cannot exceed total spend")
    with closing(_connect()) as con:
        cur = con.execute(
            """INSERT INTO financial_snapshots
            (captured_at,budget_authorized,spend,revenue,meta_spend,tiktok_spend,currency,source)
            VALUES (?,?,?,?,?,?,?,?)""",
            (_now(), data.budget_authorized, data.spend, data.revenue,
             data.meta_spend, data.tiktok_spend, data.currency.upper(), data.source),
        )
        con.commit()
        return {"id": cur.lastrowid}


def save_decision(data: DecisionIn) -> dict[str, Any]:
    with closing(_connect()) as con:
        cur = con.execute(
            """INSERT INTO cockpit_decisions
            (created_at,agent,action,reason,payload_json) VALUES (?,?,?,?,?)""",
            (_now(), data.agent, data.action, data.reason, json.dumps(data.payload, ensure_ascii=False)),
        )
        con.commit()
        return {"id": cur.lastrowid}


def cockpit_state() -> dict[str, Any]:
    init_finance_store()
    with closing(_connect()) as con:
        snap = con.execute("SELECT * FROM financial_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        decisions = con.execute(
            "SELECT id,created_at,agent,action,reason,payload_json FROM cockpit_decisions ORDER BY id DESC LIMIT 20"
        ).fetchall()

    if snap is None:
        return {
            "ready": False,
            "financial": None,
            "platform_mix": {"meta": None, "tiktok": None},
            "decisions": [dict(d) | {"payload": json.loads(d["payload_json"])} for d in decisions],
            "message": "financial source not configured",
        }

    spend = float(snap["spend"])
    revenue = float(snap["revenue"])
    meta = float(snap["meta_spend"])
    tiktok = float(snap["tiktok_spend"])
    roas = None if spend == 0 else round(revenue / spend, 4)
    known_platform_spend = meta + tiktok
    mix = {
        "meta": None if known_platform_spend == 0 else round(meta / known_platform_spend, 4),
        "tiktok": None if known_platform_spend == 0 else round(tiktok / known_platform_spend, 4),
    }
    normalized_decisions = []
    for d in decisions:
        item = dict(d)
        item["payload"] = json.loads(item.pop("payload_json"))
        normalized_decisions.append(item)

    return {
        "ready": True,
        "financial": {
            "captured_at": snap["captured_at"],
            "budget_authorized": float(snap["budget_authorized"]),
            "spend": spend,
            "revenue": revenue,
            "roas": roas,
            "currency": snap["currency"],
            "source": snap["source"],
        },
        "platform_mix": mix,
        "decisions": normalized_decisions,
    }


@router.get("")
def get_cockpit():
    return cockpit_state()


@router.post("/financial-snapshot", status_code=201)
def post_financial_snapshot(data: FinancialSnapshotIn):
    init_finance_store()
    try:
        result = save_snapshot(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, **result, "cockpit": cockpit_state()}


@router.post("/decisions", status_code=201)
def post_decision(data: DecisionIn):
    init_finance_store()
    result = save_decision(data)
    return {"ok": True, **result}
