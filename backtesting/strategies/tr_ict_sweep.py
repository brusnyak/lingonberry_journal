"""
TrIctSweep — ICT sweep + ChoCH (MSS) + FVG entry.

Signal chain (LONG):
  1. Price sweeps a recent swing LOW on entry TF
     (bar.low < swing_low AND bar.close > swing_low)
  2. Within mss_bars after the sweep, a bar closes ABOVE the most recent swing HIGH
     (ChoCH / Market Structure Shift confirms bullish intent)
  3. Between the sweep bar and the ChoCH bar, find a bearish FVG
     (bar[j].high < bar[j-2].low — gap that formed during the sweep impulse)
  4. Enter LONG at FVG midpoint when price pulls back into it

SHORT is the mirror.

HTF bias filter (4H):
  Only take setups that agree with the prevailing 4H direction.

Differences from TrFvg:
  - Requires liquidity sweep before FVG (filters random FVGs)
  - Requires ChoCH (MSS) after sweep (confirms reversal intent)
  - Enters at FVG midpoint on pullback, not at FVG formation
  - State machine: IDLE → SWEPT → ChoCH_CONFIRMED → FVG_PENDING → FILLED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


@dataclass
class _Pending:
    direction: Direction
    fvg_mid: float
    fvg_lo:  float       # bottom of FVG gap (SL anchor)
    fvg_hi:  float       # top of FVG gap
    sweep_sl: float      # extreme of sweep bar (hard SL below)
    armed_at: int        # bar index when FVG was found
    tp1_r: float


class TrIctSweep(Strategy):

    spaces = {
        "swing_n":        [3, 5],
        "mss_bars":       [5, 10, 20],
        "fvg_expiry_bars":[20, 40, 80],
        "sl_buffer_pips": [5, 10, 20, 50, 200],
        "tp1_r":          [1.5, 2.0, 3.0],
        "min_fvg_pts":    [3, 5, 10, 20],
    }

    def __init__(
        self,
        swing_n: int         = 3,      # bars each side for swing detection
        mss_bars: int        = 10,     # max bars after sweep to detect ChoCH
        fvg_expiry_bars: int = 40,     # 1 bar = 1 entry-TF bar; cancel if not filled
        sl_buffer_pips: float = 10.0,
        tp1_r: float          = 2.0,
        min_fvg_pts: float    = 5.0,   # minimum FVG gap size in price units
        risk_pct: float       = 0.003,
        pip_size: float       = 0.0001,
        direction: str        = "bear", # "bull", "bear", "both"
        htf_agree: bool       = True,
        htf_bars: int         = 10,
    ):
        self.swing_n        = swing_n
        self.mss_bars       = mss_bars
        self.fvg_expiry_bars= fvg_expiry_bars
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r          = tp1_r
        self.min_fvg_pts    = min_fvg_pts
        self.risk_pct       = risk_pct
        self.pip_size       = pip_size
        self.direction      = direction
        self.htf_agree      = htf_agree
        self.htf_bars       = htf_bars

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)

        self._high  = df["high"].to_numpy()
        self._low   = df["low"].to_numpy()
        self._close = df["close"].to_numpy()
        self._n     = len(df)

        # Precompute swing highs / lows (n-bar fractals)
        n = self.swing_n
        sh = np.full(self._n, np.nan)
        sl_arr = np.full(self._n, np.nan)
        for i in range(n, self._n - n):
            if self._high[i] == max(self._high[i-n:i+n+1]):
                sh[i] = self._high[i]
            if self._low[i] == min(self._low[i-n:i+n+1]):
                sl_arr[i] = self._low[i]

        self._swing_high = sh
        self._swing_low  = sl_arr

        # HTF direction filter
        self._htf_ts:  Optional[np.ndarray] = None
        self._htf_dir: Optional[np.ndarray] = None
        if "240" in data and self.htf_agree:
            df4h = data["240"].copy()
            if "ts" in df4h.columns:
                df4h = df4h.set_index("ts")
            df4h = df4h.sort_index()
            delta = df4h["close"] - df4h["close"].shift(self.htf_bars)
            self._htf_ts  = df4h.index.to_numpy()
            self._htf_dir = np.sign(delta).fillna(0).to_numpy()

        # State
        self._pending: Optional[_Pending] = None
        # Sweep tracking: (sweep_bar_idx, sweep_sl, last_swing_high_at_sweep, last_swing_low_at_sweep)
        self._sweep_state_long:  Optional[tuple] = None  # (sweep_idx, sweep_sl, swing_hi_level)
        self._sweep_state_short: Optional[tuple] = None  # (sweep_idx, sweep_sl, swing_lo_level)

    def _htf_dir_at(self, ts) -> int:
        if self._htf_ts is None:
            return 0
        idx = int(np.searchsorted(self._htf_ts, ts, side="right")) - 1
        if idx < 0:
            return 0
        return int(self._htf_dir[idx])

    def _last_swing_high(self, before_i: int, lookback: int = 50) -> Optional[float]:
        # Only look at swings confirmed at least swing_n bars ago (no look-ahead)
        confirmed_before = before_i - self.swing_n
        lo = max(0, confirmed_before - lookback)
        arr = self._swing_high[lo:confirmed_before]
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None

    def _last_swing_low(self, before_i: int, lookback: int = 50) -> Optional[float]:
        confirmed_before = before_i - self.swing_n
        lo = max(0, confirmed_before - lookback)
        arr = self._swing_low[lo:confirmed_before]
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None

    def _find_bear_fvg_in_range(self, from_i: int, to_i: int) -> Optional[tuple]:
        """Scan [from_i, to_i] for bearish FVG (high[j] < low[j-2]).
        Returns (fvg_mid, fvg_lo=high[j], fvg_hi=low[j-2]) of the first valid one."""
        lo = max(2, from_i)
        hi = min(self._n - 1, to_i)
        for j in range(lo, hi + 1):
            if self._high[j] < self._low[j - 2]:
                gap = self._low[j - 2] - self._high[j]
                if gap >= self.min_fvg_pts:
                    fvg_mid = (self._high[j] + self._low[j - 2]) / 2
                    return (fvg_mid, self._high[j], self._low[j - 2])
        return None

    def _find_bull_fvg_in_range(self, from_i: int, to_i: int) -> Optional[tuple]:
        """Scan [from_i, to_i] for bullish FVG (low[j] > high[j-2]).
        Returns (fvg_mid, fvg_lo=high[j-2], fvg_hi=low[j]) of the first valid one."""
        lo = max(2, from_i)
        hi = min(self._n - 1, to_i)
        for j in range(lo, hi + 1):
            if self._low[j] > self._high[j - 2]:
                gap = self._low[j] - self._high[j - 2]
                if gap >= self.min_fvg_pts:
                    fvg_mid = (self._low[j] + self._high[j - 2]) / 2
                    return (fvg_mid, self._high[j - 2], self._low[j])
        return None

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        min_i = self.swing_n * 2 + 4
        if i < min_i:
            return None

        # ── Check pending FVG fill ────────────────────────────────────────────
        if self._pending is not None:
            p = self._pending
            # Expiry
            if i - p.armed_at > self.fvg_expiry_bars:
                self._pending = None
            elif not state.has_open_position:
                # LONG: price pulls back into FVG (bar.low touches or crosses fvg_mid)
                if p.direction == Direction.LONG and bar.low <= p.fvg_mid:
                    self._pending = None
                    sl = p.sweep_sl - self.sl_buffer_pips * self.pip_size
                    stop = p.fvg_mid - sl
                    if stop > 0:
                        return Signal(
                            direction=Direction.LONG,
                            entry=p.fvg_mid,
                            sl=sl,
                            tp1=p.fvg_mid + p.tp1_r * stop,
                            risk_pct=self.risk_pct,
                            tp1_frac=0.6,
                            tp2_frac=0.0,
                            trail=True,
                            label="ict_sweep_long",
                        )
                # SHORT: price pulls back into FVG (bar.high touches fvg_mid)
                elif p.direction == Direction.SHORT and bar.high >= p.fvg_mid:
                    self._pending = None
                    sl = p.sweep_sl + self.sl_buffer_pips * self.pip_size
                    stop = sl - p.fvg_mid
                    if stop > 0:
                        return Signal(
                            direction=Direction.SHORT,
                            entry=p.fvg_mid,
                            sl=sl,
                            tp1=p.fvg_mid - p.tp1_r * stop,
                            risk_pct=self.risk_pct,
                            tp1_frac=0.6,
                            tp2_frac=0.0,
                            trail=True,
                            label="ict_sweep_short",
                        )
        if state.has_open_position:
            return None

        htf = self._htf_dir_at(bar.ts)

        # ── LONG setup: sweep of swing low → ChoCH above swing high → bear FVG ──
        if self.direction in ("bear", "both"):
            sl_level = self._last_swing_low(i, lookback=30)
            if sl_level is not None:
                # Step 1: detect sweep of swing low
                if bar.low < sl_level and bar.close > sl_level:
                    sh_at_sweep = self._last_swing_high(i, lookback=30)
                    self._sweep_state_long = (i, bar.low, sh_at_sweep)

                # Step 2: if we have a recent sweep, look for ChoCH (close above swing high)
                if self._sweep_state_long is not None:
                    sweep_i, sweep_low, sh_level = self._sweep_state_long
                    age = i - sweep_i
                    if age > self.mss_bars:
                        self._sweep_state_long = None
                    elif sh_level is not None and bar.close > sh_level:
                        # ChoCH confirmed — HTF check
                        if not (self.htf_agree and htf < 0):
                            # Find bearish FVG in the impulse leg (sweep to ChoCH)
                            fvg = self._find_bear_fvg_in_range(sweep_i, i)
                            if fvg is not None:
                                fvg_mid, fvg_lo, fvg_hi = fvg
                                # Only arm if price is currently ABOVE fvg_mid (we need pullback)
                                if bar.close > fvg_mid:
                                    self._pending = _Pending(
                                        direction=Direction.LONG,
                                        fvg_mid=fvg_mid,
                                        fvg_lo=fvg_lo,
                                        fvg_hi=fvg_hi,
                                        sweep_sl=sweep_low,
                                        armed_at=i,
                                        tp1_r=self.tp1_r,
                                    )
                        self._sweep_state_long = None  # consumed

        # ── SHORT setup: sweep of swing high → ChoCH below swing low → bull FVG ──
        if self.direction in ("bull", "both"):
            sh_level = self._last_swing_high(i, lookback=30)
            if sh_level is not None:
                # Step 1: sweep of swing high
                if bar.high > sh_level and bar.close < sh_level:
                    sl_at_sweep = self._last_swing_low(i, lookback=30)
                    self._sweep_state_short = (i, bar.high, sl_at_sweep)

                # Step 2: ChoCH below swing low
                if self._sweep_state_short is not None:
                    sweep_i, sweep_high, sl_lev = self._sweep_state_short
                    age = i - sweep_i
                    if age > self.mss_bars:
                        self._sweep_state_short = None
                    elif sl_lev is not None and bar.close < sl_lev:
                        # ChoCH confirmed
                        if not (self.htf_agree and htf > 0):
                            fvg = self._find_bull_fvg_in_range(sweep_i, i)
                            if fvg is not None:
                                fvg_mid, fvg_lo, fvg_hi = fvg
                                if bar.close < fvg_mid:
                                    self._pending = _Pending(
                                        direction=Direction.SHORT,
                                        fvg_mid=fvg_mid,
                                        fvg_lo=fvg_lo,
                                        fvg_hi=fvg_hi,
                                        sweep_sl=sweep_high,
                                        armed_at=i,
                                        tp1_r=self.tp1_r,
                                    )
                        self._sweep_state_short = None

        return None
