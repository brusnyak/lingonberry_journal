from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from webapp.app import _BLIND_SESSIONS, app


def _bars(n: int = 20) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [100 + i for i in range(n)],
            "high": [101 + i for i in range(n)],
            "low": [99 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": 1,
        }
    )


def test_blind_session_only_returns_visible_context(monkeypatch):
    import backtesting.engine.data as data_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    resp = client.post(
        "/api/blind/session",
        json={
            "symbol": "XAUUSD",
            "tf": "5",
            "context_bars": 5,
            "warmup_bars": 10,
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["total_loaded"] == 20
    assert body["cursor"] == 10
    assert len(body["candles"]) == 5
    assert len(body["indicators"]["ema21"]) == 5
    assert body["candles"][-1]["time"] == body["cursor_time"]
    assert body["candles"][-1]["close"] == 110.5
    assert body["candles"][0]["close"] == 106.5
    assert all(c["time"] <= body["cursor_time"] for c in body["candles"])


def test_blind_step_reveals_incrementally(monkeypatch):
    import backtesting.engine.data as data_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    start = client.post(
        "/api/blind/session",
        json={"symbol": "NAS100", "tf": "5", "context_bars": 3, "warmup_bars": 5},
    ).get_json()
    stepped = client.post(
        "/api/blind/step",
        json={"session_id": start["session_id"], "step": 1, "max_step": 1},
    ).get_json()

    assert stepped["cursor"] == 6
    assert len(stepped["candles"]) == 3
    assert stepped["candles"][-1]["close"] == 106.5
    assert stepped["candles"][0]["close"] == 104.5
    assert all(c["time"] <= stepped["cursor_time"] for c in stepped["candles"])


def test_blind_decision_persists_current_cursor_only(monkeypatch, tmp_path):
    import backtesting.engine.data as data_mod
    import webapp.app as app_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    monkeypatch.setattr(app_mod, "_blind_store_path", lambda: tmp_path / "blind.jsonl")
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    start = client.post(
        "/api/blind/session",
        json={"symbol": "GBPUSD", "tf": "5", "context_bars": 5, "warmup_bars": 7},
    ).get_json()
    saved = client.post(
        "/api/blind/decision",
        json={
            "session_id": start["session_id"],
            "bias": "bullish",
            "action": "trade_plan",
            "direction": "long",
            "drawings": [{"type": "ob", "price": 101.25, "cursor": 7}],
            "notes": "test",
        },
    )

    assert saved.status_code == 200
    body = saved.get_json()
    assert body["decision"]["cursor"] == 7
    assert body["decision"]["visible_until"] == start["cursor_time"]
    assert body["decision"]["drawings"] == [{"type": "ob", "price": 101.25, "cursor": 7}]
    assert body["decision"]["management_events"] == []
    assert body["decision"]["cursor_ohlc"]["close"] == 107.5
    assert body["decision"]["indicator_snapshot"]["ema21"] is not None
    assert len(body["decision"]["visible_candles"]) == 5
    assert "exit_price" not in body["decision"]
    assert "r_multiple" not in body["decision"]
    assert (tmp_path / "blind.jsonl").exists()


def test_blind_simulate_scores_plan_after_cursor(monkeypatch):
    import backtesting.engine.data as data_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    start = client.post(
        "/api/blind/session",
        json={"symbol": "XAUUSD", "tf": "5", "context_bars": 5, "warmup_bars": 7},
    ).get_json()
    sim = client.post(
        "/api/blind/simulate",
        json={
            "session_id": start["session_id"],
            "cursor": start["cursor"],
            "direction": "long",
            "entry": 107.5,
            "sl": 105.5,
            "tp": 110.5,
            "max_bars": 10,
        },
    )

    assert sim.status_code == 200
    body = sim.get_json()
    assert body["outcome"] == "tp"
    assert body["r_multiple"] == 1.5
    assert body["bars_elapsed"] == 3
    assert body["revealed_candles"][0]["close"] == 108.5


def test_blind_simulate_applies_sl_to_be_event(monkeypatch):
    import backtesting.engine.data as data_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    start = client.post(
        "/api/blind/session",
        json={"symbol": "XAUUSD", "tf": "5", "context_bars": 5, "warmup_bars": 7},
    ).get_json()
    session_id = start["session_id"]
    client.post("/api/blind/step", json={"session_id": session_id, "step": 2, "max_step": 2})
    ev = client.post("/api/blind/manage", json={"session_id": session_id, "type": "move_sl_be"}).get_json()

    sim = client.post(
        "/api/blind/simulate",
        json={
            "session_id": session_id,
            "cursor": start["cursor"],
            "direction": "long",
            "entry": 107.5,
            "sl": 105.5,
            "tp": 120.5,
            "max_bars": 3,
        },
    ).get_json()

    assert ev["total"] == 1
    assert sim["active_sl"] == 107.5
    assert len(sim["applied_events"]) == 1


def test_blind_analyze_scores_saved_jsonl(monkeypatch, tmp_path):
    import backtesting.engine.data as data_mod
    import webapp.app as app_mod

    monkeypatch.setattr(data_mod, "load_data", lambda *args, **kwargs: _bars(20))
    store = tmp_path / "blind.jsonl"
    monkeypatch.setattr(app_mod, "_blind_store_path", lambda: store)
    _BLIND_SESSIONS.clear()

    client = app.test_client()
    start = client.post(
        "/api/blind/session",
        json={"symbol": "XAUUSD", "tf": "5", "context_bars": 5, "warmup_bars": 7},
    ).get_json()
    client.post(
        "/api/blind/decision",
        json={
            "session_id": start["session_id"],
            "bias": "bullish",
            "action": "trade_plan",
            "direction": "long",
            "entry": 107.5,
            "sl": 105.5,
            "tp": 110.5,
            "notes": "unit",
        },
    )

    resp = client.get("/api/blind/analyze?max_bars=10")
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["summary"]["valid"] == 1
    assert body["summary"]["avg_r"] == 1.5
    assert body["rows"][0]["sim_outcome"] == "tp"
