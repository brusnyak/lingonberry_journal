from __future__ import annotations

import pandas as pd

from backtesting.crypto.foundation_trade_forensics import (
    apply_cost_stress,
    evaluate_extreme_config_matrix,
    ForensicsRunConfig,
    is_strict_candidate,
    profit_factor,
    rsi_bucket,
    select_concrete_execution,
    volume_bucket,
)


def test_select_concrete_execution_dedupes_physical_entry_variants():
    ts = pd.Timestamp("2026-01-01 00:00Z")
    journal = pd.DataFrame({
        "exchange": ["binance", "binance", "binance"],
        "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
        "direction": ["long", "long", "long"],
        "entry_ts": [ts, ts, ts],
        "entry": [100.0, 100.0, 100.0],
        "stop": [99.0, 99.0, 99.0],
        "target_model": ["fixed_2r", "fixed_2r", "fixed_1_5r"],
        "management_model": ["hold_target_expiry", "hold_target_expiry", "hold_target_expiry"],
        "setup_name": ["late_us_short_bull_flush_ce", "ny_long_neutral_reversal_ce", "ny_long_neutral_reversal_ce"],
        "exit_ts": [ts, ts, ts],
    })

    concrete = select_concrete_execution(journal, "fixed_2r", "hold_target_expiry")

    assert len(concrete) == 1
    assert concrete.iloc[0]["setup_name"] == "ny_long_neutral_reversal_ce"


def test_strict_candidate_accepts_separate_setup_families():
    assert is_strict_candidate({
        "setup_name": "london_long_middle_local_retest",
        "mtf_mode": "trend_aligned",
        "entry_hour_utc": 9,
    })
    assert is_strict_candidate({
        "setup_name": "ny_long_neutral_reversal_ce",
        "mtf_mode": "range_or_transition",
        "entry_hour_utc": 13,
    })
    assert is_strict_candidate({
        "setup_name": "late_us_short_bull_flush_ce",
        "mtf_mode": "countertrend",
        "entry_hour_utc": 22,
    })
    assert not is_strict_candidate({
        "setup_name": "london_long_middle_local_retest",
        "mtf_mode": "pullback_in_uptrend",
        "entry_hour_utc": 9,
    })


def test_indicator_buckets_are_stable():
    assert rsi_bucket(25) == "oversold"
    assert rsi_bucket(72) == "overbought"
    assert rsi_bucket(60) == "bullish_mid"
    assert volume_bucket(2.0) == "high"
    assert volume_bucket(-1.2) == "low"


def test_profit_factor_handles_no_losses():
    assert profit_factor(pd.Series([1.0, 2.0])) == float("inf")
    assert profit_factor(pd.Series([1.0, -0.5])) == 2.0


def test_apply_cost_stress_converts_bps_to_r_units():
    trades = pd.DataFrame({
        "entry": [100.0],
        "risk_price": [1.0],
        "net_r": [1.5],
    })

    stressed = apply_cost_stress(trades, fee_round_trip_bps=10.0, slippage_side_bps=5.0)

    assert stressed.iloc[0]["extra_cost_r"] == 0.2
    assert stressed.iloc[0]["net_r"] == 1.3


def test_extreme_config_matrix_includes_portfolio_variants():
    ts = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * 4,
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT"],
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=1),
        "bars_to_exit": [4, 4, 4, 4],
        "entry": [100.0, 100.0, 100.0, 100.0],
        "risk_price": [1.0, 1.0, 1.0, 1.0],
        "net_r": [1.0, -0.5, 1.5, -1.0],
        "setup_name": ["ny_long_neutral_reversal_ce"] * 4,
        "mtf_mode": ["range_or_transition"] * 4,
        "entry_hour_utc": [13, 13, 13, 13],
        "shock_alignment": ["no_shock"] * 4,
    })

    matrix = evaluate_extreme_config_matrix(events, ForensicsRunConfig())

    assert {"base", "aggressive", "micro_risk_tight"}.issubset(set(matrix["config"]))
    assert {"baseline", "punitive_40bps", "nightmare_60bps"}.issubset(set(matrix["scenario"]))
