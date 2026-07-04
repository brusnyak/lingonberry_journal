from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.portfolio.combined_book import CombinedBook


class _Fixed(Strategy):
    """Fires exactly one signal at the given bar index, with the given label."""

    def __init__(self, fire_at: int, label: str, close_at: int | None = None):
        self.fire_at = fire_at
        self.label = label
        self.close_at = close_at

    def init(self, data: dict) -> None:
        pass

    def next(self, bar: BarData, state: EngineState) -> Signal | None:
        if bar.index != self.fire_at:
            return None
        return Signal(direction=Direction.LONG, entry=100.0, sl=95.0, tp1=110.0, label=self.label)

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return self.close_at is not None and bar.index >= self.close_at


def _bar(i: int) -> BarData:
    return BarData(ts="2026-01-01T00:00:00Z", open_=100.0, high=101.0, low=99.0, close=100.0, volume=1, index=i)


def _state(open_positions=None) -> EngineState:
    return EngineState(equity=10_000, initial_equity=10_000,
                       open_positions=open_positions or [], closed_trades=[], bar_index=0)


def test_no_signal_when_no_member_fires():
    book = CombinedBook([("orb", _Fixed(5, "orb_wide_long")), ("overnight", _Fixed(10, "overnight_drift_long"))])
    assert book.next(_bar(0), _state()) is None


def test_single_member_fires_cleanly():
    book = CombinedBook([("orb", _Fixed(5, "orb_wide_long")), ("overnight", _Fixed(10, "overnight_drift_long"))])
    sig = book.next(_bar(5), _state())
    assert sig is not None
    assert sig.label == "orb_wide_long"
    assert book.collisions == []


def test_collision_logged_when_both_fire_same_bar():
    book = CombinedBook([("orb", _Fixed(5, "orb_wide_long")), ("overnight", _Fixed(5, "overnight_drift_long"))])
    sig = book.next(_bar(5), _state())
    assert sig is not None  # first member still wins, not dropped silently
    assert len(book.collisions) == 1
    assert set(book.collisions[0]["members"]) == {"orb", "overnight"}


def test_no_entry_while_position_already_open():
    book = CombinedBook([("orb", _Fixed(5, "orb_wide_long"))])
    fake_position = object()
    assert book.next(_bar(5), _state(open_positions=[fake_position])) is None


def test_should_close_dispatches_by_label():
    orb = _Fixed(5, "orb_wide_long", close_at=8)
    overnight = _Fixed(10, "overnight_drift_long", close_at=20)
    book = CombinedBook([("orb", orb), ("overnight", overnight)])

    class _Pos:
        label = "orb_wide_long"

    assert book.should_close(_Pos(), _bar(7), _state()) is False
    assert book.should_close(_Pos(), _bar(8), _state()) is True

    class _Pos2:
        label = "overnight_drift_long"

    assert book.should_close(_Pos2(), _bar(15), _state()) is False
    assert book.should_close(_Pos2(), _bar(20), _state()) is True
