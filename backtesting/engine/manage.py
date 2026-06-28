"""Management layer — the expectancy layer the old engine was missing.

Two jobs, both structure-aware:

  1. entry_sl()    — place the initial stop at structural INVALIDATION (just beyond
                     the swing that voids the thesis), not a fixed far distance.
  2. should_exit() — runtime exit for Strategy.should_close(): once the trade is in
                     enough profit (activate_r), cut on an opposite-direction BOS/CHoCH.
                     Partial@1R and trail-to-BE are already owned by the runner.

Pure-array design (no FeatureCore dependency) so it is unit-testable in isolation.
Wire it from a strategy: pass the FeatureCore arrays in, delegate should_close to it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def direction_sign(direction) -> int:
    """+1 long / -1 short / 0 unknown, tolerant of enum or str."""
    val = getattr(direction, "value", direction)
    if val in ("long", "LONG", 1):
        return 1
    if val in ("short", "SHORT", -1):
        return -1
    return 0


@dataclass
class StructuralManager:
    """Structure-based SL placement + exit. All arrays index-aligned to entry-tf bars."""
    bearish_bos: np.ndarray
    bullish_bos: np.ndarray
    bearish_choch: np.ndarray
    bullish_choch: np.ndarray
    last_swing_high: np.ndarray
    last_swing_low: np.ndarray
    activate_r: float = 1.0      # arm structural exit only after this floating R
    sl_buffer: float = 0.0       # price units beyond the swing
    min_stop: float = 0.0        # reject/expand stops tighter than this (price units)

    # ── entry stop ────────────────────────────────────────────────────────────
    def entry_sl(self, direction, entry_price: float, i: int) -> float | None:
        """Invalidation stop just beyond the most recent confirmed swing.
        Returns None when no valid structural level exists (caller falls back)."""
        sign = direction_sign(direction)
        if sign == 0:
            return None
        if sign == 1:
            swing = self.last_swing_low[i]
            if np.isnan(swing) or swing >= entry_price:
                return None
            sl = swing - self.sl_buffer
            if entry_price - sl < self.min_stop:
                sl = entry_price - self.min_stop
            return sl
        swing = self.last_swing_high[i]
        if np.isnan(swing) or swing <= entry_price:
            return None
        sl = swing + self.sl_buffer
        if sl - entry_price < self.min_stop:
            sl = entry_price + self.min_stop
        return sl

    # ── runtime exit ──────────────────────────────────────────────────────────
    def floating_r(self, direction, entry_price: float, original_sl: float, price: float) -> float:
        stop_dist = abs(entry_price - original_sl)
        if stop_dist == 0:
            return 0.0
        sign = direction_sign(direction)
        return sign * (price - entry_price) / stop_dist

    def should_exit(self, position, bar, i: int) -> bool:
        """True → close remaining at bar.close. Asymmetric:
          - confirmed adverse BOS → exit ALWAYS (cut losers before the wide SL,
            and cap a winner if the trend flips). BOS = real invalidation.
          - adverse CHoCH → exit ONLY once in profit (armed). CHoCH is transitional
            noise (your own research); don't churn losers on it.
        """
        sign = direction_sign(position.direction)
        if sign == 0 or i < 0 or i >= len(self.bearish_bos):
            return False
        if sign == 1:
            adverse_bos, adverse_choch = bool(self.bearish_bos[i]), bool(self.bearish_choch[i])
        else:
            adverse_bos, adverse_choch = bool(self.bullish_bos[i]), bool(self.bullish_choch[i])

        if adverse_bos:
            return True
        if adverse_choch and self.floating_r(position.direction, position.entry_price,
                                             position.original_sl, bar.close) > self.activate_r:
            return True
        return False

    @classmethod
    def from_core(cls, core, **kw) -> "StructuralManager":
        return cls(
            bearish_bos=core.bearish_bos, bullish_bos=core.bullish_bos,
            bearish_choch=core.bearish_choch, bullish_choch=core.bullish_choch,
            last_swing_high=core.last_swing_high, last_swing_low=core.last_swing_low,
            **kw,
        )
