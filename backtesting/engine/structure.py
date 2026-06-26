"""
Market structure detector — HH/HL/LL/LH labeling.

Given an OHLCV array, detects:
  - Swing highs / swing lows (fractal pivots, n bars each side)
  - Labels: HH (higher high), HL (higher low), LL (lower low), LH (lower high)
  - Current trend: "up" | "down" | "range"
  - Order blocks: last opposing candle before a significant impulse
  - BOS / ChoCH events

Used by:
  - TrFvg: OB-based SL placement, structure-aware entry filter
  - Review UI: chart overlay showing labeled pivots and OBs
  - Future: post-entry structure invalidation exit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx:    int
    price:  float
    kind:   str   # "HH" | "HL" | "LL" | "LH" | "H" | "L" (unlabeled until context known)
    is_high: bool


@dataclass
class OrderBlock:
    idx:     int
    open:    float
    high:    float
    low:     float
    close:   float
    kind:    str    # "demand" (bullish OB, SL anchor for longs) | "supply" (bearish OB, SL for shorts)
    # True if this OB has been mitigated (price returned into it)
    mitigated: bool = False


@dataclass
class StructureSnapshot:
    """Structure state at a given bar index (no look-ahead)."""
    bar_idx:    int
    pivots:     list[Pivot]        # confirmed pivots up to this bar
    trend:      str                # "up" | "down" | "range"
    last_hh:    Optional[float]
    last_hl:    Optional[float]
    last_ll:    Optional[float]
    last_lh:    Optional[float]
    demand_obs: list[OrderBlock]   # active demand OBs (for long SL)
    supply_obs: list[OrderBlock]   # active supply OBs (for short SL)


class StructureAnalyzer:
    """
    Precomputes full structure for a price series.
    All methods are look-ahead safe: results at bar i use only data up to bar i.
    """

    def __init__(
        self,
        high:  np.ndarray,
        low:   np.ndarray,
        close: np.ndarray,
        open_: np.ndarray,
        swing_n: int = 3,           # fractal half-width (bars each side)
        ob_lookback: int = 30,      # max bars back to find OB
        ob_min_body_ratio: float = 0.3,  # OB candle body/range ratio
    ):
        self.high    = high
        self.low     = low
        self.close   = close
        self.open_   = open_
        self.n       = len(high)
        self.swing_n = swing_n
        self.ob_lookback = ob_lookback
        self.ob_min_body_ratio = ob_min_body_ratio

        self._sh: np.ndarray = np.full(self.n, np.nan)  # swing high values
        self._sl: np.ndarray = np.full(self.n, np.nan)  # swing low values
        self._labels: list[Optional[Pivot]] = [None] * self.n

        self._compute_swings()
        self._label_pivots()

    # ── Swing detection ───────────────────────────────────────────────────────

    def _compute_swings(self) -> None:
        n = self.swing_n
        for i in range(n, self.n - n):
            window_h = self.high[i - n: i + n + 1]
            window_l = self.low[i - n:  i + n + 1]
            if self.high[i] == window_h.max():
                self._sh[i] = self.high[i]
            if self.low[i] == window_l.min():
                self._sl[i] = self.low[i]

    # ── HH/HL/LL/LH labeling ─────────────────────────────────────────────────

    def _label_pivots(self) -> None:
        """Label each confirmed swing as HH/HL/LL/LH relative to the prior pivot of same type."""
        last_sh: Optional[float] = None
        last_sl: Optional[float] = None

        # Walk forward; a pivot at i is "confirmed" at i + swing_n (both sides seen)
        for i in range(self.swing_n, self.n - self.swing_n):
            if not np.isnan(self._sh[i]):
                kind = "HH" if (last_sh is None or self.high[i] > last_sh) else "LH"
                self._labels[i] = Pivot(idx=i, price=self.high[i], kind=kind, is_high=True)
                last_sh = self.high[i]
            if not np.isnan(self._sl[i]):
                kind = "HL" if (last_sl is None or self.low[i] > last_sl) else "LL"
                self._labels[i] = Pivot(idx=i, price=self.low[i], kind=kind, is_high=False)
                last_sl = self.low[i]

    # ── Public API ────────────────────────────────────────────────────────────

    def confirmed_before(self, bar_i: int) -> list[Pivot]:
        """All pivots confirmed strictly before bar_i (look-ahead safe)."""
        cutoff = bar_i - self.swing_n
        return [p for p in self._labels[:cutoff] if p is not None]

    def trend_at(self, bar_i: int, lookback_pivots: int = 4) -> str:
        """
        Determine trend using last N confirmed pivots.
        "up"    — recent highs and lows are both rising (HH+HL sequence)
        "down"  — recent highs and lows are both falling (LL+LH sequence)
        "range" — mixed
        """
        pivots = self.confirmed_before(bar_i)[-lookback_pivots * 2:]
        if len(pivots) < 2:
            return "range"

        highs = [p for p in pivots if p.is_high]
        lows  = [p for p in pivots if not p.is_high]

        if len(highs) >= 2 and len(lows) >= 2:
            hh = highs[-1].price > highs[-2].price
            hl = lows[-1].price  > lows[-2].price
            ll = lows[-1].price  < lows[-2].price
            lh = highs[-1].price < highs[-2].price
            if hh and hl:
                return "up"
            if ll and lh:
                return "down"
        return "range"

    def last_pivot_before(self, bar_i: int, kind_filter: Optional[str] = None) -> Optional[Pivot]:
        """Most recent confirmed pivot before bar_i, optionally filtered by kind."""
        pivots = self.confirmed_before(bar_i)
        if kind_filter:
            pivots = [p for p in pivots if p.kind == kind_filter]
        return pivots[-1] if pivots else None

    def demand_ob_before(self, bar_i: int) -> Optional[OrderBlock]:
        """
        Find the demand Order Block before bar_i using proper ICT logic.

        Algorithm:
          1. Scan back from bar_i to find the most recent significant bearish impulse candle
             (strong body = bears taking control, body/range >= 0.5).
          2. Scan back from BEFORE that impulse for the last bullish candle (body >= threshold).
             This candle is the OB — the origin of the move that got imbalanced.
          3. OB.low must be below entry price to serve as a valid SL anchor.

        This avoids the pitfall of treating any nearby bullish candle as an OB — the OB
        must be the last bullish candle before the impulse that caused the imbalance.
        """
        entry_price = self.close[bar_i]
        lo = max(0, bar_i - self.ob_lookback)

        # Step 1: find most recent bearish impulse
        impulse_idx = None
        for j in range(bar_i - 1, lo, -1):
            o, h, l, c = self.open_[j], self.high[j], self.low[j], self.close[j]
            rng = h - l
            if rng == 0:
                continue
            if c < o and abs(c - o) / rng >= 0.5:
                impulse_idx = j
                break

        if impulse_idx is None:
            return None

        # Step 2: last bullish candle before the impulse
        for j in range(impulse_idx - 1, lo, -1):
            o, h, l, c = self.open_[j], self.high[j], self.low[j], self.close[j]
            rng = h - l
            if rng == 0:
                continue
            is_bullish = c > o and abs(c - o) / rng >= self.ob_min_body_ratio
            if is_bullish and l < entry_price:
                return OrderBlock(idx=j, open=o, high=h, low=l, close=c, kind="demand")

        return None

    def supply_ob_before(self, bar_i: int) -> Optional[OrderBlock]:
        """
        Find the supply Order Block before bar_i using proper ICT logic.

        Algorithm:
          1. Find the most recent bullish impulse candle before bar_i.
          2. Last bearish candle before that impulse = supply OB.
          3. OB.high must be above entry price.
        """
        entry_price = self.close[bar_i]
        lo = max(0, bar_i - self.ob_lookback)

        # Step 1: find most recent bullish impulse
        impulse_idx = None
        for j in range(bar_i - 1, lo, -1):
            o, h, l, c = self.open_[j], self.high[j], self.low[j], self.close[j]
            rng = h - l
            if rng == 0:
                continue
            if c > o and abs(c - o) / rng >= 0.5:
                impulse_idx = j
                break

        if impulse_idx is None:
            return None

        # Step 2: last bearish candle before the impulse
        for j in range(impulse_idx - 1, lo, -1):
            o, h, l, c = self.open_[j], self.high[j], self.low[j], self.close[j]
            rng = h - l
            if rng == 0:
                continue
            is_bearish = c < o and abs(c - o) / rng >= self.ob_min_body_ratio
            if is_bearish and h > entry_price:
                return OrderBlock(idx=j, open=o, high=h, low=l, close=c, kind="supply")

        return None

    def snapshot(self, bar_i: int, lookback_pivots: int = 4) -> StructureSnapshot:
        """Full structure state at bar_i for use in strategy and UI."""
        pivots = self.confirmed_before(bar_i)
        trend  = self.trend_at(bar_i, lookback_pivots)

        highs = [p for p in pivots if p.is_high]
        lows  = [p for p in pivots if not p.is_high]

        return StructureSnapshot(
            bar_idx=bar_i,
            pivots=pivots[-20:],  # last 20 for UI
            trend=trend,
            last_hh=next((p.price for p in reversed(highs) if p.kind == "HH"), None),
            last_hl=next((p.price for p in reversed(lows)  if p.kind == "HL"), None),
            last_ll=next((p.price for p in reversed(lows)  if p.kind == "LL"), None),
            last_lh=next((p.price for p in reversed(highs) if p.kind == "LH"), None),
            demand_obs=[ob for ob in [self.demand_ob_before(bar_i)] if ob is not None],
            supply_obs=[ob for ob in [self.supply_ob_before(bar_i)] if ob is not None],
        )
