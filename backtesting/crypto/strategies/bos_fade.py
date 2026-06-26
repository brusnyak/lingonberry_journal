"""
TR BOS Fade — fade breakouts: short after bullish BOS, long after bearish BOS.

Thesis:
  A "break of structure" (close beyond N-bar high/low) most often fails within
  1–4 hours on forex. Smart money absorbs breakout buyers/sellers at the level,
  creating a liquidity sweep. Enter counter-direction after the BOS close,
  targeting a return into the prior range.

  Signal diagnostic: t=8.89 on EURGBP 5m (N=5,239), t=4.07 avg across 7/7 pairs.

Setup (bearish — fade bullish BOS):
  1. bar.close > rolling N-bar high (BOS above prior structure)
  2. Enter SHORT at bar.close
  3. SL: bar.high + sl_buffer_pips  (above the breakout candle's wick)
  4. TP1: entry - tp1_r × risk

Setup (bullish — fade bearish BOS) is the mirror.

Data required: {"<entry_tf>": df_entry}
Optional: {"240": df_4h} for HTF direction filter (same momentum check as TrAccumulation)
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class TrBosFade(Strategy):
    """Fade break-of-structure reversals."""

    spaces = {
        "bos_lookback": [10, 15, 20, 30],
        "sl_buffer_pips": [3, 5, 8, 10],
        "tp1_r": [1.0, 1.5, 2.0],
        "risk_pct": [0.005],
        "direction": ["bull", "bear", "both"],
    }

    def __init__(
        self,
        bos_lookback: int = 20,         # N-bar high/low for BOS detection
        sl_buffer_pips: int = 5,        # pips beyond the BOS candle wick for SL
        tp1_r: float = 1.5,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        direction: str = "both",        # "bull" = fade bearish BOS, "bear" = fade bullish BOS
        tp1_frac: float = 0.6,
        # HTF direction filter (requires "240" key in data dict)
        # For BOS fade: if 4H is bullish, allow bull fades; if bearish, allow bear fades
        htf_momentum_bars: int = 10,
        htf_agree: bool = True,         # require 4H agreement; set False to disable
    ):
        self.bos_lookback = bos_lookback
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r = tp1_r
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction
        self.tp1_frac = tp1_frac
        self.htf_momentum_bars = htf_momentum_bars
        self.htf_agree = htf_agree

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        # Precompute rolling N-bar high/low (causal: shift(1) so we don't use current bar)
        lb = self.bos_lookback
        self._roll_high = df["high"].rolling(lb).max().shift(1)
        self._roll_low  = df["low"].rolling(lb).min().shift(1)

        # HTF direction filter
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
        if i < self.bos_lookback + 1:
            return None

        prior_high = float(self._roll_high.iloc[i])
        prior_low  = float(self._roll_low.iloc[i])
        if np.isnan(prior_high) or np.isnan(prior_low):
            return None

        pip = self.pip_size
        sl_buf = self.sl_buffer_pips * pip

        # HTF direction check
        htf = 0
        if self._htf_ts is not None:
            idx4h = int(np.searchsorted(self._htf_ts, bar.ts, side="right")) - 1
            if idx4h >= 0:
                htf = int(self._htf_dir[idx4h])

        # ── Bearish fade: bullish BOS (close above prior high) → SHORT ──────
        if self.direction in ("bear", "both") and bar.close > prior_high:
            # HTF gate: only fade if 4H is NOT strongly bullish (i.e. not agree with BOS direction)
            if self.htf_agree and htf > 0:
                return None
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
                tp1_frac=self.tp1_frac,
                tp2_frac=0.0,
                trail=True,
                label="bos_fade_bear",
            )

        # ── Bullish fade: bearish BOS (close below prior low) → LONG ────────
        if self.direction in ("bull", "both") and bar.close < prior_low:
            # HTF gate: only fade if 4H is NOT strongly bearish
            if self.htf_agree and htf < 0:
                return None
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
                tp1_frac=self.tp1_frac,
                tp2_frac=0.0,
                trail=True,
                label="bos_fade_bull",
            )

        return None
