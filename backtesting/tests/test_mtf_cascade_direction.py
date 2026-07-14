from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.crypto.mtf_cascade_direction import (
    CHECKLIST_CRITERIA,
    CascadeConfig,
    asof_direction,
    build_checklist,
    checklist_ablation,
    ema_only_direction,
    evaluate_direction_series,
    evaluate_real_sltp_series,
    null_test_from_checklist,
    null_test_real_sltp,
    rolling_stability,
    rolling_stability_real_sltp,
    sl_tp_geometry,
    structural_stop_target,
    structure_ema_direction,
    structure_trend_bias_direction,
    summarize_checklist,
    sweep_preceded,
    vec_ema_state,
    walk_limit_outcome,
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


def test_asof_direction_returns_neutral_before_first_known_coarse_state():
    coarse = pd.DataFrame({
        "ts": pd.to_datetime(["2026-01-01T04:00Z"]),
        "direction": ["bull"],
    })
    fine_ts = pd.to_datetime(["2026-01-01T00:15Z", "2026-01-01T04:00Z"])

    out = asof_direction(fine_ts, coarse)

    assert list(out) == ["neutral", "bull"]


def test_structure_ema_direction_timestamps_at_availability_not_pivot_bar():
    ohlcv = make_staircase_series("up", bars=120, tf_minutes=240, seed=31)

    direction = structure_ema_direction(ohlcv)

    assert pd.to_datetime(direction["ts"].iloc[0], utc=True) == pd.to_datetime(ohlcv["ts"].iloc[1], utc=True)


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


def test_structure_trend_bias_can_upgrade_neutral_when_indicators_and_swings_agree():
    ohlcv = make_staircase_series("up", bars=500, tf_minutes=240, seed=33)
    # Keep volume explicit so the VWAP branch is exercised.
    ohlcv["volume"] = 1000.0

    direction = structure_trend_bias_direction(ohlcv)

    assert (direction["direction"] == "bull").sum() > 50


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


def test_walk_limit_outcome_rejects_invalid_passive_limit_side():
    bars = pd.DataFrame({
        "close": [100, 100, 100],
        "high": [100, 103, 104],
        "low": [100, 99, 98],
    })

    assert walk_limit_outcome(bars, 0, "long", limit_price=101.0, sl=95.0, tp=110.0) is None
    assert walk_limit_outcome(bars, 0, "short", limit_price=99.0, sl=105.0, tp=90.0) is None


def test_walk_limit_outcome_counts_same_fill_bar_stop_conservatively():
    bars = pd.DataFrame({
        "close": [100, 100, 100],
        "high": [100, 110, 100],
        "low": [100, 94, 100],
    })

    outcome = walk_limit_outcome(
        bars,
        entry_i=0,
        direction="long",
        limit_price=99.0,
        sl=95.0,
        tp=107.0,
        horizon=2,
        track_excursion=True,
    )

    assert outcome["exit_reason"] == "stop"
    assert outcome["r_multiple"] == -1.0
    assert outcome["mfe_r"] > 0
    assert outcome["mae_r"] < 0


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


def test_sweep_preceded_detects_sweep_in_lookback_window():
    structure = pd.DataFrame({
        "sweep_low": [False, False, True, False, False],
        "sweep_high": [False, False, False, False, False],
    })
    assert sweep_preceded(structure, entry_i=4, direction="long", lookback_bars=3) is True
    assert sweep_preceded(structure, entry_i=4, direction="short", lookback_bars=3) is False
    assert sweep_preceded(structure, entry_i=2, direction="long", lookback_bars=1) is False  # sweep is AT i=2, not before it


def test_require_sweep_filters_to_disjoint_subsets():
    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=9)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    from backtesting.features.structure import StructureConfig, build_structure_index
    structure = build_structure_index(ohlcv30.reset_index(drop=True), StructureConfig(left=2, right=2))

    with_sweep = evaluate_real_sltp_series(ohlcv30.reset_index(drop=True), structure, combo, require_sweep=True)
    without_sweep = evaluate_real_sltp_series(ohlcv30.reset_index(drop=True), structure, combo, require_sweep=False)
    baseline = evaluate_real_sltp_series(ohlcv30.reset_index(drop=True), structure, combo)
    # the two filtered subsets should partition the baseline (no overlap, no gain)
    assert with_sweep["n"] + without_sweep["n"] == baseline["n"]


