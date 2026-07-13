from __future__ import annotations

import pandas as pd

from backtesting.crypto.structure_direction_accuracy import _regime_transitions, _walk_outcome


def test_regime_transitions_dedupes_persistent_regime():
    structure = pd.DataFrame({
        "known_after_ts": pd.date_range("2026-01-01", periods=6, freq="4h", tz="UTC"),
        "regime": ["neutral", "bull", "bull", "bull", "bear", "bear"],
    })
    out = _regime_transitions(structure)
    assert list(out["regime"]) == ["bull", "bear"]


def test_walk_outcome_detects_win_and_loss_and_expiry():
    ohlcv = pd.DataFrame({
        "ts": pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
        "open": [100, 100, 100, 100, 100],
        "high": [100, 103, 100, 100, 100],
        "low": [100, 99, 100, 100, 100],
        "close": [100, 100, 100, 100, 100],
    })
    # long, target hit at bar 1 (high=103 >= 100+2)
    assert _walk_outcome(ohlcv, entry_i=0, direction="long", stop_dist=2, target_dist=2, horizon=3) == "win"
    # short, stop hit at bar 1 (high=103 >= 100+2)
    assert _walk_outcome(ohlcv, entry_i=0, direction="short", stop_dist=2, target_dist=2, horizon=3) == "loss"
    # tiny horizon with flat bars afterward -> expiry
    flat = pd.DataFrame({
        "ts": pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC"),
        "open": [100] * 5, "high": [100.1] * 5, "low": [99.9] * 5, "close": [100] * 5,
    })
    assert _walk_outcome(flat, entry_i=0, direction="long", stop_dist=5, target_dist=5, horizon=3) == "expiry"
