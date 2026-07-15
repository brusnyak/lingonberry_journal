from __future__ import annotations

import pandas as pd

from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.path_setup_lab import PathSetupConfig, reversal_confirmed, select_expansion_exhaustion_calls
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
