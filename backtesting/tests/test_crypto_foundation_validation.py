"""Tests for crypto foundation validation layer metrics."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.foundation_validation import _grade, _prepare_outcomes, _summary_row
from backtesting.crypto.canonical_session_harness import SetupSpec


def _base_trades() -> pd.DataFrame:
    return pd.DataFrame({
        "entry_ts": pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
        "bars_to_exit": [4, 4, 4, 4, 4],
        "exchange": ["binance"] * 5,
        "symbol": ["ETHUSDT"] * 5,
        "entry_model": ["structure_confirmed_next_open"] * 5,
        "target_model": ["fixed_2r"] * 5,
        "management_model": ["be_after_half_target"] * 5,
        "direction": ["long"] * 5,
        "entry": [100.0] * 5,
        "stop": [99.0] * 5,
        "target": [102.0] * 5,
        "net_r": [1.5, -0.8, -1.1, -0.2, -0.05],
        "pnl_pct": [0.003, -0.0016, -0.0022, -0.0004, -0.0001],
        "mfe_r": [2.1, 0.3, 1.2, 1.3, 1.1],
        "mae_r": [-0.2, -0.4, -1.2, -0.3, -0.2],
        "hit_1r": [True, False, True, True, True],
        "hit_target": [True, False, False, False, False],
        "hit_stop": [False, False, True, False, False],
        "exit_reason": ["target", "expiry", "stop", "expiry", "breakeven"],
    })


def test_prepare_outcomes_classifies_foundation_failures():
    out = _prepare_outcomes(_base_trades())

    assert out.loc[0, "layer_failure"] == "winner"
    assert out.loc[1, "layer_failure"] == "direction"
    assert out.loc[2, "layer_failure"] == "entry"
    assert out.loc[3, "layer_failure"] == "target"
    assert out.loc[4, "layer_failure"] == "management"
    assert out["direction_correct"].sum() == 4
    assert out["target_too_far"].sum() == 1
    assert out["management_neutralized"].sum() == 1


def test_summary_row_marks_small_sample_as_reject():
    accepted = _prepare_outcomes(_base_trades())
    spec = SetupSpec(
        name="sample",
        filters={},
        entry_priority=("structure_confirmed_next_open",),
        target_model="fixed_2r",
        management_model="be_after_half_target",
    )
    portfolio = {
        "avg_r": 0.5,
        "median_r": 0.5,
        "profit_factor": 3.0,
        "gross_return_pct": 0.01,
        "max_dd_pct": 0.005,
        "daily_max_dd_pct": 0.005,
        "return_to_dd": 2.0,
        "win_rate": 0.6,
        "stop_rate": 0.1,
        "expiry_rate": 0.2,
    }

    row = _summary_row("test", spec, accepted, accepted, portfolio)

    assert row["accepted"] == 5
    assert row["foundation_grade"] == "reject"
    assert "sample<30" in row["foundation_reason"]


def test_grade_promotes_only_clean_enough_foundation():
    base = {
        "accepted": 40,
        "avg_r": 0.42,
        "profit_factor": 2.2,
        "max_dd_pct": 0.01,
    }
    metrics = {
        "direction_accuracy": 0.58,
        "bad_entry_rate": 0.20,
        "clean_path_rate": 0.35,
    }

    assert _grade(base, metrics) == "promote_candidate"

    metrics["direction_accuracy"] = 0.40
    assert _grade(base, metrics) == "reject"
