from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop


def _strategy() -> OrbNyWideStop:
    s = OrbNyWideStop()
    n = 20
    s._n = n
    s._htf_up_per_bar = None
    s._vol_ok_per_bar = None
    s._day_ord = np.zeros(n, dtype=int)
    s._or_high = np.full(n, 105.0)
    s._or_low = np.full(n, 95.0)
    s._entry_ok = np.full(n, True)
    s._eod = np.full(n, False)
    s._last_trade_day = -1
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=close + 1,
                   low=close - 1, close=close, volume=1, index=i)


def _state() -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=[], closed_trades=[], bar_index=10)


def test_stop_is_opposite_side_of_range_not_midpoint():
    sig = _strategy().next(_bar(close=106.0), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 95.0  # opposite side of range, not the 100.0 midpoint


def test_target_is_ten_times_risk():
    s = _strategy()
    sig = s.next(_bar(close=106.0), _state())
    risk = 106.0 - 95.0
    assert sig.tp1 == 106.0 + 10 * risk


def test_short_stop_at_range_high():
    sig = _strategy().next(_bar(close=94.0), _state())
    assert sig.direction == Direction.SHORT
    assert sig.sl == 105.0


def test_one_trade_per_day_still_enforced():
    s = _strategy()
    assert s.next(_bar(i=10, close=106.0), _state()) is not None
    assert s.next(_bar(i=11, close=106.0), _state()) is None