def test_sl_tp_geometry_returns_one_row_per_entry_with_expected_columns():
    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=11)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    from backtesting.features.structure import StructureConfig, build_structure_index
    structure = build_structure_index(ohlcv30.reset_index(drop=True), StructureConfig(left=2, right=2))

    geo = sl_tp_geometry(ohlcv30.reset_index(drop=True), structure, combo)
    assert not geo.empty
    assert {"stop_pct", "target_pct", "planned_rr", "stop_atr_mult"}.issubset(geo.columns)
    assert (geo["stop_pct"] > 0).all()
    assert (geo["planned_rr"] >= 1.49).all()  # min_rr floor is 1.5, small float slack


def test_stop_pct_range_filter_narrows_to_subset():
    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=11)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    from backtesting.features.structure import StructureConfig, build_structure_index
    structure = build_structure_index(ohlcv30.reset_index(drop=True), StructureConfig(left=2, right=2))
    bars = ohlcv30.reset_index(drop=True)

    baseline = evaluate_real_sltp_series(bars, structure, combo)
    geo = sl_tp_geometry(bars, structure, combo)
    lo, hi = geo["stop_pct"].quantile(0.25), geo["stop_pct"].quantile(0.75)
    filtered = evaluate_real_sltp_series(bars, structure, combo, stop_pct_range=(lo, hi))
    assert 0 < filtered["n"] < baseline["n"]


def _build_synth_checklist_inputs(seed: int = 21):
    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=seed)
    ohlcv240 = _resample(ohlcv30, 240)
    dir_global = structure_ema_direction(ohlcv240)
    dir_local = structure_ema_direction(ohlcv30)
    g = asof_direction(ohlcv30["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    from backtesting.features.structure import StructureConfig, build_structure_index
    bars = ohlcv30.reset_index(drop=True)
    structure = build_structure_index(bars, StructureConfig(left=2, right=2))
    return bars, structure, combo


def test_build_checklist_returns_expected_columns_and_valid_flags():
    bars, structure, combo = _build_synth_checklist_inputs()
    checklist = build_checklist(bars, structure, combo)
    assert not checklist.empty
    assert set(CHECKLIST_CRITERIA).issubset(checklist.columns)
    assert {"idx", "r_multiple", "hit", "stop_atr_mult"}.issubset(checklist.columns)
    for c in CHECKLIST_CRITERIA:
        assert checklist[c].dtype == bool


def test_summarize_checklist_filters_to_all_criteria_true():
    checklist = pd.DataFrame({
        "idx": [0, 1, 2, 3],
        "r_multiple": [2.0, -1.0, 1.5, -1.0],
        "flag_a": [True, True, False, True],
        "flag_b": [True, False, True, True],
    })
    baseline = summarize_checklist(checklist, [])
    assert baseline["n"] == 4
    only_a = summarize_checklist(checklist, ["flag_a"])
    assert only_a["n"] == 3  # idx 0,1,3
    both = summarize_checklist(checklist, ["flag_a", "flag_b"])
    assert both["n"] == 2  # idx 0,3 -- both true


def test_null_test_from_checklist_shows_no_edge_on_random_walk():
    from unittest.mock import patch

    ohlcv30 = make_random_walk_series(bars=30000, tf_minutes=30, seed=7)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_random_walk_series(bars=30000 * 6, tf_minutes=5, seed=7)

    def fake_load_crypto(symbol, tf, days, exchange, source):
        return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}[tf]

    with patch("backtesting.crypto.mtf_cascade_direction.load_crypto", fake_load_crypto):
        from backtesting.crypto.mtf_cascade_direction import build_global_local_series
        bars, structure, combo = build_global_local_series("SYNTH", CascadeConfig())

    checklist = build_checklist(bars, structure, combo)
    result = null_test_from_checklist(bars, structure, checklist, n_seeds=5)
    assert 10 < result["percentile"] < 90, result  # not a decisive edge on pure noise


def test_checklist_ablation_rows_are_baseline_plus_each_criterion_plus_combined():
    from unittest.mock import patch

    ohlcv30 = make_staircase_series("up", bars=30000, tf_minutes=30, seed=25)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_staircase_series("up", bars=30000 * 6, tf_minutes=5, seed=25)

    def fake_load_crypto(symbol, tf, days, exchange, source):
        return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}[tf]

    with patch("backtesting.crypto.mtf_cascade_direction.load_crypto", fake_load_crypto):
        result = checklist_ablation("SYNTH", CascadeConfig(), stage="global_local", n_seeds=5)

    assert not result.empty
    expected_labels = {"baseline"} | set(CHECKLIST_CRITERIA) | {"all_combined"}
    assert set(result["criterion"]) == expected_labels
    baseline_n = result.loc[result["criterion"] == "baseline", "n"].iat[0]
    # every filtered criterion is a subset of the baseline candidate set
    assert (result.loc[result["criterion"] != "baseline", "n"] <= baseline_n).all()
