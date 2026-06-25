"""
TR Accumulation — range-sweep reversal.

Thesis:
  When price is "accumulating" (range compressed vs its own history), one side
  is swept by a wick (liquidity taken) then closes back inside.
  Enter in the opposite direction targeting the other side of the range.

Setup (bullish):
  1. Price in accumulation: N-bar range < compress_ratio × mean(last history_bars N-bar ranges)
  2. Sweep below: bar.low < range_low and bar.close > range_low  (wick through)
  3. Entry at bar.close
  4. SL: sweep_bar_low - sl_buffer_pips
  5. TP1 at tp1_r × risk above entry

Bearish is the mirror.

Data required: {"<entry_tf>": df_entry}
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


# ── strategy ─────────────────────────────────────────────────────────────────

class TrAccumulation(Strategy):
    """Range-sweep reversal strategy."""

    # freqtrade-style spaces — used by batch grid search
    spaces = {
        "range_lookback": [10, 15, 20, 30],
        "history_bars": [30, 50, 100],
        "compress_ratio": [0.60, 0.70, 0.80],
        "sl_buffer_pips": [3, 5, 8],
        "tp1_r": [1.0, 1.5, 2.0],
        "risk_pct": [0.005],
    }

    def __init__(
        self,
        range_lookback: int = 20,       # bars for the "current" accumulation range
        history_bars: int = 50,         # bars to compute mean range over
        compress_ratio: float = 0.70,   # current_range < compress_ratio × mean_range
        sl_buffer_pips: int = 5,
        tp1_r: float = 1.5,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        direction: str = "both",        # "bull", "bear", or "both"
    ):
        self.range_lookback = range_lookback
        self.history_bars = history_bars
        self.compress_ratio = compress_ratio
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r = tp1_r
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction  # filter to confirmed signal direction

    def init(self, data: dict) -> None:
        key = next(iter(data))
        df = data[key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        # Precompute rolling N-bar range series
        lb = self.range_lookback
        roll_range = df["high"].rolling(lb).max() - df["low"].rolling(lb).min()
        # Mean range over history_bars of rolling-range values
        self._mean_range = roll_range.rolling(self.history_bars).mean()
        self._roll_range = roll_range

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        lb = self.range_lookback
        min_bars = lb + self.history_bars
        if i < min_bars:
            return None

        pip = self.pip_size
        df = self._df

        # Causal: use values at i-1 (exclude current bar)
        current_range = float(self._roll_range.iloc[i - 1])
        mean_range = float(self._mean_range.iloc[i - 1])
        if np.isnan(current_range) or np.isnan(mean_range) or mean_range == 0:
            return None

        # Accumulation condition: current range is compressed vs its own history
        if current_range >= self.compress_ratio * mean_range:
            return None

        # Range bounds at i-1 (causal)
        window = df.iloc[i - lb: i]
        range_high = float(window["high"].max())
        range_low = float(window["low"].min())

        sl_buf = self.sl_buffer_pips * pip

        # Bullish sweep: wick below range_low, close back above
        if self.direction in ("bull", "both") and bar.low < range_low and bar.close > range_low:
            sl = bar.low - sl_buf
            stop = bar.close - sl
            if stop <= 0:
                return None
            tp1 = bar.close + self.tp1_r * stop
            return Signal(
                direction=Direction.LONG,
                entry=bar.close,
                sl=sl,
                tp1=tp1,
                risk_pct=self.risk_pct,
                tp1_frac=0.6,
                tp2_frac=0.0,
                trail=True,
                label="acc_bull_sweep",
            )

        # Bearish sweep: wick above range_high, close back below
        if self.direction in ("bear", "both") and bar.high > range_high and bar.close < range_high:
            sl = bar.high + sl_buf
            stop = sl - bar.close
            if stop <= 0:
                return None
            tp1 = bar.close - self.tp1_r * stop
            return Signal(
                direction=Direction.SHORT,
                entry=bar.close,
                sl=sl,
                tp1=tp1,
                risk_pct=self.risk_pct,
                tp1_frac=0.6,
                tp2_frac=0.0,
                trail=True,
                label="acc_bear_sweep",
            )

        return None
