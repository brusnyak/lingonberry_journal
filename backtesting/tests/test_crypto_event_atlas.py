"""Tests for crypto event atlas labeling and outcome math."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.event_atlas import (
    EventAtlasConfig,
    attach_structure_context,
    build_event_atlas,
    summarize_context_buckets,
    summarize_events,
)


def _base_bars(periods: int = 80) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=periods, freq="5min", tz="UTC")
    price = [100.0 + i * 0.1 for i in range(periods)]
    return pd.DataFrame({
        "ts": ts,
        "open": price,
        "high": [p + 0.4 for p in price],
        "low": [p - 0.4 for p in price],
        "close": [p + 0.05 for p in price],
        "volume": [1.0] * periods,
    })


def test_event_atlas_scores_sweep_reclaim_with_cost_adjusted_r():
    df = _base_bars()
    # Make the previous 24-bar low obvious, then sweep/reclaim it.
    df.loc[20:44, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.5]
    df.loc[45, ["open", "high", "low", "close"]] = [100.0, 100.8, 98.5, 99.8]
    df.loc[46, ["open", "high", "low", "close"]] = [100.0, 100.2, 98.0, 99.5]
    df.loc[47, ["open", "high", "low", "close"]] = [99.5, 100.5, 98.7, 100.2]
    df.loc[48, ["open", "high", "low", "close"]] = [100.3, 102.6, 100.1, 102.0]

    events = build_event_atlas(
        df,
        symbol="BTCUSDT",
        exchange="binance",
        tf="5",
        config=EventAtlasConfig(lookback_bars=24, horizon_bars=8, atr_period=5),
    )

    sweep = events[events["event"] == "sweep_reclaim_low"]
    assert not sweep.empty
    row = sweep[sweep["hit_1r"]].iloc[0]
    assert row["direction"] == "long"
    assert row["hit_1r"]
    assert row["gross_r"] >= 1.0
    assert row["cost_r"] > 0.0
    assert row["net_r"] < row["gross_r"]
    assert {"event_extreme", "prior_swing", "atr"} & set(events["stop_model"])
    assert {"fixed_1r", "fixed_2r", "prior_opposite", "round_number"} & set(events["target_model"])
    assert "session_utc" in events.columns
    assert "vol_bucket" in events.columns


def test_structure_context_uses_only_known_after_signal_time():
    events = pd.DataFrame({
        "signal_ts": pd.to_datetime(["2026-01-01 00:10:00Z", "2026-01-01 00:20:00Z"]),
        "event": ["a", "b"],
    })
    structure = pd.DataFrame({
        "known_after_ts": pd.to_datetime(["2026-01-01 00:05:00Z", "2026-01-01 00:15:00Z", "2026-01-01 00:25:00Z"]),
        "regime": ["bull", "bear", "future"],
        "bos_up": [True, False, False],
    })

    out = attach_structure_context(events, structure, context_tf="240")

    assert out.iloc[0]["ctx_240_regime"] == "bull"
    assert out.iloc[1]["ctx_240_regime"] == "bear"
    assert "future" not in set(out["ctx_240_regime"])


def test_summarize_events_marks_small_buckets_not_research_ready():
    events = pd.DataFrame({
        "exchange": ["binance"] * 3,
        "symbol": ["BTCUSDT"] * 3,
        "tf": ["5"] * 3,
        "event": ["sweep"] * 3,
        "direction": ["long"] * 3,
        "net_r": [1.0, -1.0, 2.0],
        "hit_1r": [True, False, True],
        "hit_2r": [False, False, True],
        "hit_stop": [False, True, False],
        "mfe_r": [1.2, 0.2, 2.3],
        "mae_r": [-0.2, -1.0, -0.4],
    })

    summary = summarize_events(events, min_events=5)

    assert summary.iloc[0]["events"] == 3
    assert summary.iloc[0]["avg_net_r"] > 0
    assert not bool(summary.iloc[0]["research_ready"])


def test_context_bucket_summary_groups_by_regime_session_and_volatility():
    events = pd.DataFrame({
        "exchange": ["binance", "bybit"],
        "symbol": ["BTCUSDT", "ETHUSDT"],
        "tf": ["5", "5"],
        "event": ["sweep", "sweep"],
        "direction": ["long", "long"],
        "stop_model": ["event_extreme", "event_extreme"],
        "target_model": ["fixed_2r", "fixed_2r"],
        "ctx_240_regime": ["bull", "bull"],
        "session_utc": ["ny", "ny"],
        "vol_bucket": ["normal", "normal"],
        "net_r": [1.0, -0.2],
        "hit_1r": [True, False],
        "hit_2r": [False, False],
        "hit_target": [True, False],
        "hit_stop": [False, False],
        "mfe_r": [1.5, 0.5],
        "mae_r": [-0.2, -0.4],
    })

    summary = summarize_context_buckets(events, min_events=2)

    assert summary.iloc[0]["ctx_240_regime"] == "bull"
    assert summary.iloc[0]["session_utc"] == "ny"
    assert summary.iloc[0]["vol_bucket"] == "normal"
    assert summary.iloc[0]["symbols"] == 2
    assert summary.iloc[0]["exchanges"] == 2
    assert bool(summary.iloc[0]["research_ready"])
