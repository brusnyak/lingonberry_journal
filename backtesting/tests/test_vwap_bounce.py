from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl2_vwap_bounce.vwap_bounce import VwapBounce


def _strategy() -> VwapBounce:
    s = VwapBounce()
    n = 20
    s._n = n
    s._cross_up = np.full(n, False)
    s._cross_down = np.full(n, False)
    s._atr = np.full(n, 2.0)
    s._htf_up_per_bar = None
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=close + 1,
                   low=close - 1, close=close, volume=1, index=i)


def _state() -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=[], closed_trades=[], bar_index=10)


def test_cross_up_goes_long():
    s = _strategy()
    s._cross_up[10] = True
    sig = s.next(_bar(), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 100.0 - 1.5 * 2.0


def test_cross_down_goes_short():
    s = _strategy()
    s._cross_down[10] = True
    sig = s.next(_bar(), _state())
    assert sig.direction == Direction.SHORT


def test_no_signal_without_cross():
    s = _strategy()
    assert s.next(_bar(), _state()) is None


def test_htf_filter_blocks_counter_trend_cross():
    s = _strategy()
    s._cross_down[10] = True
    s._htf_up_per_bar = np.full(20, True)  # HTF up -- blocks a short cross
    assert s.next(_bar(), _state()) is None
