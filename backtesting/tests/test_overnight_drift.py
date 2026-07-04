from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl2_overnight_drift.overnight_drift import OvernightDrift


def _strategy() -> OvernightDrift:
    s = OvernightDrift()
    n = 20
    s._n = n
    s._day_ord = np.zeros(n, dtype=int)
    s._entry_ok = np.full(n, True)
    s._exit_ok = np.full(n, False)
    s._atr = np.full(n, 2.0)
    s._htf_up_per_bar = None
    s._last_entry_day = -1
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=close + 1,
                   low=close - 1, close=close, volume=1, index=i)


def _state() -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=[], closed_trades=[], bar_index=10)


def test_always_goes_long():
    s = _strategy()
    sig = s.next(_bar(), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 100.0 - 2.0 * 2.0


def test_one_entry_per_close_day():
    s = _strategy()
    assert s.next(_bar(i=10), _state()) is not None
    assert s.next(_bar(i=11), _state()) is None


def test_no_entry_outside_close_window():
    s = _strategy()
    s._entry_ok[10] = False
    assert s.next(_bar(i=10), _state()) is None


def test_exits_at_next_session_open():
    s = _strategy()
    s._exit_ok[15] = True
    assert s.should_close(object(), _bar(i=15), _state()) is True
    assert s.should_close(object(), _bar(i=10), _state()) is False


def _structure_strategy() -> OvernightDrift:
    s = _strategy()
    s.stop_mode = "structure"
    n = s._n
    s._last_hl = np.full(n, np.nan)
    s._last_ll = np.full(n, np.nan)
    return s


def test_structure_stop_uses_last_hl_minus_buffer():
    s = _structure_strategy()
    s._last_hl[10] = 95.0
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 95.0 - 0.1 * 2.0


def test_structure_stop_falls_back_to_atr_when_no_swing():
    s = _structure_strategy()
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 100.0 - 2.0 * 2.0


def test_structure_stop_falls_back_when_swing_above_price():
    s = _structure_strategy()
    s._last_hl[10] = 101.0
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 100.0 - 2.0 * 2.0
