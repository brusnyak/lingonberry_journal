from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction, Position
from backtesting.crypto.strategies.ict import TrIct
from backtesting.structure_lib.fvg import FVG
from backtesting.structure_lib.sweep import LiquidityPool, Sweep


def _bar(i: int, close: float, ts="2026-01-01T00:00:00Z") -> BarData:
    return BarData(ts=ts, open_=close, high=close + 0.001, low=close - 0.001,
                    close=close, volume=1, index=i)


def _state() -> EngineState:
    return EngineState(equity=50.0, initial_equity=50.0, open_positions=[],
                        closed_trades=[], bar_index=0)


def _position(direction: Direction, entry_price: float) -> Position:
    return Position(id=1, direction=direction, entry_price=entry_price,
                     entry_time=pd.Timestamp("2026-01-01"), sl=entry_price - 1,
                     tp1=entry_price + 1, tp2=None, tp3=None, lots=1.0,
                     risk_pct=0.005, tp1_frac=1.0, tp2_frac=0.0, trail=False)


def _long_signal_fixture(entry, sl, tp, min_stop_pct=None):
    """Minimal TrIct instance + inputs to drive _build_signal for a long."""
    strat = TrIct(min_stop_pct=min_stop_pct)
    ts0 = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    idx = pd.date_range(ts0, periods=5, freq="30min")
    strat._df30 = pd.DataFrame(
        {"open": entry, "high": entry + 0.01, "low": sl - 0.01, "close": entry},
        index=idx,
    )
    pool = LiquidityPool(level=sl + 0.0005, side="sell", source="swing_low", time=idx[0])
    sweep = Sweep(pool=pool, sweep_time=idx[0], direction="bullish", reclaim=False, wick_only=False)
    fvg = FVG(kind="bullish", top=entry + 0.001, bottom=entry - 0.001, ce=entry,
              c2_time=idx[1], c1_idx=0, c2_idx=1, c3_idx=2)
    strat._fvg_by_time = [(idx[1], fvg)]
    strat._ob_by_time = []
    strat._buy_pool_levels = [tp]
    strat._sell_pool_levels = []
    return strat, sweep


def test_min_stop_pct_filters_tight_stop_signal():
    # entry=100, sl=99.95 -> stop is 0.05% of price, tighter than the 0.25 filter
    strat, sweep = _long_signal_fixture(entry=100.0, sl=99.95, tp=103.0, min_stop_pct=0.25)
    sig = strat._build_signal(sweep, shift_idx=2, shift_dir="bullish")
    assert sig is None


def test_min_stop_pct_none_allows_tight_stop_signal():
    strat, sweep = _long_signal_fixture(entry=100.0, sl=99.95, tp=103.0, min_stop_pct=None)
    sig = strat._build_signal(sweep, shift_idx=2, shift_dir="bullish")
    assert sig is not None


def test_min_stop_pct_allows_wide_enough_stop():
    # entry=100, sl=99.5 -> stop is 0.5% of price, wider than the 0.25 filter
    strat, sweep = _long_signal_fixture(entry=100.0, sl=99.5, tp=103.0, min_stop_pct=0.25)
    sig = strat._build_signal(sweep, shift_idx=2, shift_dir="bullish")
    assert sig is not None


def _init_empty_sweep_state(strat: TrIct, n: int = 5) -> None:
    """Minimal state _detect_sweeps_at_bar()/next() need beyond what these
    tests set explicitly -- empty active/broken pool lists (no pools to
    sweep) and a tiny OHLC frame so `next()` can run end-to-end."""
    idx = pd.date_range("2026-01-01 00:00:00", periods=n, freq="30min", tz="UTC")
    strat._df30 = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}, index=idx)
    strat._buy_active_levels, strat._buy_active_pools = [], []
    strat._buy_broken_levels, strat._buy_broken_pools = [], []
    strat._sell_active_levels, strat._sell_active_pools = [], []
    strat._sell_broken_levels, strat._sell_broken_pools = [], []


