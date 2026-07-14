from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.crypto.simple_setup_lab import (
    SimpleSetupConfig,
    apply_trade_filters,
    exit_kind,
    profit_factor,
    rolling_window_summary,
    run_portfolio_validation,
    session_bucket,
    setup_signal,
    summarize_trades,
    summarize_windows,
)


def test_setup_signal_context_change_fires_only_on_fresh_direction():
    bars = pd.DataFrame({"close": [100, 101, 102, 103]})
    combo = np.array(["neutral", "bull", "bull", "bear"])

    signal = setup_signal(bars, combo, "context_change")

    assert signal.tolist() == [False, True, False, True]


def test_setup_signal_pullback_reclaim_requires_existing_context_and_ema_reclaim():
    bars = pd.DataFrame(
        {
            "close": [100, 100, 100, 100, 99, 101, 102],
            "high": [101, 101, 101, 101, 100, 102, 103],
            "low": [99, 99, 99, 99, 98, 100, 101],
        }
    )
    combo = np.array(["bull"] * len(bars))

    signal = setup_signal(bars, combo, "pullback_reclaim")

    assert signal.sum() == 1
    assert np.where(signal)[0][0] > 0


def test_setup_signal_rejects_unknown_setup():
    with pytest.raises(ValueError):
        setup_signal(pd.DataFrame({"close": [1, 2, 3]}), np.array(["bull", "bull", "bull"]), "bad")


def test_profit_factor_and_exit_kind():
    assert profit_factor(np.array([1.0, 2.0, -1.0])) == 3.0
    assert exit_kind(1.5) == "target"
    assert exit_kind(-1.0) == "stop"
    assert exit_kind(0.0) == "expiry"


def test_summarize_trades_reports_cost_fragility_fields():
    trades = pd.DataFrame(
        {
            "setup": ["pullback_reclaim", "pullback_reclaim"],
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "base_net_r": [1.4, -1.2],
            "stress_net_r": [0.8, -1.8],
            "gross_r": [1.5, -1.0],
            "stop_pct": [0.5, 0.3],
            "planned_rr": [1.5, 1.5],
            "base_cost_r": [0.1, 0.2],
            "stress_cost_r": [0.7, 0.8],
            "exit_kind": ["target", "stop"],
            "mfe_r": [1.6, 0.4],
            "mae_r": [-0.2, -1.0],
        }
    )

    summary = summarize_trades(trades)

    assert {"base_avg_r", "base_pf", "stress_avg_r", "median_base_cost_r"}.issubset(summary.columns)
    assert summary.iloc[0]["trades"] == 2
    assert summary.iloc[0]["median_stop_pct"] == 0.4


def test_apply_trade_filters_cost_and_session_gate():
    trades = pd.DataFrame(
        {
            "base_cost_r": [0.10, 0.20, 0.10],
            "stress_cost_r": [0.30, 0.40, 0.60],
            "session_utc": ["ny", "ny", "late_us"],
        }
    )
    cfg = SimpleSetupConfig(max_base_cost_r=0.15, max_stress_cost_r=0.50, sessions=("ny",))

    out = apply_trade_filters(trades, cfg)

    assert len(out) == 1
    assert out.iloc[0]["base_cost_r"] == 0.10


def test_rolling_window_summary_and_summary_windows():
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(
                ["2026-01-01T00:00Z", "2026-01-05T00:00Z", "2026-01-20T00:00Z", "2026-02-05T00:00Z"]
            ),
            "base_net_r": [1.0, -0.5, 0.5, -1.0],
            "stress_net_r": [0.5, -0.8, 0.2, -1.2],
            "stop_pct": [0.5, 0.6, 0.7, 0.8],
        }
    )

    windows = rolling_window_summary(trades, window_days=30, step_days=15, min_trades=1)
    summary = summarize_windows(windows)

    assert not windows.empty
    assert {"base_pf", "stress_pf", "base_return_r"}.issubset(windows.columns)
    assert summary.iloc[0]["windows"] == len(windows)


def test_run_portfolio_validation_converts_simple_lab_trades_to_risk_path():
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T00:15Z", "2026-01-01T01:30Z"]),
            "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT"],
            "setup": ["context_change"] * 3,
            "entry": [100.0, 100.0, 100.0],
            "sl": [99.0, 99.0, 99.0],
            "tp": [102.0, 102.0, 102.0],
            "planned_rr": [2.0, 2.0, 2.0],
            "bars_to_exit": [4, 4, 1],
            "exit_kind": ["target", "stop", "target"],
            "stress_net_r": [2.0, -1.0, 2.0],
        }
    )

    accepted, summary = run_portfolio_validation(
        trades,
        net_column="stress_net_r",
        risk_pct=0.01,
        max_open=1,
        max_open_per_symbol=1,
        daily_loss_limit_pct=1.0,
        cooldown_after_loss_bars=0,
    )

    assert len(accepted) < len(trades)
    assert summary["accepted"] == len(accepted)
    assert summary["risk_per_trade_pct"] == 0.01


def test_session_bucket_uses_utc_pseudo_sessions():
    assert session_bucket(pd.Timestamp("2026-01-01T03:00:00Z")) == "asia"
    assert session_bucket(pd.Timestamp("2026-01-01T08:00:00Z")) == "london"
    assert session_bucket(pd.Timestamp("2026-01-01T13:00:00Z")) == "ny"
    assert session_bucket(pd.Timestamp("2026-01-01T20:00:00Z")) == "late_us"
