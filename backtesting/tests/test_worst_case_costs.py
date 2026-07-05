from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.costs import WorstCaseCryptoCosts


def test_default_round_trip_is_2_percent():
    costs = WorstCaseCryptoCosts()
    assert costs.round_trip_pct == 0.02


def test_long_entry_fills_worse_price_higher():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    fill = costs.entry_fill(100.0, "long")
    assert fill == 101.0  # +1% (half of 2% round trip)


def test_long_exit_fills_worse_price_lower():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    fill = costs.exit_fill(100.0, "long")
    assert fill == 99.0  # -1%


def test_short_entry_fills_worse_price_lower():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    fill = costs.entry_fill(100.0, "short")
    assert fill == 99.0


def test_short_exit_fills_worse_price_higher():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    fill = costs.exit_fill(100.0, "short")
    assert fill == 101.0


def test_exit_adverse_regardless_of_tp_or_sl():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    # A worst-case model doesn't spare winners -- TP exits get hit too.
    tp_fill = costs.exit_fill(100.0, "long", is_sl=False)
    sl_fill = costs.exit_fill(100.0, "long", is_sl=True)
    assert tp_fill == sl_fill == 99.0


def test_round_trip_cost_is_configurable():
    costs = WorstCaseCryptoCosts(round_trip_pct=0.04)
    fill = costs.entry_fill(100.0, "long")
    assert fill == 102.0  # +2% (half of 4%)


def test_full_round_trip_drag_matches_round_trip_pct():
    """A long entered and exited at the same nominal price should show a
    combined loss of ~round_trip_pct (2%), not 2% per leg (4% total)."""
    costs = WorstCaseCryptoCosts(round_trip_pct=0.02)
    entry_fill = costs.entry_fill(100.0, "long")
    exit_fill = costs.exit_fill(100.0, "long")
    total_drag_pct = (entry_fill - exit_fill) / 100.0 * 100
    assert abs(total_drag_pct - 2.0) < 1e-9