def test_multi_target_ladder_sets_tp1_tp2_tp3():
    strat = TrIct(multi_target=True, tp1_r=1.0, tp1_frac=0.4, tp2_frac=0.35, sessions_only=False)
    strat._n = 5
    strat._pending = {
        "k": {"direction": "long", "entry": 100.0, "sl": 99.0, "tp": 103.0,
              "tp_ext": 105.0, "signal_time": pd.Timestamp("2026-01-01", tz="UTC"),
              "confidence": "high", "pool_source": "swing_low"}
    }
    strat._sweeps = []
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.zeros(5, dtype=bool)
    strat._bearish_bos = np.zeros(5, dtype=bool)
    _init_empty_sweep_state(strat)

    bar = _bar(0, close=100.0, ts=pd.Timestamp("2026-01-01 01:00:00", tz="UTC"))
    bar.low = 99.5  # touches entry
    sig = strat.next(bar, _state())

    assert sig is not None
    assert sig.tp1 == 101.0  # entry + 1.0R
    assert sig.tp2 == 103.0  # original pool-based target
    assert sig.tp3 == 105.0
    assert sig.tp1_frac == 0.4
    assert sig.tp2_frac == 0.35


def test_multi_target_falls_back_to_single_when_pool_too_close():
    # tp1_r=1.0 would land AT or past the pool target (103 - 100 = 3R away is
    # fine, but here the pool target is only 0.5R away -- quick partial isn't
    # meaningfully "before" it, so should fall back to a single full exit).
    strat = TrIct(multi_target=True, tp1_r=1.0, sessions_only=False)
    strat._n = 5
    strat._pending = {
        "k": {"direction": "long", "entry": 100.0, "sl": 99.0, "tp": 100.5,
              "tp_ext": 101.0, "signal_time": pd.Timestamp("2026-01-01", tz="UTC"),
              "confidence": "high", "pool_source": "swing_low"}
    }
    strat._sweeps = []
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.zeros(5, dtype=bool)
    strat._bearish_bos = np.zeros(5, dtype=bool)
    _init_empty_sweep_state(strat)

    bar = _bar(0, close=100.0, ts=pd.Timestamp("2026-01-01 01:00:00", tz="UTC"))
    bar.low = 99.5
    sig = strat.next(bar, _state())

    assert sig is not None
    assert sig.tp2 is None
    assert sig.tp1_frac == 1.0


def test_should_close_true_when_losing_and_structure_invalidated():
    strat = TrIct()
    strat._n = 5
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.zeros(5, dtype=bool)
    strat._bearish_bos = np.array([False, False, True, False, False])

    pos = _position(Direction.LONG, entry_price=100.0)
    bar = _bar(2, close=99.0)  # losing (below entry) + bearish BOS at this bar
    assert strat.should_close(pos, bar, _state()) is True


def test_should_close_false_when_winning_despite_invalidation():
    strat = TrIct()
    strat._n = 5
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.zeros(5, dtype=bool)
    strat._bearish_bos = np.array([False, False, True, False, False])

    pos = _position(Direction.LONG, entry_price=100.0)
    bar = _bar(2, close=101.0)  # winning, structure invalidation shouldn't cut it
    assert strat.should_close(pos, bar, _state()) is False


def test_should_close_false_when_losing_but_no_invalidation():
    strat = TrIct()
    strat._n = 5
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.zeros(5, dtype=bool)
    strat._bearish_bos = np.zeros(5, dtype=bool)

    pos = _position(Direction.LONG, entry_price=100.0)
    bar = _bar(2, close=99.0)  # losing but no opposing structure
    assert strat.should_close(pos, bar, _state()) is False


def test_should_close_short_position_mirrors_long():
    strat = TrIct()
    strat._n = 5
    strat._bullish_choch = np.zeros(5, dtype=bool)
    strat._bearish_choch = np.zeros(5, dtype=bool)
    strat._bullish_bos = np.array([False, False, True, False, False])
    strat._bearish_bos = np.zeros(5, dtype=bool)

    pos = _position(Direction.SHORT, entry_price=100.0)
    bar = _bar(2, close=101.0)  # losing for a short (price rose) + bullish BOS
    assert strat.should_close(pos, bar, _state()) is True
