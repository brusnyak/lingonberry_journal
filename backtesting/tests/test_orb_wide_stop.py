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
    s._ltf_up_per_bar = None
    s._pending_dir = {}
    s._retested = {}
    s._hold_count = {}
    s._hold_dir = {}
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


def _bar2(i: int, close: float, high: float, low: float) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=high, low=low,
                   close=close, volume=1, index=i)


def test_retest_no_entry_on_first_breakout():
    s = _strategy()
    s.require_retest = True
    sig = s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())
    assert sig is None
    assert s._pending_dir[0] == 1


def test_retest_no_entry_until_price_touches_back():
    s = _strategy()
    s.require_retest = True
    s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())   # arm pending long
    sig = s.next(_bar2(11, close=107.0, high=107.5, low=106.5), _state())  # still above OR, no touch back
    assert sig is None
    assert s._retested.get(0, False) is False


def test_retest_enters_on_reconfirmation_after_touch():
    s = _strategy()
    s.require_retest = True
    s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())        # arm pending long
    s.next(_bar2(11, close=105.5, high=106.0, low=104.5), _state())        # touches back to or_h=105
    sig = s.next(_bar2(12, close=106.2, high=106.5, low=105.6), _state())  # re-breaks above 105
    assert sig is not None
    assert sig.direction == Direction.LONG


def test_retest_flips_pending_direction_on_opposite_break():
    s = _strategy()
    s.require_retest = True
    s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())  # arm pending long
    s.next(_bar2(11, close=94.0, high=95.5, low=93.5), _state())     # breaks the OTHER side -> flips
    assert s._pending_dir[0] == -1
    assert s._retested.get(0, False) is False


def test_confirm_bars_no_entry_before_hold_met():
    s = _strategy()
    s.confirm_bars = 2
    sig = s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())
    assert sig is None
    assert s._hold_count[0] == 1


def test_confirm_bars_enters_after_hold_met():
    s = _strategy()
    s.confirm_bars = 2
    s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())   # 1st close beyond, hold=1
    sig = s.next(_bar2(11, close=106.3, high=106.8, low=106.0), _state())  # 2nd, hold=2 -> enters
    assert sig is not None
    assert sig.direction == Direction.LONG


def test_confirm_bars_resets_if_price_falls_back_inside_range():
    s = _strategy()
    s.confirm_bars = 2
    s.next(_bar2(10, close=106.0, high=106.5, low=105.5), _state())   # hold=1
    s.next(_bar2(11, close=100.0, high=101.0, low=99.0), _state())    # back inside OR -> resets
    sig = s.next(_bar2(12, close=106.3, high=106.8, low=106.0), _state())  # fresh hold=1, no entry yet
    assert sig is None
