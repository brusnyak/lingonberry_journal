"""
TR Breakout — BOS retracement continuation.

Thesis:
  When price breaks structure (closes above/below N-bar high/low), it
  often retraces 50-65% of the breakout move before continuing.
  Enter on the retracement in the direction of the break.

Setup (bullish BOS):
  1. Close > max(high, lookback bars)  → BOS confirmed
  2. Record: bos_level = prior N-bar high, bos_bar_high = bar.high
  3. Wait for pullback: price retraces 50–65% of (bos_bar_high - bos_level)
     i.e. bar.low enters [bos_level + (1-retrace_max)*move, bos_level + (1-retrace_min)*move]
  4. Entry at bar.close inside pullback zone
  5. SL: below bos_level - sl_buffer_pips
  6. TP: entry + tp_r × risk, or next structural high

Bearish BOS is the mirror.

Data required: {"<entry_tf>": df_entry}
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class TrBreakout(Strategy):
    """BOS pullback continuation strategy."""

    spaces = {
        "bos_lookback": [10, 15, 20, 30],
        "retrace_min": [0.45, 0.50, 0.55],
        "retrace_max": [0.60, 0.65, 0.70],
        "sl_buffer_pips": [3, 5, 8],
        "tp_r": [1.0, 1.5, 2.0],
        "max_wait_bars": [10, 20, 30],
        "risk_pct": [0.005],
    }

    def __init__(
        self,
        bos_lookback: int = 20,       # N-bar structure window
        retrace_min: float = 0.50,    # min pullback fraction (50%)
        retrace_max: float = 0.65,    # max pullback fraction (65%)
        sl_buffer_pips: int = 5,
        tp_r: float = 1.5,
        max_wait_bars: int = 20,      # invalidate setup if no entry in N bars
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
    ):
        super().__init__()
        self.bos_lookback = bos_lookback
        self.retrace_min = retrace_min
        self.retrace_max = retrace_max
        self.sl_buffer_pips = sl_buffer_pips
        self.tp_r = tp_r
        self.max_wait_bars = max_wait_bars
        self.risk_pct = risk_pct
        self.pip_size = pip_size

    def init(self, data: dict) -> None:
        key = next(iter(data))
        df = data[key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        # Setup state
        self._dir: Optional[str] = None    # "bull" or "bear"
        self._bos_level: float = 0.0       # the broken structure level
        self._bos_extreme: float = 0.0     # high (bull) or low (bear) of BOS bar
        self._bos_bar_idx: int = -1
        self._entry_zone_lo: float = 0.0
        self._entry_zone_hi: float = 0.0
        self._sl_level: float = 0.0

    def _reset(self) -> None:
        self._dir = None
        self._bos_level = 0.0
        self._bos_extreme = 0.0
        self._bos_bar_idx = -1

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            self._reset()
            return None

        i = bar.index
        lb = self.bos_lookback
        if i < lb:
            return None

        pip = self.pip_size
        df = self._df

        # ── 1. Expire stale setup ─────────────────────────────────────────────
        if self._dir is not None and (i - self._bos_bar_idx) > self.max_wait_bars:
            self._reset()

        # ── 2. Entry on pullback ───────────────────────────────────────────────
        if self._dir == "bull":
            if self._entry_zone_lo <= bar.low <= self._entry_zone_hi or \
               self._entry_zone_lo <= bar.close <= self._entry_zone_hi:
                entry = bar.close
                sl = self._sl_level
                stop = entry - sl
                if stop > 0:
                    self._reset()
                    return Signal(
                        direction=Direction.LONG,
                        entry=entry,
                        sl=sl,
                        tp1=entry + self.tp_r * stop,
                        risk_pct=self.risk_pct,
                        tp1_frac=0.6,
                        tp2_frac=0.0,
                        trail=True,
                        label="bos_bull_retrace",
                    )

        elif self._dir == "bear":
            if self._entry_zone_lo <= bar.high <= self._entry_zone_hi or \
               self._entry_zone_lo <= bar.close <= self._entry_zone_hi:
                entry = bar.close
                sl = self._sl_level
                stop = sl - entry
                if stop > 0:
                    self._reset()
                    return Signal(
                        direction=Direction.SHORT,
                        entry=entry,
                        sl=sl,
                        tp1=entry - self.tp_r * stop,
                        risk_pct=self.risk_pct,
                        tp1_frac=0.6,
                        tp2_frac=0.0,
                        trail=True,
                        label="bos_bear_retrace",
                    )

        # ── 3. BOS detection ──────────────────────────────────────────────────
        if self._dir is None:
            window = df.iloc[i - lb: i]
            prior_high = float(window["high"].max())
            prior_low = float(window["low"].min())

            # Bullish BOS: close above prior N-bar high
            if bar.close > prior_high:
                move = bar.high - prior_high
                if move > 0:
                    self._dir = "bull"
                    self._bos_level = prior_high
                    self._bos_extreme = bar.high
                    self._bos_bar_idx = i
                    # Pullback zone: 50-65% retracement of the BOS move
                    self._entry_zone_hi = prior_high + (1 - self.retrace_min) * move
                    self._entry_zone_lo = prior_high + (1 - self.retrace_max) * move
                    self._sl_level = prior_high - self.sl_buffer_pips * pip

            # Bearish BOS: close below prior N-bar low
            elif bar.close < prior_low:
                move = prior_low - bar.low
                if move > 0:
                    self._dir = "bear"
                    self._bos_level = prior_low
                    self._bos_extreme = bar.low
                    self._bos_bar_idx = i
                    self._entry_zone_lo = prior_low - (1 - self.retrace_min) * move
                    self._entry_zone_hi = prior_low - (1 - self.retrace_max) * move
                    self._sl_level = prior_low + self.sl_buffer_pips * pip

        return None
