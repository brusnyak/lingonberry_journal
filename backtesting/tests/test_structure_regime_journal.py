from __future__ import annotations

import pandas as pd

from backtesting.crypto.structure_regime_journal import (
    average_true_range,
    classify_mtf_mode,
    compression_bucket,
    price_action_snapshot,
    range_atr_ratio,
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
