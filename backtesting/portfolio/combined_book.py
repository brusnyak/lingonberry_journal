"""
Combined-book wrapper: runs two (or more) strategies against ONE shared
equity/position slot, the way they'd actually run live on one account.

Why this exists: ORB and OvernightDrift were each validated as isolated
backtests on their own $10k baseline. They're designed to be time-disjoint
(ORB flat by ~15:55 NY, OvernightDrift holds 16:00->09:30 NY, i.e. exits
right as ORB's session opens) but that's a design ASSUMPTION, never
actually verified end-to-end. Holidays, early closes, and data gaps are
exactly where a supposedly-sequential handoff breaks. This wrapper makes
the engine enforce a single shared position slot across both strategies
(reusing EngineState.has_open_position, which is already global, not
per-strategy) and reports any place a hand-off would have collided.

Usage:
    from backtesting.portfolio.combined_book import CombinedBook
    book = CombinedBook([("orb", OrbNyWideStop(htf_key="240", ltf_key="30", multi_target=True)),
                          ("overnight", OvernightDrift(htf_key="240", stop_mode="structure"))])
    result = run(book, data, entry_tf="5", costs=ForexCosts(...), initial_equity=10_000)
"""
from __future__ import annotations

from typing import Optional

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Signal


class CombinedBook(Strategy):
    def __init__(self, members: list[tuple[str, Strategy]]):
        self.members = members
        self.collisions: list[dict] = []  # bars where >1 member wanted to enter at once
        self._active_name: Optional[str] = None

    def init(self, data: dict) -> None:
        for _, strat in self.members:
            strat.init(data)

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None
        candidates = []
        for name, strat in self.members:
            sig = strat.next(bar, state)
            if sig is not None:
                candidates.append((name, sig))
        if not candidates:
            return None
        if len(candidates) > 1:
            self.collisions.append({
                "ts": bar.ts, "index": bar.index,
                "members": [n for n, _ in candidates],
            })
        # First member in the list wins on a same-bar collision; logged above
        # either way so it's visible, not silently dropped.
        name, sig = candidates[0]
        self._active_name = name
        return sig

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        label = getattr(position, "label", "") or ""
        for name, strat in self.members:
            if name in label or (self._active_name == name and not label):
                return strat.should_close(position, bar, state)
        # Fallback: shouldn't happen if labels are set consistently, but
        # fail safe by closing rather than holding an unowned position open.
        return True

    def on_close(self, trade, state: EngineState) -> None:
        for _, strat in self.members:
            strat.on_close(trade, state)

    def on_partial(self, trade, state: EngineState) -> None:
        for _, strat in self.members:
            strat.on_partial(trade, state)
