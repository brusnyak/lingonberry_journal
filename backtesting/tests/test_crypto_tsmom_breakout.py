from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState
from backtesting.engine.orders import Direction
from backtesting.crypto.strategies.tsmom_breakout import CryptoTsmomBreakout


def _strategy() -> CryptoTsmomBreakout:
    s = CryptoTsmomBreakout()
    n = 20
    s._n = n
    s._atr = np.full(n, 2.0)
    s._entry_hi = np.full(n, 105.0)
    s._entry_lo = np.full(n, 95.0)
    s._exit_hi = np.full(n, 102.0)
    s._exit_lo = np.full(n, 98.0)
    s._pos_dir = 0
    return s


def _bar(i: int = 10, close: float = 100.0) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=close, high=close + 1,
                   low=close - 1, close=close, volume=1, index=i)


def _state(open_positions=None) -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=open_positions or [], closed_trades=[], bar_index=10)


def test_close_above_entry_channel_goes_long():
    sig = _strategy().next(_bar(close=106.0), _state())
    assert sig is not None
    assert sig.direction == Direction.LONG
    assert sig.sl == 106.0 - 2.0 * 2.0


def test_close_below_entry_channel_goes_short():
    sig = _strategy().next(_bar(close=94.0), _state())
    assert sig is not None
    assert sig.direction == Direction.SHORT
    assert sig.sl == 94.0 + 2.0 * 2.0


def test_no_signal_inside_channel():
    sig = _strategy().next(_bar(close=100.0), _state())
    assert sig is None


def test_no_entry_while_position_open():
    fake_pos = object()
    sig = _strategy().next(_bar(close=106.0), _state(open_positions=[fake_pos]))
    assert sig is None


def test_no_entry_when_atr_not_ready():
    s = _strategy()
    s._atr[10] = np.nan
    assert s.next(_bar(close=106.0), _state()) is None


class _Pos:
    def __init__(self, label):
        self.label = label


def test_long_closes_on_exit_channel_breakdown():
    s = _strategy()
    assert s.should_close(_Pos("crypto_tsmom_long"), _bar(close=97.0), _state()) is True
    assert s.should_close(_Pos("crypto_tsmom_long"), _bar(close=99.0), _state()) is False


def test_short_closes_on_exit_channel_breakout():
    s = _strategy()
    assert s.should_close(_Pos("crypto_tsmom_short"), _bar(close=103.0), _state()) is True
    assert s.should_close(_Pos("crypto_tsmom_short"), _bar(close=101.0), _state()) is False


def test_direction_long_only_ignores_short_breakouts():
    s = _strategy()
    s.direction = "long"
    assert s.next(_bar(close=94.0), _state()) is None
    sig = s.next(_bar(close=106.0), _state())
    assert sig is not None and sig.direction == Direction.LONG


def test_channel_stop_long_uses_exit_channel_low():
    s = _strategy()
    s.stop_mode = "channel"
    sig = s.next(_bar(close=106.0), _state())
    assert sig.sl == 98.0  # s._exit_lo fixture value


def test_channel_stop_falls_back_to_atr_when_channel_wrong_side():
    s = _strategy()
    s.stop_mode = "channel"
    s._exit_lo = np.full(20, 107.0)  # above entry price -- unusable for a long
    sig = s.next(_bar(close=106.0), _state())
    assert sig.sl == 106.0 - 2.0 * 2.0


def _structure_strategy():
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
    sig = s.next(_bar(close=106.0), _state())
    assert sig.sl == 95.0 - 0.1 * 2.0


def test_structure_stop_falls_back_to_atr_when_no_swing():
    s = _structure_strategy()
    sig = s.next(_bar(close=106.0), _state())
    assert sig.sl == 106.0 - 2.0 * 2.0
