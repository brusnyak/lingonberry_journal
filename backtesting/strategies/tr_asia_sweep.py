"""
TR Asia Sweep — Asia range liquidity sweep + 1m FVG 50% retest entry.

Manual review (203 NAS100 trades, 1m chart, 15m structure):
  - asia_night: 14W/3L=82% — Asia range swept → reversal
  - fvg_50: 7W/2L=78% — 1m FVG 50% retest entry

TF stack (REQUIRED):
  data = {"1": df_1m, "15": df_15m}

Setup (long — Asia LOW sweep):
  1. 15m session (22:00–07:00 UTC): compute Asia range high/low from 15m bars
  2. During London/NY (07:00–21:00 UTC): 1m bar wicks below Asia LOW, closes back above
  3. Scan backward on 1m: find bearish FVG (b[j].high < b[j-2].low) formed during the drop
     The FVG gap is above current price — price fills it upward
  4. Pending LONG at FVG midpoint when 1m bar.high >= fvg_mid
  5. SL: b[j].high - sl_buffer (below the FVG bottom)
  6. TP: fvg_mid + tp_r × (fvg_mid - sl)

Short (Asia HIGH sweep) is the mirror.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import datetime

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


@dataclass
class _PendingSetup:
    direction: Direction
    fvg_mid: float
    sl: float
    tp1: float
    risk_pct: float
    bars_remaining: int


class TrAsiaSweep(Strategy):
    """Asia range (15m) sweep + 1m FVG 50% retest reversal."""

    spaces = {
        "sl_buffer_pts": [3, 5, 10, 20],
        "tp1_r": [1.5, 2.0, 3.0],
        "sweep_lookback": [5, 10, 20, 30],   # 1m bars to scan backward for FVG
        "fvg_entry_bars": [20, 40, 80],       # 1m bars to wait for FVG mid touch
        "min_fvg_pts": [3, 5, 10],
    }

    def __init__(
        self,
        sl_buffer_pts: float = 5.0,
        tp1_r: float = 2.0,
        tp1_frac: float = 0.6,
        risk_pct: float = 0.005,
        pip_size: float = 1.0,
        direction: str = "both",
        asia_start_h: int = 22,
        asia_end_h: int = 7,
        active_start_h: int = 7,
        active_end_h: int = 21,
        sweep_lookback: int = 10,
        fvg_entry_bars: int = 40,
        min_fvg_pts: float = 5.0,
    ):
        self.sl_buffer_pts = sl_buffer_pts
        self.tp1_r = tp1_r
        self.tp1_frac = tp1_frac
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction
        self.asia_start_h = asia_start_h
        self.asia_end_h = asia_end_h
        self.active_start_h = active_start_h
        self.active_end_h = active_end_h
        self.sweep_lookback = sweep_lookback
        self.fvg_entry_bars = fvg_entry_bars
        self.min_fvg_pts = min_fvg_pts

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _in_asia(self, hour: int) -> bool:
        # 22:00–07:00 UTC crosses midnight
        if self.asia_start_h > self.asia_end_h:
            return hour >= self.asia_start_h or hour < self.asia_end_h
        return self.asia_start_h <= hour < self.asia_end_h

    def _in_active(self, hour: int) -> bool:
        return self.active_start_h <= hour < self.active_end_h

    def _compute_asia_ranges_15m(self, df15: pd.DataFrame) -> Dict[datetime.date, Tuple[float, float]]:
        """
        Build {active_session_date: (asia_high, asia_low)} from 15m bars.
        Asia session for active day D = 15m bars in [22:00 UTC day D-1, 07:00 UTC day D).
        """
        ranges: Dict[datetime.date, Tuple[float, float]] = {}
        asia_h = -np.inf
        asia_l = np.inf
        in_asia = False

        for ts, row in df15.iterrows():
            h = ts.hour
            if self._in_asia(h):
                asia_h = max(asia_h, row["high"])
                asia_l = min(asia_l, row["low"])
                in_asia = True
            elif in_asia:
                # Transition out of Asia (into active session)
                if asia_h > asia_l and not np.isinf(asia_h):
                    ranges[ts.date()] = (asia_h, asia_l)
                asia_h = -np.inf
                asia_l = np.inf
                in_asia = False

        return ranges

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def init(self, data: dict) -> None:
        # Entry TF: "1" (1m bars)
        entry_key = "1" if "1" in data else next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)

        self._high  = df["high"].to_numpy()
        self._low   = df["low"].to_numpy()
        self._close = df["close"].to_numpy()
        self._ts    = df.index

        # Precompute Asia ranges from 15m if available
        if "15" in data:
            df15 = data["15"].copy()
            if "ts" in df15.columns:
                df15 = df15.set_index("ts")
            df15.sort_index(inplace=True)
            self._asia_ranges: Optional[Dict] = self._compute_asia_ranges_15m(df15)
        else:
            self._asia_ranges = None
            # Fallback: track on-the-fly from entry TF
            self._asia_high_live: float = float("nan")
            self._asia_low_live:  float = float("nan")
            self._asia_date_live: Optional[str] = None

        self._pending: Optional[_PendingSetup] = None

    def _get_asia_range(self, bar: BarData) -> Optional[Tuple[float, float]]:
        ts = pd.Timestamp(self._ts[bar.index])
        if self._asia_ranges is not None:
            return self._asia_ranges.get(ts.date())
        # Fallback: live tracking
        h = ts.hour
        d = str(ts.date())
        if self._in_asia(h):
            if d != self._asia_date_live:
                self._asia_high_live = bar.high
                self._asia_low_live  = bar.low
                self._asia_date_live = d
            else:
                self._asia_high_live = max(self._asia_high_live, bar.high)
                self._asia_low_live  = min(self._asia_low_live,  bar.low)
            return None  # in Asia session, no active range yet
        if np.isnan(self._asia_high_live):
            return None
        return (self._asia_high_live, self._asia_low_live)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        ts = pd.Timestamp(self._ts[i])
        h = ts.hour

        # With 15m precomputed ranges, skip Asia session bars entirely
        if self._asia_ranges is not None and self._in_asia(h):
            return None

        asia = self._get_asia_range(bar)
        if asia is None:
            return None
        asia_h, asia_l = asia

        # ── Service pending entry ────────────────────────────────────────────
        if self._pending is not None and not state.has_open_position:
            p = self._pending
            p.bars_remaining -= 1
            triggered = (
                (p.direction == Direction.LONG  and bar.high >= p.fvg_mid) or
                (p.direction == Direction.SHORT and bar.low  <= p.fvg_mid)
            )
            if triggered:
                self._pending = None
                return Signal(
                    direction=p.direction,
                    entry=p.fvg_mid,
                    sl=p.sl,
                    tp1=p.tp1,
                    risk_pct=p.risk_pct,
                    tp1_frac=self.tp1_frac,
                    tp2_frac=0.0,
                    trail=True,
                    label="asia_sweep_fvg50",
                )
            if p.bars_remaining <= 0:
                self._pending = None

        if state.has_open_position:
            return None

        if not self._in_active(h):
            return None

        if self._pending is not None:
            return None

        buf = self.sl_buffer_pts

        # Bull sweep: 1m bar wicks below Asia LOW, closes back above
        if self.direction in ("bull", "both"):
            if bar.low < asia_l and bar.close > asia_l:
                sweep_sl = bar.low - buf
                fvg = self._find_fvg_bull(i, sweep_sl)
                if fvg is not None:
                    self._pending = fvg

        # Bear sweep: 1m bar wicks above Asia HIGH, closes back below
        if self.direction in ("bear", "both") and self._pending is None:
            if bar.high > asia_h and bar.close < asia_h:
                sweep_sl = bar.high + buf
                fvg = self._find_fvg_bear(i, sweep_sl)
                if fvg is not None:
                    self._pending = fvg

        return None

    # ── FVG scanners ──────────────────────────────────────────────────────────

    def _find_fvg_bull(self, i: int, sweep_sl: float) -> Optional[_PendingSetup]:
        """
        Scan backward on 1m from sweep bar for a bearish FVG (gap above current price).
        Bearish FVG: b[j].high < b[j-2].low → gap between them → price fills upward.
        Take the lowest fvg_mid (first one price reaches on recovery).
        """
        best: Optional[_PendingSetup] = None
        limit = max(2, i - self.sweep_lookback)
        for j in range(i, limit - 1, -1):
            if j < 2:
                break
            b0_high = self._high[j]
            b2_low  = self._low[j - 2]
            if b0_high >= b2_low:
                continue
            gap = b2_low - b0_high
            if gap < self.min_fvg_pts:
                continue
            fvg_mid = (b0_high + b2_low) / 2.0
            if fvg_mid <= self._close[i]:
                continue
            sl = min(b0_high - self.sl_buffer_pts, sweep_sl)
            stop = fvg_mid - sl
            if stop < self.min_fvg_pts:
                continue
            setup = _PendingSetup(
                direction=Direction.LONG,
                fvg_mid=fvg_mid,
                sl=sl,
                tp1=fvg_mid + self.tp1_r * stop,
                risk_pct=self.risk_pct,
                bars_remaining=self.fvg_entry_bars,
            )
            if best is None or fvg_mid < best.fvg_mid:
                best = setup
        return best

    def _find_fvg_bear(self, i: int, sweep_sl: float) -> Optional[_PendingSetup]:
        """
        Scan backward on 1m from sweep bar for a bullish FVG (gap below current price).
        Bullish FVG: b[j].low > b[j-2].high → gap between them → price fills downward.
        Take the highest fvg_mid (first one price reaches on pullback).
        """
        best: Optional[_PendingSetup] = None
        limit = max(2, i - self.sweep_lookback)
        for j in range(i, limit - 1, -1):
            if j < 2:
                break
            b0_low  = self._low[j]
            b2_high = self._high[j - 2]
            if b0_low <= b2_high:
                continue
            gap = b0_low - b2_high
            if gap < self.min_fvg_pts:
                continue
            fvg_mid = (b0_low + b2_high) / 2.0
            if fvg_mid >= self._close[i]:
                continue
            sl = max(b0_low + self.sl_buffer_pts, sweep_sl)
            stop = sl - fvg_mid
            if stop < self.min_fvg_pts:
                continue
            setup = _PendingSetup(
                direction=Direction.SHORT,
                fvg_mid=fvg_mid,
                sl=sl,
                tp1=fvg_mid - self.tp1_r * stop,
                risk_pct=self.risk_pct,
                bars_remaining=self.fvg_entry_bars,
            )
            if best is None or fvg_mid > best.fvg_mid:
                best = setup
        return best
