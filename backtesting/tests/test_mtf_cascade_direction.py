from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.crypto.mtf_cascade_direction import (
    CascadeConfig,
    asof_direction,
    ema_only_direction,
    evaluate_direction_series,
    null_test_real_sltp,
    rolling_stability,
    rolling_stability_real_sltp,
    structural_stop_target,
    structure_ema_direction,
    vec_ema_state,
    walk_structural_outcome,
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


def test_rolling_stability_returns_one_row_per_window_with_no_gaps():
    from unittest.mock import patch

    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=5)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_staircase_series("up", bars=30000 * 6, tf_minutes=5, seed=5)

    def fake_load_crypto(symbol, tf, days, exchange, source):
        return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}[tf]

    with patch("backtesting.crypto.mtf_cascade_direction.load_crypto", fake_load_crypto):
        result = rolling_stability("SYNTH", window_days=30, step_days=15, config=CascadeConfig())

    assert not result.empty
    assert (result["window_end"] - result["window_start"]).dt.days.eq(30).all()
    # windows should tile forward without gaps between consecutive starts
    starts = result["window_start"].sort_values().reset_index(drop=True)
    assert (starts.diff().dropna().dt.days == 15).all()


def test_structural_stop_target_matches_propfirmstructurev1_fallback_pattern():
    row = pd.Series({"long_structural_sl": 95.0, "last_swing_low": 90.0, "long_target_1": 110.0})
    sl, tp = structural_stop_target(row, "long", entry=100.0, min_rr=1.5)
    assert sl == 95.0  # structural level preferred over last_swing_low fallback
    assert tp == 110.0  # 2R structural target beats the 1.5R floor (107.5)

    # target closer than the min_rr floor -- floor wins
    row2 = pd.Series({"long_structural_sl": 95.0, "long_target_1": 101.0})
    sl2, tp2 = structural_stop_target(row2, "long", entry=100.0, min_rr=1.5)
    assert tp2 == 107.5


def test_walk_structural_outcome_hits_target_before_stop():
    bars = pd.DataFrame({
        "close": [100, 100, 100, 100],
        "high": [100, 110, 100, 100],
        "low": [100, 100, 100, 100],
    })
    outcome = walk_structural_outcome(bars, entry_i=0, direction="long", sl=95.0, tp=108.0, horizon=3)
    assert outcome["hit"] is True
    assert outcome["r_multiple"] > 0


def test_rolling_stability_real_sltp_returns_tiled_windows():
    from unittest.mock import patch

    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=5)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_staircase_series("up", bars=30000 * 6, tf_minutes=5, seed=5)

    def fake_load_crypto(symbol, tf, days, exchange, source):
        return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}[tf]

    with patch("backtesting.crypto.mtf_cascade_direction.load_crypto", fake_load_crypto):
        result = rolling_stability_real_sltp("SYNTH", window_days=30, step_days=15, config=CascadeConfig())

    assert not result.empty
    assert {"win_rate", "avg_r", "pf"}.issubset(result.columns)
    assert (result["window_end"] - result["window_start"]).dt.days.eq(30).all()


def test_null_test_real_sltp_shows_no_edge_on_random_walk():
    from unittest.mock import patch

    ohlcv30 = make_random_walk_series(bars=30000, tf_minutes=30, seed=7)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_random_walk_series(bars=30000 * 6, tf_minutes=5, seed=7)

    def fake_load_crypto(symbol, tf, days, exchange, source):
        return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}[tf]

    with patch("backtesting.crypto.mtf_cascade_direction.load_crypto", fake_load_crypto):
        from backtesting.crypto.mtf_cascade_direction import build_global_local_series
        bars, structure, combo = build_global_local_series("SYNTH", CascadeConfig())

    result = null_test_real_sltp(bars, structure, combo, n_seeds=5)
    assert 10 < result["percentile"] < 90, result  # not a decisive edge on pure noise
