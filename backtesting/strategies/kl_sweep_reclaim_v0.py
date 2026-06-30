"""
Key-level sweep + reclaim v0 — false-breakout reversal on 15m FX.

Hypothesis: price wicks below the PRIOR DAY's low (stop run / liquidity sweep),
then reclaims it and trades back above VWAP/EMA20 → fade the sweep, long. Mirror
at the prior day's high for shorts. Bullish/bearish regime gated by EMA200.

Causality (the only thing that matters in a reversal backtest):
  - VWAP: session-anchored cumulative (resets 00:00 UTC). cumsum includes only
    bars up to i. No future.
  - prior-day low/high: yesterday's FINALIZED extreme, shifted one day. Bar i
    never sees today's still-forming high/low.
  - EMA20/EMA200: ewm — past+present only.
  - Trigger is an EVENT (reclaim cross this bar), not a state, so it fires once
    per sweep instead of every bar the condition holds.

Run with next_bar_fill=True.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class KlSweepReclaimV0(Strategy):
    def __init__(
        self,
        reclaim: str = "vwap",     # "vwap" or "ema20" — the reclaim confirmation line
        sweep_lookback: int = 6,    # bars to measure the sweep low/high for SL anchor
        atr_buffer: float = 0.5,    # ATR multiples added beyond the sweep extreme
        rr: float = 1.5,
        atr_period: int = 14,
        risk_pct: float = 0.005,
        use_regime: bool = True,    # EMA200 regime gate
        allowed_hours: Optional[set[int]] = None,  # UTC entry-hour gate; None = all
        entry_tf: str = "15",
    ) -> None:
        self.reclaim = reclaim
        self.sweep_lookback = sweep_lookback
        self.atr_buffer = atr_buffer
        self.rr = rr
        self.atr_period = atr_period
        self.risk_pct = risk_pct
        self.use_regime = use_regime
        self.allowed_hours = allowed_hours
        self.entry_tf = entry_tf

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        df = data[self.entry_tf].copy()
        high, low, close = df["high"], df["low"], df["close"]
        vol = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)

        # Session-anchored VWAP (UTC day). Cumulative => causal.
        day = df["ts"].dt.floor("D")
        tp = (high + low + close) / 3.0
        v = vol.where(vol > 0, 1.0)  # tick-vol fallback to equal weight if zero
        cum_pv = (tp * v).groupby(day).cumsum()
        cum_v = v.groupby(day).cumsum()
        self.vwap = (cum_pv / cum_v).to_numpy()

        self.ema20 = close.ewm(span=20, adjust=False).mean().to_numpy()
        self.ema200 = close.ewm(span=200, adjust=False).mean().to_numpy()

        # Prior-day finalized low/high mapped onto each bar (shift one day).
        daily = df.groupby(day).agg(d_low=("low", "min"), d_high=("high", "max"))
        pdl_map = daily["d_low"].shift(1)
        pdh_map = daily["d_high"].shift(1)
        self.pdl = day.map(pdl_map).to_numpy()
        self.pdh = day.map(pdh_map).to_numpy()

        # ATR (Wilder-simple).
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(),
                        (low - prev_close).abs()], axis=1).max(axis=1)
        self.atr = tr.rolling(self.atr_period).mean().to_numpy()

        self.high = high.to_numpy()
        self.low = low.to_numpy()
        self.close = close.to_numpy()
        self._ref = self.vwap if self.reclaim == "vwap" else self.ema20
        self._warmup = max(self.atr_period, self.sweep_lookback, 200) + 1

        # Precompute UTC-hour gate (np datetime64 in next() has no .hour).
        if self.allowed_hours is None:
            self._hour_ok = np.ones(len(df), dtype=bool)
        else:
            self._hour_ok = df["ts"].dt.hour.isin(self.allowed_hours).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._warmup or state.has_open_position:
            return None
        if not self._hour_ok[i]:
            return None

        atr = self.atr[i]
        ref, ref_prev = self._ref[i], self._ref[i - 1]
        pdl, pdh = self.pdl[i], self.pdh[i]
        c, c_prev = self.close[i], self.close[i - 1]
        if not (np.isfinite(atr) and atr > 0 and np.isfinite(ref) and np.isfinite(ref_prev)):
            return None

        lo_win = self.low[i - self.sweep_lookback + 1: i + 1]
        hi_win = self.high[i - self.sweep_lookback + 1: i + 1]

        # ── LONG: swept prior-day low, reclaimed it this bar, above ref + regime ──
        if np.isfinite(pdl):
            swept = lo_win.min() < pdl                 # wick took out yesterday's low
            reclaim_event = c_prev <= pdl < c          # closed back above it THIS bar
            confirm = c > ref                          # above VWAP/EMA20
            regime_ok = (not self.use_regime) or c > self.ema200[i]
            if swept and reclaim_event and confirm and regime_ok:
                sl = lo_win.min() - self.atr_buffer * atr
                risk = c - sl
                if risk > 0:
                    return Signal(direction=Direction.LONG, entry=c, sl=sl,
                                  tp1=c + self.rr * risk, risk_pct=self.risk_pct,
                                  tp1_frac=1.0, trail=False, label="kl_long")

        # ── SHORT: mirror at prior-day high ──
        if np.isfinite(pdh):
            swept = hi_win.max() > pdh
            reclaim_event = c_prev >= pdh > c
            confirm = c < ref
            regime_ok = (not self.use_regime) or c < self.ema200[i]
            if swept and reclaim_event and confirm and regime_ok:
                sl = hi_win.max() + self.atr_buffer * atr
                risk = sl - c
                if risk > 0:
                    return Signal(direction=Direction.SHORT, entry=c, sl=sl,
                                  tp1=c - self.rr * risk, risk_pct=self.risk_pct,
                                  tp1_frac=1.0, trail=False, label="kl_short")
        return None
