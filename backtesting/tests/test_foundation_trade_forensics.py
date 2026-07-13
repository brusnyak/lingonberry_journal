from __future__ import annotations

import pandas as pd

from backtesting.crypto.foundation_trade_forensics import (
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
