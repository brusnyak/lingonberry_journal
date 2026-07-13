from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.crypto.mtf_cascade_direction import (
    asof_direction,
    ema_only_direction,
    evaluate_direction_series,
    structure_ema_direction,
    vec_ema_state,
)
from backtesting.crypto.synthetic_ohlcv import make_random_walk_series, make_staircase_series


def _resample(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    d = df.set_index("ts")
    r = d.resample(f"{minutes}min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return r.reset_index()


def test_vec_ema_state_matches_manual_bullish_case():
    close = pd.Series(np.linspace(100, 200, 200))
    ohlcv = pd.DataFrame({"close": close})
    states = vec_ema_state(ohlcv)
    # a strictly rising series should end up bullish once EMAs catch up
    assert states.iloc[-1] == "bullish"


def test_asof_direction_is_causal_no_future_leak():
    coarse = pd.DataFrame({
        "ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T04:00Z"]),
        "direction": ["bull", "bear"],
    })
    fine_ts = pd.to_datetime(["2026-01-01T01:00Z", "2026-01-01T03:59Z", "2026-01-01T04:00Z"])
    out = asof_direction(fine_ts, coarse)
    assert list(out) == ["bull", "bull", "bear"]


def test_global_local_cascade_detects_known_trend_on_synthetic_data():
    ohlcv30 = make_staircase_series("up", bars=80000, tf_minutes=30, seed=1)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    result = evaluate_direction_series(ohlcv30.reset_index(drop=True), combo)
    assert result["decided"] > 100
    assert result["direction_accuracy"] > 0.70, result


def test_global_local_cascade_shows_no_edge_on_random_walk():
    ohlcv30 = make_random_walk_series(bars=80000, tf_minutes=30, seed=2)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    result = evaluate_direction_series(ohlcv30.reset_index(drop=True), combo)
    assert result["decided"] > 100
    assert 0.40 < result["direction_accuracy"] < 0.60, result
