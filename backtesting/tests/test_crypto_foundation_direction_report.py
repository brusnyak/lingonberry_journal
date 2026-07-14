from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.crypto.foundation_direction_report import (
    FoundationDirectionConfig,
    classify_state_arrays,
    sample_foundation_calls,
    score_foundation_calls,
    summarize_foundation_scores_by_symbol,
)


def test_classify_state_arrays_separates_foundation_states():
    state, direction = classify_state_arrays(
        np.array(["bull", "bull", "neutral", "bull", "neutral"]),
        np.array(["bull", "bull", "bear", "bear", "neutral"]),
        np.array(["bull", "bear", "bear", "bear", "neutral"]),
    )

    assert state.tolist() == [
        "confirmed_trend",
        "pullback_in_trend",
        "local_trend_htf_neutral",
        "htf_local_disagree",
        "range_or_unresolved",
    ]
    assert direction.tolist() == ["bull", "bull", "bear", "none", "none"]


def test_sample_foundation_calls_keeps_first_state_direction_per_day():
    states = pd.DataFrame({
        "symbol": ["BTCUSDT"] * 5,
        "ts": pd.to_datetime(
            [
                "2026-01-01T00:00Z",
                "2026-01-01T00:15Z",
                "2026-01-01T00:30Z",
                "2026-01-02T00:00Z",
                "2026-01-02T00:15Z",
            ]
        ),
        "day": [
            pd.Timestamp("2026-01-01").date(),
            pd.Timestamp("2026-01-01").date(),
            pd.Timestamp("2026-01-01").date(),
            pd.Timestamp("2026-01-02").date(),
            pd.Timestamp("2026-01-02").date(),
        ],
        "foundation_state": [
            "confirmed_trend",
            "confirmed_trend",
            "pullback_in_trend",
            "confirmed_trend",
            "range_or_unresolved",
        ],
        "direction": ["bull", "bull", "bull", "bear", "none"],
    })

    calls = sample_foundation_calls(states)

    assert calls["entry_i"].tolist() == [0, 2, 3]


def test_score_foundation_calls_uses_symmetric_r_outcomes():
    bars = pd.DataFrame({
        "ts": pd.date_range("2026-01-01", periods=40, freq="15min", tz="UTC"),
        "open": [100.0] * 40,
        "high": [101.0] * 40,
        "low": [99.0] * 40,
        "close": [100.0] * 40,
    })
    calls = pd.DataFrame({
        "entry_i": [20],
        "symbol": ["BTCUSDT"],
        "ts": [bars["ts"].iat[20]],
        "day": [bars["ts"].iat[20].date()],
        "foundation_state": ["confirmed_trend"],
        "direction": ["bull"],
    })
    # Put the winning bar after ATR has warmed up.
    bars.loc[21, "high"] = 103.0
    cfg = FoundationDirectionConfig(horizons_bars=(4,))

    scores = score_foundation_calls(bars, calls, cfg)

    assert scores.iloc[0]["outcome"] == "win"


def test_summarize_foundation_scores_by_symbol_reports_accuracy():
    scores = pd.DataFrame({
        "symbol": ["BTCUSDT", "BTCUSDT", "ETHUSDT"],
        "foundation_state": ["confirmed_trend", "confirmed_trend", "confirmed_trend"],
        "horizon_bars": [24, 24, 24],
        "outcome": ["win", "loss", "win"],
    })

    out = summarize_foundation_scores_by_symbol(scores)

    btc = out[out["symbol"] == "BTCUSDT"].iloc[0]
    eth = out[out["symbol"] == "ETHUSDT"].iloc[0]
    assert btc["direction_accuracy"] == 0.5
    assert eth["direction_accuracy"] == 1.0
