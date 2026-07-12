"""Tests for rolling validation of event-atlas buckets."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.event_validation import ValidationGate, validate_event_buckets, walk_forward_validate_buckets


def _events() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=12, freq="7D", tz="UTC")
    rows = []
    for i, t in enumerate(ts):
        rows.append({
            "entry_ts": t,
            "exchange": "binance" if i % 2 == 0 else "bybit",
            "symbol": "BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            "event": "bullish_fvg_formation",
            "direction": "long",
            "stop_model": "prior_swing",
            "target_model": "fixed_2r",
            "ctx_240_regime": "bear",
            "session_utc": "asia",
            "vol_bucket": "normal",
            "net_r": 0.5 if i != 3 else -0.2,
            "entry": 100.0,
            "risk_price": 0.25,
            "target_r": 2.0,
        })
    return pd.DataFrame(rows)


def test_validate_event_buckets_passes_diversified_positive_bucket():
    result = validate_event_buckets(
        _events(),
        window_days=14,
        step_days=7,
        gate=ValidationGate(
            min_events=10,
            min_windows=4,
            min_pf=1.2,
            min_avg_net_r=0.05,
            min_positive_window_rate=0.7,
            max_concentration=0.6,
        ),
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert bool(row["passed_gate"])
    assert row["symbols"] == 2
    assert row["exchanges"] == 2
    assert row["positive_window_rate"] >= 0.7


def test_validate_event_buckets_fails_single_symbol_concentration():
    events = _events()
    events["symbol"] = "BTCUSDT"

    result = validate_event_buckets(
        events,
        window_days=14,
        step_days=7,
        gate=ValidationGate(min_events=10, min_windows=4, max_concentration=0.6),
    )

    assert len(result) == 1
    assert not bool(result.iloc[0]["passed_gate"])
    assert result.iloc[0]["max_symbol_share"] == 1.0


def test_validate_event_buckets_rejects_missing_required_columns():
    events = _events().drop(columns=["net_r"])

    try:
        validate_event_buckets(events)
    except ValueError as exc:
        assert "net_r" in str(exc)
    else:
        raise AssertionError("Expected missing net_r to raise ValueError")


def test_validate_event_buckets_filters_low_reward_ratio_plans():
    events = _events()
    events["target_r"] = 1.0

    result = validate_event_buckets(
        events,
        window_days=14,
        step_days=7,
        gate=ValidationGate(min_events=10, min_windows=4, min_target_r=1.5),
    )

    assert result.empty


def test_validate_event_buckets_fails_tiny_stop_distance():
    events = _events()
    events["risk_price"] = 0.05

    result = validate_event_buckets(
        events,
        window_days=14,
        step_days=7,
        gate=ValidationGate(
            min_events=10,
            min_windows=4,
            min_pf=1.2,
            min_avg_net_r=0.05,
            min_positive_window_rate=0.7,
            min_median_risk_pct=0.0015,
            max_concentration=0.6,
        ),
    )

    assert len(result) == 1
    assert not bool(result.iloc[0]["passed_gate"])
    assert result.iloc[0]["median_risk_pct"] < 0.0015


def test_walk_forward_reports_selected_bucket_holdout_result():
    discovery_ts = pd.date_range("2026-01-01", periods=20, freq="D", tz="UTC")
    holdout_ts = pd.date_range("2026-01-21", periods=20, freq="D", tz="UTC")
    rows = []
    for i, t in enumerate([*discovery_ts, *holdout_ts]):
        is_holdout = t >= holdout_ts[0]
        rows.append({
            "entry_ts": t,
            "exchange": "binance" if i % 2 == 0 else "bybit",
            "symbol": "BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            "event": "bearish_fvg_formation",
            "direction": "short",
            "stop_model": "prior_swing",
            "target_model": "fixed_2r",
            "ctx_240_regime": "bull",
            "session_utc": "late_us",
            "vol_bucket": "high",
            "entry": 100.0,
            "risk_price": 1.0,
            "target_r": 2.0,
            "net_r": -0.5 if is_holdout else 0.7,
        })
    events = pd.DataFrame(rows)

    result = walk_forward_validate_buckets(
        events,
        discovery_days=20,
        holdout_days=20,
        gate=ValidationGate(
            min_events=10,
            min_windows=1,
            min_pf=1.2,
            min_avg_net_r=0.05,
            min_positive_window_rate=0.5,
            max_concentration=0.6,
        ),
    )

    assert len(result) == 1
    assert result.iloc[0]["discovery_avg_net_r"] > 0
    assert result.iloc[0]["holdout_avg_net_r"] < 0
    assert not bool(result.iloc[0]["passed_holdout"])
