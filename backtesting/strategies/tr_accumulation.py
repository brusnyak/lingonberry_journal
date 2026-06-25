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
        direction: str = "bull",        # "bull", "bear", or "both" — research shows bull is the edge
        # HTF direction filter (requires "240" key in data dict)
        # Method: 4H close > close N bars ago = bullish; disagree = block entry
        # Validated: acc_sweep + 4H momentum agree → t=4.97 across 7/7 pairs (vs t=3.03 unfiltered)
        htf_momentum_bars: int = 10,    # 4H bars for momentum look-back (~40 hours)
    ):
        self.range_lookback = range_lookback
        self.history_bars = history_bars
        self.compress_ratio = compress_ratio
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r = tp1_r
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction
        self.htf_momentum_bars = htf_momentum_bars

    def init(self, data: dict) -> None:
        # Entry TF data (first key = entry TF passed by runner)
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        # Precompute rolling N-bar range series (all as numpy — avoids per-bar pandas slice)
        lb = self.range_lookback
        roll_high_s = df["high"].rolling(lb).max()
        roll_low_s  = df["low"].rolling(lb).min()
        roll_range  = roll_high_s - roll_low_s
        self._mean_range  = roll_range.rolling(self.history_bars).mean().to_numpy()
        self._roll_range  = roll_range.to_numpy()
        self._roll_high_v = roll_high_s.to_numpy()  # range_high per bar
        self._roll_low_v  = roll_low_s.to_numpy()   # range_low per bar

        # HTF direction filter: 4H close momentum
        # +1 = bullish (close > close N bars ago), -1 = bearish, 0 = flat/unknown
        self._htf_ts:  Optional[np.ndarray] = None
        self._htf_dir: Optional[np.ndarray] = None
        if "240" in data:
            df4h = data["240"].copy()
            if "ts" in df4h.columns:
                df4h = df4h.set_index("ts")
            df4h = df4h.sort_index()
            delta = df4h["close"] - df4h["close"].shift(self.htf_momentum_bars)
            direction_series = np.sign(delta).fillna(0)
            self._htf_ts  = df4h.index.to_numpy()
            self._htf_dir = direction_series.to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        # HTF direction gate: only enter when 4H momentum agrees with trade direction
        if self._htf_ts is not None:
            idx4h = int(np.searchsorted(self._htf_ts, bar.ts, side="right")) - 1
            if idx4h >= 0:
                htf = self._htf_dir[idx4h]
                if self.direction == "bull" and htf < 0:
                    return None
                if self.direction == "bear" and htf > 0:
                    return None

        i = bar.index
        lb = self.range_lookback
        min_bars = lb + self.history_bars
        if i < min_bars:
            return None

        pip = self.pip_size

        # Causal: use values at i-1 (exclude current bar) — all numpy, no per-bar pandas slice
        current_range = self._roll_range[i - 1]
        mean_range    = self._mean_range[i - 1]
        if np.isnan(current_range) or np.isnan(mean_range) or mean_range == 0:
            return None

        # Accumulation condition: current range is compressed vs its own history
        if current_range >= self.compress_ratio * mean_range:
            return None

        range_high = self._roll_high_v[i - 1]
        range_low  = self._roll_low_v[i - 1]

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
