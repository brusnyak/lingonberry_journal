from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.crypto.synthetic_ohlcv import make_staircase_series
from backtesting.crypto.structure_regime_journal import (
    average_true_range,
    classify_consolidation_state,
    classify_foundation_state,
    classify_mtf_mode,
    compression_bucket,
    directional_movement_index,
    price_action_snapshot,
    range_atr_ratio,
    trend_strength_bucket,
)
from backtesting.crypto.direction_layer import structure_at


def test_mtf_mode_marks_pullback_inside_higher_timeframe_uptrend():
    mode = classify_mtf_mode(
        direction="long",
        local_regime="bear",
        middle_regime="bull",
        context_regime="bull",
        local_label="LL",
    )

    assert mode == "pullback_in_uptrend"


def test_mtf_mode_marks_pullback_inside_higher_timeframe_downtrend():
    mode = classify_mtf_mode(
        direction="short",
        local_regime="bull",
        middle_regime="bear",
        context_regime="bear",
        local_label="HH",
    )

    assert mode == "pullback_in_downtrend"


def test_mtf_mode_marks_countertrend_when_middle_and_context_oppose_direction():
    mode = classify_mtf_mode(
        direction="long",
        local_regime="bull",
        middle_regime="bear",
        context_regime="bear",
    )

    assert mode == "countertrend"


def test_mtf_mode_marks_range_when_higher_timeframe_is_neutral():
    mode = classify_mtf_mode(
        direction="long",
        local_regime="bull",
        middle_regime="neutral",
        context_regime="bull",
    )

    assert mode == "range_or_transition"


def test_mtf_mode_marks_conflict_when_middle_and_context_disagree():
    mode = classify_mtf_mode(
        direction="short",
        local_regime="bear",
        middle_regime="bull",
        context_regime="bear",
    )

    assert mode == "conflict"


def test_structure_lookup_uses_known_after_for_mtf_journal_inputs():
    structure = pd.DataFrame({
        "known_after_ts": pd.to_datetime(["2026-01-01 00:10Z", "2026-01-01 00:30Z"]),
        "swing_ts": pd.to_datetime(["2026-01-01 00:05Z", "2026-01-01 00:00Z"]),
        "regime": ["bear", "bull"],
    })

    row = structure_at(structure, pd.Timestamp("2026-01-01 00:20Z"))

    assert row is not None
    assert row["regime"] == "bear"


def test_compression_bucket_boundaries():
    assert compression_bucket(1.9) == "compressed"
    assert compression_bucket(3.0) == "normal"
    assert compression_bucket(6.0) == "expanded"


def test_trend_strength_bucket_boundaries():
    assert trend_strength_bucket(10) == "weak_or_range"
    assert trend_strength_bucket(22) == "transition"
    assert trend_strength_bucket(30) == "trend"
    assert trend_strength_bucket(45) == "strong_trend"


def test_consolidation_state_splits_range_from_transition():
    assert classify_consolidation_state(
        compression_state="compressed",
        trend_strength="weak_or_range",
        pre_range_atr_16=1.8,
    ) == "tight_range"
    assert classify_consolidation_state(
        compression_state="compressed",
        trend_strength="transition",
        pre_range_atr_16=2.1,
    ) == "coiling_transition"
    assert classify_consolidation_state(
        compression_state="expanded",
        trend_strength="weak_or_range",
        pre_range_atr_16=6.0,
    ) == "volatile_range"


def test_foundation_state_does_not_treat_range_as_directional_trend():
    assert classify_foundation_state(
        mtf_mode="range_or_transition",
        consolidation_state="tight_range",
        trend_strength="weak_or_range",
    ) == "consolidation"
    assert classify_foundation_state(
        mtf_mode="pullback_in_uptrend",
        consolidation_state="directional",
        trend_strength="trend",
    ) == "directional_trend"
    assert classify_foundation_state(
        mtf_mode="countertrend",
        consolidation_state="directional",
        trend_strength="trend",
    ) == "countertrend_risk"


def test_directional_movement_index_marks_synthetic_trend_stronger_than_range():
    ts = pd.date_range("2026-01-01", periods=80, freq="15min", tz="UTC")
    trend_close = [100 + i * 0.4 for i in range(80)]
    trend = pd.DataFrame({
        "ts": ts,
        "open": trend_close,
        "high": [p + 0.3 for p in trend_close],
        "low": [p - 0.2 for p in trend_close],
        "close": trend_close,
    })
    range_close = [100 + (0.2 if i % 2 else -0.2) for i in range(80)]
    ranging = pd.DataFrame({
        "ts": ts,
        "open": range_close,
        "high": [p + 0.3 for p in range_close],
        "low": [p - 0.3 for p in range_close],
        "close": range_close,
    })

    trend_adx = directional_movement_index(trend, 14)["adx"].iloc[-1]
    range_adx = directional_movement_index(ranging, 14)["adx"].iloc[-1]

    assert trend_adx > 25
    assert range_adx < trend_adx


def test_price_action_snapshot_flags_opposing_shock_before_long_entry():
    ts = pd.date_range("2026-01-01", periods=24, freq="15min", tz="UTC")
    close = [100.0] * 24
    data = pd.DataFrame({
        "ts": ts,
        "open": close,
        "high": [101.0] * 24,
        "low": [99.0] * 24,
        "close": close,
    })
    data.loc[20, ["open", "high", "low", "close"]] = [100.0, 100.5, 94.0, 94.2]

    snap = price_action_snapshot(data, entry_ts=ts[22], direction="long")

    assert snap["shock_state"] == "bearish_shock"
    assert snap["shock_alignment"] == "opposing_shock"
    assert snap["entry_hour_utc"] == 5
    assert "trend_strength" in snap
    assert "consolidation_state" in snap


def test_price_action_snapshot_separates_synthetic_trend_from_chop():
    trend = make_staircase_series("up", bars=240, tf_minutes=15, seed=101, noise_std_pct=0.0002)
    chop_ts = pd.date_range("2024-01-01", periods=240, freq="15min", tz="UTC")
    chop_close = 100.0 + np.sin(np.arange(240) / 2.0) * 0.10
    chop_open = np.roll(chop_close, 1)
    chop_open[0] = chop_close[0]
    chop = pd.DataFrame({
        "ts": chop_ts,
        "open": chop_open,
        "high": np.maximum(chop_open, chop_close) + 0.40,
        "low": np.minimum(chop_open, chop_close) - 0.40,
        "close": chop_close,
        "volume": 1.0,
    })

    trend_snap = price_action_snapshot(trend, entry_ts=trend["ts"].iloc[-1], direction="long")
    chop_snap = price_action_snapshot(chop, entry_ts=chop["ts"].iloc[-1], direction="long")

    assert trend_snap["trend_strength"] in {"trend", "strong_trend"}
    assert chop_snap["trend_strength"] in {"weak_or_range", "transition"}
    assert trend_snap["consolidation_state"] != "tight_range"


def test_range_atr_ratio_uses_only_past_window():
    ts = pd.date_range("2026-01-01", periods=20, freq="15min", tz="UTC")
    data = pd.DataFrame({
        "ts": ts,
        "open": [100.0] * 20,
        "high": [101.0] * 20,
        "low": [99.0] * 20,
        "close": [100.0] * 20,
    })
    data.loc[19, "high"] = 130.0
    atr = average_true_range(data.iloc[:19].copy(), 14)

    ratio = range_atr_ratio(data.iloc[:19].copy(), atr, 18, 8)

    assert ratio < 2.0
