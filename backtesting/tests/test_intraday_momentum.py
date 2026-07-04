from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl2_intraday_momentum.intraday_momentum import IntradayMomentum


def _strategy() -> IntradayMomentum:
    s = IntradayMomentum()
    n = 20
    s._n = n
    s._day_ord = np.zeros(n, dtype=int)
    s._signal_per_day = np.array([1])
    s._entry_ok = np.full(n, True)
    s._eod = np.full(n, False)
    s._atr = np.full(n, 2.0)
    s._last_trade_day = -1
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=close + 1,
                   low=close - 1, close=close, volume=1, index=i)


def _state() -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=[], closed_trades=[], bar_index=10)


def test_positive_first_window_goes_long():
    s = _strategy()
    sig = s.next(_bar(), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 100.0 - 1.5 * 2.0


def test_negative_first_window_goes_short():
    s = _strategy()
    s._signal_per_day = np.array([-1])
    sig = s.next(_bar(), _state())
    assert sig.direction == Direction.SHORT
    assert sig.sl == 100.0 + 1.5 * 2.0


def test_flat_first_window_no_trade():
    s = _strategy()
    s._signal_per_day = np.array([0])
    assert s.next(_bar(), _state()) is None


def test_one_trade_per_day():
    s = _strategy()
    assert s.next(_bar(i=10), _state()) is not None
    assert s.next(_bar(i=11), _state()) is None


def test_flat_at_eod():
    s = _strategy()
    s._eod[10] = True
    assert s.should_close(object(), _bar(i=10), _state()) is True


def _structure_strategy() -> IntradayMomentum:
    s = _strategy()
    s.stop_mode = "structure"
    n = s._n
    s._last_hl = np.full(n, np.nan)
    s._last_ll = np.full(n, np.nan)
    s._last_lh = np.full(n, np.nan)
    s._last_hh = np.full(n, np.nan)
    return s


def test_structure_stop_long_uses_last_hl_minus_buffer():
    s = _structure_strategy()
    s._last_hl[10] = 95.0
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 95.0 - 0.1 * 2.0  # structure_buffer_atr=0.1, atr=2.0


def test_structure_stop_short_uses_last_lh_plus_buffer():
    s = _structure_strategy()
    s._signal_per_day = np.array([-1])
    s._last_lh[10] = 105.0
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 105.0 + 0.1 * 2.0


def test_structure_stop_falls_back_to_atr_when_no_swing_available():
    s = _structure_strategy()
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 100.0 - 1.5 * 2.0  # ATR fallback, same as default stop_atr_mult


def test_structure_stop_falls_back_when_swing_is_wrong_side_of_price():
    s = _structure_strategy()
    s._last_hl[10] = 101.0  # above entry price -- not a usable stop for a long
    sig = s.next(_bar(close=100.0), _state())
    assert sig.sl == 100.0 - 1.5 * 2.0
