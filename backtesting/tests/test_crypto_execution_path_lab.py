"""Tests for survivor execution-path lab."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.direction_layer import DirectionLayerConfig
from backtesting.crypto.execution_path_lab import ExecutionConfig, evaluate_bearish_fvg_survivor, summarize_execution


def test_execution_lab_scores_retest_and_next_open_entries():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    # Force late-US bearish FVG at i=24: c3 high < c1 low.
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [97.0, 99.0, 95.0, 96.0]
    df.loc[26, ["open", "high", "low", "close"]] = [96.0, 96.5, 90.0, 91.0]
    structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=structure,
        config=ExecutionConfig(atr_period=3, retest_bars=4, horizon_bars=8),
    )

    assert not out.empty
    assert "next_open" in set(out["entry_model"])
    assert {"fvg_ce_retest", "fvg_top_retest"} & set(out["entry_model"])
    assert {"fixed_1_5r", "fixed_2r"} <= set(out["target_model"])
    summary = summarize_execution(out)
    assert not summary.empty
    assert "avg_net_r" in summary.columns
    assert "target_model" in summary.columns


def test_structure_confirmed_entries_require_causal_confirmation():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [97.0, 99.0, 95.0, 96.0]
    df.loc[26, ["open", "high", "low", "close"]] = [96.0, 96.5, 90.0, 91.0]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[25]],
        "regime": ["neutral"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=4,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
        ),
    )

    assert not out.empty
    assert set(out["entry_model"]).issubset({
        "structure_confirmed_next_open",
        "structure_confirmed_fvg_ce_retest",
        "structure_confirmed_fvg_top_retest",
        "structure_confirmed_break_continuation",
    })
    assert "bos_down" in set(out["confirmation_model"])


def test_ema_confirmed_entries_are_optional():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    close = [120.0 - i * 0.2 for i in range(80)]
    df = pd.DataFrame({
        "ts": ts,
        "open": close,
        "high": [p + 1.0 for p in close],
        "low": [p - 1.0 for p in close],
        "close": close,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [115.6, 116.6, 114.6, 115.6]
    df.loc[23, ["open", "high", "low", "close"]] = [115.4, 115.8, 111.0, 111.5]
    df.loc[24, ["open", "high", "low", "close"]] = [111.2, 111.8, 109.0, 110.0]
    df.loc[25, ["open", "high", "low", "close"]] = [110.0, 114.8, 108.5, 109.5]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[25]],
        "regime": ["bear"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=4,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=False,
            include_ema_confirmed_entries=True,
            direction_config=DirectionLayerConfig(ema_fast=3, ema_slow=5),
        ),
    )

    assert not out.empty
    assert set(out["entry_model"]).issubset({
        "ema_structure_confirmed_next_open",
        "ema_structure_confirmed_fvg_ce_retest",
        "ema_structure_confirmed_fvg_top_retest",
        "ema_structure_confirmed_break_continuation",
    })
    assert set(out["ema_state"]) == {"bearish"}


def test_structure_confirmed_entries_do_not_use_future_confirmation():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [97.0, 99.0, 95.0, 96.0]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    future_entry_structure = pd.DataFrame({
        "known_after_ts": [ts[30]],
        "regime": ["bear"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=future_entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=4,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
        ),
    )

    assert out.empty


def test_structure_confirmed_entries_reject_stale_retests():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    # Retest only happens late at bar 29.
    df.loc[25:28, ["open", "high", "low", "close"]] = [96.0, 96.4, 94.0, 95.0]
    df.loc[29, ["open", "high", "low", "close"]] = [95.0, 99.0, 94.0, 94.5]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[25]],
        "regime": ["bear"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=8,
            stale_retest_bars=2,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
        ),
    )

    assert not out.empty
    assert "structure_confirmed_fvg_top_retest" not in set(out["entry_model"])


def test_bearish_shock_allows_stale_continuation_retest():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [96.0, 96.4, 90.0, 90.5]
    df.loc[26:28, ["open", "high", "low", "close"]] = [92.0, 93.0, 90.0, 91.0]
    df.loc[29, ["open", "high", "low", "close"]] = [95.0, 99.0, 94.0, 94.5]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[25]],
        "regime": ["bear"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=8,
            stale_retest_bars=2,
            continuation_stale_retest_bars=8,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
            include_ema_confirmed_entries=False,
        ),
    )

    assert "structure_confirmed_fvg_top_retest" in set(out["entry_model"])
    assert "bearish" in set(out["shock_state"])


def test_bullish_shock_blocks_short_without_fresh_confirmation():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [97.0, 106.0, 96.5, 105.5]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[24]],
        "regime": ["bear"],
        "bos_down": [True],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=4,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
            include_ema_confirmed_entries=False,
        ),
    )

    assert out.empty


def test_structure_target_uses_causal_swing_low():
    ts = pd.date_range("2026-01-01 15:00", periods=80, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 80,
        "high": [101.0] * 80,
        "low": [99.0] * 80,
        "close": [100.0] * 80,
        "volume": [1.0] * 80,
    })
    df.loc[22, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
    df.loc[23, ["open", "high", "low", "close"]] = [100.0, 100.0, 97.5, 98.0]
    df.loc[24, ["open", "high", "low", "close"]] = [98.0, 98.5, 96.0, 97.0]
    df.loc[25, ["open", "high", "low", "close"]] = [97.0, 99.0, 95.0, 96.0]
    htf_structure = pd.DataFrame({
        "known_after_ts": [ts[24] + pd.Timedelta(minutes=15)],
        "regime": ["bull"],
    })
    entry_structure = pd.DataFrame({
        "known_after_ts": [ts[25]],
        "regime": ["bear"],
        "bos_down": [True],
        "short_target_1": [90.0],
    })

    out = evaluate_bearish_fvg_survivor(
        df,
        symbol="TESTUSDT",
        exchange="binance",
        structure=htf_structure,
        entry_structure=entry_structure,
        config=ExecutionConfig(
            atr_period=3,
            retest_bars=4,
            horizon_bars=8,
            include_raw_entries=False,
            include_structure_confirmed_entries=True,
            target_models=("structure_swing_low",),
        ),
    )

    assert not out.empty
    assert set(out["target_model"]) == {"structure_swing_low"}
    assert set(out["target"]) == {90.0}
