from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl2_orb.orb import OrbNy


def _strategy() -> OrbNy:
    s = OrbNy()
    n = 20
    s._n = n
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


def test_orb_no_signal_inside_range():
    assert _strategy().next(_bar(close=100.0), _state()) is None


def test_orb_long_on_break_above_stop_at_mid():
    sig = _strategy().next(_bar(close=106.0), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 100.0  # range midpoint


def test_orb_short_on_break_below():
    sig = _strategy().next(_bar(close=94.0), _state())
    assert sig is not None
    assert sig.direction == Direction.SHORT
    assert sig.sl == 100.0


def test_orb_one_trade_per_day():
    s = _strategy()
    assert s.next(_bar(i=10, close=106.0), _state()) is not None
    assert s.next(_bar(i=11, close=106.0), _state()) is None


def test_orb_skips_days_without_full_opening_range():
    s = _strategy()
    s._or_high[:] = np.nan
    assert s.next(_bar(close=106.0), _state()) is None


def test_orb_flat_at_eod():
    s = _strategy()
    s._eod[10] = True
    assert s.should_close(object(), _bar(i=10), _state()) is True
