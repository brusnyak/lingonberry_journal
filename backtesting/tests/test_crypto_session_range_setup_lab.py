from __future__ import annotations

import pandas as pd

from backtesting.crypto.session_range_setup_lab import (
    SessionRangeConfig,
    apply_feature_filter,
    candidate_passes_filters,
    output_suffix,
    parse_csv_tuple,
    primary_session_blocker,
    reference_direction,
    session_range_signal,
    summarize_feature_bucket,
)


def test_session_range_signal_breakout_direction():
    assert session_range_signal(
        mode="breakout",
        close=102.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "long"
    assert session_range_signal(
        mode="breakout",
        close=94.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "short"


def test_session_range_signal_fakeout_requires_sweep_and_mid_reclaim():
    assert session_range_signal(
        mode="fakeout",
        close=97.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "short"
    assert session_range_signal(
        mode="fakeout",
        close=98.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) is None


def test_reference_direction_requires_body_and_edge_close():
    ref = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [104.0, 105.0],
            "low": [99.0, 100.0],
            "close": [102.0, 104.5],
        }
    )
    cfg = SessionRangeConfig(reference_close_location_threshold=0.7, min_reference_body_atr=0.5)

    assert reference_direction(ref, ref_high=105.0, ref_low=99.0, atr=5.0, cfg=cfg) == "long"

    weak_body = ref.copy()
    weak_body.loc[1, "close"] = 101.0
    assert reference_direction(weak_body, ref_high=105.0, ref_low=99.0, atr=5.0, cfg=cfg) is None


def test_session_range_signal_continuation_uses_reference_bias():
    assert session_range_signal(
        mode="continuation",
        close=102.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
        reference_bias="long",
    ) == "long"
    assert session_range_signal(
        mode="continuation",
        close=102.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
        reference_bias="short",
    ) is None


def test_session_range_signal_reversal_fades_reference_bias_after_sweep_reclaim():
    assert session_range_signal(
        mode="reversal",
        close=97.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
        reference_bias="long",
    ) == "short"
    assert session_range_signal(
        mode="reversal",
        close=97.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
        reference_bias="long",
    ) is None
    assert session_range_signal(
        mode="reversal",
        close=97.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
        reference_bias="short",
    ) is None


def test_output_suffix_records_session_range_config():
    cfg = SessionRangeConfig(
        setup="ny_london_breakout",
        min_reference_range_atr=1.0,
        max_reference_range_atr=4.0,
        stress_round_trip_pct=0.004,
    )

    suffix = output_suffix(cfg)

    assert "ny_london_breakout" in suffix
    assert "ref1-4" in suffix
    assert "stressfee0p004" in suffix


def test_candidate_passes_filters_rejects_cost_before_day_slot():
    cfg = SessionRangeConfig(max_stress_cost_r=0.25)

    assert candidate_passes_filters({"stress_cost_r": 0.2}, cfg)
    assert not candidate_passes_filters({"stress_cost_r": 0.3}, cfg)


def test_primary_session_blocker_uses_session_range_stages():
    assert primary_session_blocker(pd.Series({"pre_portfolio_pass": 1})) == "pre_portfolio_pass"
    assert primary_session_blocker(pd.Series({"blocked_cost": 1})) == "blocked_cost"
    assert primary_session_blocker(pd.Series({"signal_attempts": 0, "reference_bars": 4, "trade_bars": 4, "reference_range_atr": 1.0})) == "no_sweep"


def test_primary_session_blocker_respects_custom_reference_range():
    cfg = SessionRangeConfig(min_reference_range_atr=1.5, max_reference_range_atr=4.0)

    blocker = primary_session_blocker(
        pd.Series({"signal_attempts": 0, "reference_bars": 4, "trade_bars": 4, "reference_range_atr": 1.0}),
        cfg,
    )

    assert blocker == "reference_range_too_small"


def test_summarize_feature_bucket_keeps_missing_bucket():
    trades = pd.DataFrame(
        {
            "reference_bias": ["long", "", None],
            "stress_net_r": [1.0, -1.0, 0.5],
            "stop_pct": [1.0, 2.0, 3.0],
        }
    )

    summary = summarize_feature_bucket(trades, "reference_bias")

    assert set(summary["reference_bias"]) == {"long", "missing"}
    missing = summary[summary["reference_bias"].eq("missing")].iloc[0]
    assert int(missing["trades"]) == 2


def test_apply_feature_filter_treats_blank_as_missing():
    trades = pd.DataFrame({"reference_bias": ["long", "", None], "stress_net_r": [1.0, -1.0, 0.5]})

    filtered = apply_feature_filter(trades, "reference_bias", ("missing",))

    assert len(filtered) == 2


def test_output_suffix_records_feature_filters():
    cfg = SessionRangeConfig(reference_biases=("missing", "short"), first_trade_hour_directions=("up", "down", "flat"))

    suffix = output_suffix(cfg)

    assert "refbias-missing-short" in suffix
    assert "firsthour-up-down-flat" in suffix


def test_parse_csv_tuple_returns_none_for_empty_input():
    assert parse_csv_tuple("") is None
    assert parse_csv_tuple("up, down") == ("up", "down")
