"""Validate the structure/direction measurement harness on synthetic ground truth.

If the harness can't detect a known, planted trend in synthetic data, the harness
is broken and any null result on real data is not trustworthy yet. This is a
sanity gate on the measurement tool, not a claim about real markets.
"""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.synthetic_ohlcv import make_random_walk_series, make_staircase_series
from backtesting.features.structure import StructureConfig, build_structure_index
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.structure_direction_accuracy import _regime_transitions, _walk_outcome


def _measure_accuracy(ohlcv: pd.DataFrame, horizon: int = 48, left: int = 2, right: int = 2) -> dict:
    structure = build_structure_index(ohlcv, StructureConfig(left=left, right=right))
    structure["known_after_ts"] = pd.to_datetime(structure["known_after_ts"], utc=True)
    transitions = _regime_transitions(structure)
    atr = _atr(ohlcv, 14)
    outcomes = []
    for _, srow in transitions.iterrows():
        idx = ohlcv["ts"].searchsorted(srow["known_after_ts"], side="right")
        if idx >= len(ohlcv) - 1:
            continue
        atr_now = atr.iat[idx] if idx < len(atr) else float("nan")
        if not (atr_now > 0):
            continue
        direction = "long" if srow["regime"] == "bull" else "short"
        outcomes.append(_walk_outcome(ohlcv, idx, direction, atr_now, atr_now, horizon))
    n = len(outcomes)
    wins = outcomes.count("win")
    losses = outcomes.count("loss")
    decided = wins + losses
    return {
        "n_calls": n,
        "decided": decided,
        "direction_accuracy": wins / decided if decided else float("nan"),
    }


def test_harness_detects_known_uptrend_at_wide_pivot_window():
    # left=2/right=2 (the project-wide default) is too noise-sensitive to
    # cleanly characterize even a known planted trend (measured ~57%, see
    # CLEAN.md) -- left=8/right=8 is what actually recovers a strong signal.
    # This test locks in that empirical finding as a regression check.
    ohlcv = make_staircase_series("up", bars=20000, seed=1)
    result = _measure_accuracy(ohlcv, left=8, right=8)
    assert result["decided"] >= 10, "too few resolved calls to judge accuracy"
    assert result["direction_accuracy"] > 0.70, result


def test_harness_detects_known_downtrend_at_wide_pivot_window():
    ohlcv = make_staircase_series("down", bars=20000, seed=2)
    result = _measure_accuracy(ohlcv, left=8, right=8)
    assert result["decided"] >= 10, "too few resolved calls to judge accuracy"
    assert result["direction_accuracy"] > 0.70, result


def test_harness_shows_no_edge_on_pure_random_walk():
    ohlcv = make_random_walk_series(bars=20000, seed=3)
    result = _measure_accuracy(ohlcv, left=8, right=8)
    assert result["decided"] >= 20, "too few resolved calls to judge accuracy"
    assert 0.35 < result["direction_accuracy"] < 0.65, result


def test_default_pivot_window_is_noticeably_weaker_than_wide_window():
    # Documents the actual project-wide default's behavior so nobody assumes
    # left=2/right=2 gives the same fidelity as a wider, less noise-sensitive
    # pivot window -- it measurably doesn't, on the same known trend.
    ohlcv = make_staircase_series("up", bars=20000, seed=1)
    narrow = _measure_accuracy(ohlcv, left=2, right=2)
    wide = _measure_accuracy(ohlcv, left=8, right=8)
    assert wide["direction_accuracy"] > narrow["direction_accuracy"]
