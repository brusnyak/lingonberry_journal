from __future__ import annotations

import pandas as pd

from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.path_setup_lab import (
    PathSetupConfig,
    find_displacement_confirmation,
    primary_frequency_blocker,
    reversal_confirmed,
    select_expansion_exhaustion_calls,
    select_sweep_reclaim_calls,
)
from backtesting.crypto.path_setup_lab import path_stop_target


def test_select_expansion_exhaustion_calls_maps_expected_fade_directions():
    calls = pd.DataFrame({
        "path_context": [
            "expansion_up",
            "expansion_down",
            "sweep_reclaim_long",
            "sweep_reclaim_short",
            "expansion_up",
        ],
        "foundation_state": [
            "range_or_unresolved",
            "local_trend_htf_neutral",
            "range_or_unresolved",
            "confirmed_trend",
            "confirmed_trend",
        ],
    })

    selected = select_expansion_exhaustion_calls(calls, include_sweep_reclaim_long=True)

    assert selected["path_context"].tolist() == ["expansion_up", "expansion_down", "sweep_reclaim_long"]
    assert selected["trade_direction"].tolist() == ["short", "long", "short"]


def test_path_setup_config_defaults_to_expansion_exhaustion_fade():
    cfg = PathSetupConfig()

    assert cfg.setup == "expansion_exhaustion_fade"
    assert cfg.min_rr == 1.5


def test_select_sweep_reclaim_calls_maps_reclaim_direction():
    calls = pd.DataFrame({
        "path_context": ["sweep_reclaim_long", "sweep_reclaim_short", "expansion_up"],
    })

    selected = select_sweep_reclaim_calls(calls)

    assert selected["path_context"].tolist() == ["sweep_reclaim_long", "sweep_reclaim_short"]
    assert selected["trade_direction"].tolist() == ["long", "short"]


def test_path_extreme_stop_places_stop_behind_candle_extreme():
    bars = pd.DataFrame({
        "open": [100.0] * 20,
        "high": [101.0] * 20,
        "low": [99.0] * 20,
        "close": [100.0] * 20,
    })
    atr_values = _atr(bars, 14)

    short_sl, short_tp = path_stop_target(
        bars, 15, "short", entry=100.0, min_rr=1.5, atr_values=atr_values, stop_buffer_atr=0.1
    )
    long_sl, long_tp = path_stop_target(
        bars, 15, "long", entry=100.0, min_rr=1.5, atr_values=atr_values, stop_buffer_atr=0.1
    )

    assert short_sl > 101.0
    assert short_tp < 100.0
    assert long_sl < 99.0
    assert long_tp > 100.0


def test_reversal_confirmed_requires_close_against_signal_direction():
    bars = pd.DataFrame({"close": [100.0, 99.0, 101.0]})

    assert reversal_confirmed(bars, 0, 1, "short") is True
    assert reversal_confirmed(bars, 0, 2, "short") is False
    assert reversal_confirmed(bars, 0, 2, "long") is True
    assert reversal_confirmed(bars, 0, 1, "long") is False


def test_find_displacement_confirmation_requires_directional_body():
    bars = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "high": [101.0, 103.0, 101.0],
        "low": [99.0, 99.5, 97.0],
        "close": [100.0, 102.5, 97.5],
    })
    atr_values = _atr(bars, 1)

    long_i = find_displacement_confirmation(
        bars, 0, "long", atr_values, max_bars=2, displacement_atr=0.25, close_location=0.6
    )
    short_i = find_displacement_confirmation(
        bars, 1, "short", atr_values, max_bars=1, displacement_atr=0.25, close_location=0.6
    )

    assert long_i == 1
    assert short_i == 2


def test_primary_frequency_blocker_orders_tradeable_before_signal_gaps():
    row = pd.Series({
        "portfolio_accepted": 0,
        "pre_portfolio_pass": 1,
        "blocked_cost": 2,
        "setup_signals": 3,
        "raw_events": 4,
    })

    assert primary_frequency_blocker(row) == "portfolio_throttle"
    assert primary_frequency_blocker(pd.Series({"setup_signals": 0, "raw_events": 2})) == "no_setup_signal"
    assert primary_frequency_blocker(pd.Series({"setup_signals": 0, "raw_events": 0})) == "no_raw_event"
