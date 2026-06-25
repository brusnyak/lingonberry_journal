"""
TR FVG — Fair Value Gap fill reversal.

Thesis:
  A 3-bar FVG (impulse + gap) creates an imbalance that price routinely returns to fill.
  The fill direction has a real t-statistic edge (research: fvg_bear_fill t=6.81 EURGBP 5m,
  avg_t=3.43 across 7/7 pairs on 5m). Enter on the bar the gap forms, targeting the fill.

Bearish FVG (LONG setup — "bear fill"):
  bar[i].high < bar[i-2].low → price gapped DOWN → fill is UP
  Entry: bar.close
  SL: bar.low - sl_buffer_pips
  TP1: bar.close + tp1_r × risk  (targeting into the gap zone)

Bullish FVG (SHORT setup — "bull fill"):
  bar[i].low > bar[i-2].high → price gapped UP → fill is DOWN
  Entry: bar.close
  SL: bar.high + sl_buffer_pips
  TP1: bar.close - tp1_r × risk

Signal strength: bear_fill >> bull_fill (research confirmed). Default direction="bear".

Optional HTF filter: 4H momentum direction must agree with fill direction.
Optional: min_gap_atr_pct — gap must be at least X% of ATR14 to count.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class TrFvg(Strategy):
    """FVG fill reversal strategy."""

    spaces = {
        "sl_buffer_pips": [3, 5, 8, 10],
        "tp1_r": [0.8, 1.0, 1.5, 2.0],
        "min_gap_atr_pct": [0.2, 0.3, 0.5],
        "direction": ["bear", "bull", "both"],
    }

    def __init__(
        self,
        sl_buffer_pips: int = 5,
        tp1_r: float = 1.5,
        tp1_frac: float = 0.6,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        direction: str = "bear",        # "bear" = long on bear FVG fill
        min_gap_atr_pct: float = 0.3,   # gap must be >= this × ATR14
        # HTF filter
        htf_momentum_bars: int = 10,
        htf_agree: bool = True,
    ):
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r = tp1_r
        self.tp1_frac = tp1_frac
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction
        self.min_gap_atr_pct = min_gap_atr_pct
        self.htf_momentum_bars = htf_momentum_bars
        self.htf_agree = htf_agree

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        # Precompute ATR14 as numpy
        h = df["high"].to_numpy()
        l = df["low"].to_numpy()
        c = np.roll(df["close"].to_numpy(), 1)
        c[0] = h[0]
        tr = np.maximum(h - l, np.maximum(np.abs(h - c), np.abs(l - c)))
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        self._atr = atr

        # Numpy arrays for bar data
        self._high  = h
        self._low   = l
        self._close = df["close"].to_numpy()

        # HTF filter
        self._htf_ts:  Optional[np.ndarray] = None
        self._htf_dir: Optional[np.ndarray] = None
        if "240" in data and self.htf_agree:
            df4h = data["240"].copy()
            if "ts" in df4h.columns:
                df4h = df4h.set_index("ts")
            df4h = df4h.sort_index()
            delta = df4h["close"] - df4h["close"].shift(self.htf_momentum_bars)
            self._htf_ts  = df4h.index.to_numpy()
            self._htf_dir = np.sign(delta).fillna(0).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        if i < 3:
            return None

        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None

        gap_thresh = atr * self.min_gap_atr_pct
        pip = self.pip_size
        sl_buf = self.sl_buffer_pips * pip

        b0_high  = self._high[i]
        b0_low   = self._low[i]
        b0_close = self._close[i]
        b2_high  = self._high[i - 2]
        b2_low   = self._low[i - 2]

        # HTF gate
        htf = 0
        if self._htf_ts is not None:
            idx4h = int(np.searchsorted(self._htf_ts, bar.ts, side="right")) - 1
            if idx4h >= 0:
                htf = int(self._htf_dir[idx4h])

        # ── Bearish FVG → LONG (bear fill: price gapped DOWN, fill = UP) ──────
        if self.direction in ("bear", "both"):
            # b0.high < b2.low: gap from b0.high to b2.low
            if b0_high < b2_low:
                gap = b2_low - b0_high
                if gap >= gap_thresh:
                    # HTF: 4H should be bullish (agrees with LONG fill)
                    if self.htf_agree and htf < 0:
                        pass
                    else:
                        sl = b0_low - sl_buf
                        stop = b0_close - sl
                        if stop > 0:
                            return Signal(
                                direction=Direction.LONG,
                                entry=b0_close,
                                sl=sl,
                                tp1=b0_close + self.tp1_r * stop,
                                risk_pct=self.risk_pct,
                                tp1_frac=self.tp1_frac,
                                tp2_frac=0.0,
                                trail=True,
                                label="fvg_bear_fill",
                            )

        # ── Bullish FVG → SHORT (bull fill: price gapped UP, fill = DOWN) ─────
        if self.direction in ("bull", "both"):
            # b0.low > b2.high: gap from b2.high to b0.low
            if b0_low > b2_high:
                gap = b0_low - b2_high
                if gap >= gap_thresh:
                    # HTF: 4H should be bearish (agrees with SHORT fill)
                    if self.htf_agree and htf > 0:
                        pass
                    else:
                        sl = b0_high + sl_buf
                        stop = sl - b0_close
                        if stop > 0:
                            return Signal(
                                direction=Direction.SHORT,
                                entry=b0_close,
                                sl=sl,
                                tp1=b0_close - self.tp1_r * stop,
                                risk_pct=self.risk_pct,
                                tp1_frac=self.tp1_frac,
                                tp2_frac=0.0,
                                trail=True,
                                label="fvg_bull_fill",
                            )

        return None
