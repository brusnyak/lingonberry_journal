"""Tests for causal crypto direction/confirmation filters."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.direction_layer import (
    DirectionLayerConfig,
    has_direction_confirmation,
    has_opposing_spike,
    structure_at,
)


def test_structure_at_uses_known_after_not_future_pivot_context():
    structure = pd.DataFrame({
        "known_after_ts": pd.to_datetime(["2026-01-01 00:10Z", "2026-01-01 00:20Z"]),
        "swing_ts": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:05Z"]),
        "regime": ["bear", "future_bull"],
    })

    row = structure_at(structure, pd.Timestamp("2026-01-01 00:15Z"))

    assert row is not None
    assert row["regime"] == "bear"


def test_direction_confirmation_rejects_future_structure_event():
    structure = pd.DataFrame({
        "known_after_ts": pd.to_datetime(["2026-01-01 00:30Z"]),
        "regime": ["bear"],
        "bos_down": [True],
    })

    ok, reason, confirmation_ts = has_direction_confirmation(
        structure,
        direction="short",
        signal_ts=pd.Timestamp("2026-01-01 00:10Z"),
        entry_ts=pd.Timestamp("2026-01-01 00:15Z"),
        bar_delta=pd.Timedelta(minutes=5),
    )

    assert not ok
    assert reason == "no_known_structure"
    assert pd.isna(confirmation_ts)


def test_direction_confirmation_accepts_recent_bearish_break():
    structure = pd.DataFrame({
        "known_after_ts": pd.to_datetime(["2026-01-01 00:05Z", "2026-01-01 00:15Z"]),
        "regime": ["neutral", "neutral"],
        "bos_down": [False, True],
    })

    ok, reason, confirmation_ts = has_direction_confirmation(
        structure,
        direction="short",
        signal_ts=pd.Timestamp("2026-01-01 00:10Z"),
        entry_ts=pd.Timestamp("2026-01-01 00:20Z"),
        bar_delta=pd.Timedelta(minutes=5),
        config=DirectionLayerConfig(confirmation_window_bars=3),
    )

    assert ok
    assert reason == "bos_down"
    assert confirmation_ts == pd.Timestamp("2026-01-01 00:15Z")


def test_opposing_spike_blocks_short_after_bullish_displacement():
    ts = pd.date_range("2026-01-01", periods=6, freq="5min", tz="UTC")
    data = pd.DataFrame({
        "ts": ts,
        "open": [100, 100, 100, 100, 100, 100],
        "high": [101, 101, 101, 106, 101, 101],
        "low": [99, 99, 99, 99, 99, 99],
        "close": [100, 100, 100, 105.5, 100, 100],
    })
    atr = pd.Series([2.0] * len(data))

    blocked, reason = has_opposing_spike(
        data,
        direction="short",
        entry_i=4,
        atr=atr,
        config=DirectionLayerConfig(opposing_spike_lookback_bars=2, opposing_spike_atr=2.0),
    )

    assert blocked
    assert reason == "bullish_opposing_spike"
