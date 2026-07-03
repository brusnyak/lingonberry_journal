from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.lvl1_trend.htf_structure_vwap import HtfStructureVwap


def _strategy() -> HtfStructureVwap:
    s = HtfStructureVwap(min_rr=1.0, cooldown_bars=3)
    n = 20
    s._n = n
    s._min_i = 0
    s._last_close_i = -999
    s._regime_per_bar = [1] * n
    s._atr = [1.0] * n
    s._time_ok = [True] * n
    s._trend_ok = [True] * n
    s._vol_ok = [True] * n
    s._pdh = [105.0] * n
    s._pdl = [95.0] * n
    s._vwap_bounce_long = [False] * n
    s._vwap_bounce_short = [False] * n
    s._entry_bar_bos_idx = {}
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(
        ts="2026-01-01T00:00:00Z",
        open_=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1,
        index=i,
    )


def _state() -> EngineState:
    return EngineState(
        equity=25_000,
        initial_equity=25_000,
        open_positions=[],
        closed_trades=[],
        bar_index=10,
    )


def test_lvl2_rejects_prior_day_target_below_min_rr():
    s = _strategy()
    s._vwap_bounce_long[10] = True
    s._pdh[10] = 101.0  # reward 1, risk 2.5 -> 0.4R

    assert s.next(_bar(), _state()) is None


def test_lvl2_rejects_high_volatility_even_when_er_trends():
    s = _strategy()
    s._vwap_bounce_long[10] = True
    s._vol_ok[10] = False

    assert s.next(_bar(), _state()) is None


def test_lvl2_cooldown_blocks_immediate_reentry():
    s = _strategy()
    s._vwap_bounce_long[10] = True
    s._last_close_i = 8

    assert s.next(_bar(10), _state()) is None


def test_lvl2_accepts_clean_long_setup():
    s = _strategy()
    s._vwap_bounce_long[10] = True

    sig = s.next(_bar(), _state())

    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.tp1 == 105.0
