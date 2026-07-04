"""
Lvl2 (new family) -- literal VWAP crossover/bounce, per @PBInvesting's
publicly described rules (research pass, CLEAN.md #25), tested at the
user's request to check whether our earlier rejection (KL sweep+reclaim,
PF 0.99) was too narrow -- that test required a prior liquidity SWEEP
before the VWAP reclaim; PB's simplest setups (crossover/bounce/flush/
rejection) don't require one, just VWAP + a confirming 5m close.

Also a genuine mechanics fix vs. the project's existing `vwap_bounce_long/
short` columns (backtesting/features/vwap.py): those trigger off the ±1σ
BAND, not the VWAP centerline PB actually describes crossing. This
strategy crosses the literal VWAP line.

Spec, taken directly from the research (no evidence was found for any of
these setups -- this is a fair-test of the RULES, not a replication of a
verified track record, since none exists):
  - direction context: HTF trend (already in an uptrend/downtrend, matches
    PB's own framing "stock already above VWAP in an uptrend") -- reuses
    the same EMA-slope filter validated for ORB/OvernightDrift, not a new
    invention.
  - entry: price crosses VWAP centerline, confirmed by a close on the far
    side (PB: "ALWAYS wait for a 5-min close"), in the direction of the
    HTF trend.
  - stop: opposite side of VWAP by one recent ATR (PB gives no numeric
    stop rule beyond "5-min close back through VWAP" -- using ATR here so
    the stop is a fixed distance for position sizing, not a second closing
    candle, which the engine can't easily model as a stop-loss level).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.vwap import build_vwap_index


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


class VwapBounce(Strategy):
    def __init__(self, risk_pct: float = 0.005, atr_period: int = 14, stop_atr_mult: float = 1.5,
                 target_r: float = 3.0, htf_key: str | None = None, htf_ema_period: int = 50):
        self.risk_pct = risk_pct
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.target_r = target_r
        self.htf_key = htf_key
        self.htf_ema_period = htf_ema_period
        self._in_position_day = None

    def init(self, data: dict) -> None:
        entry_key = self.htf_key and next(k for k in data if k != self.htf_key) or next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        df_vwap = build_vwap_index(df.reset_index(drop=True))
        self._vwap = df_vwap["vwap"].to_numpy()
        close = df["close"].to_numpy()
        self._close = close
        prev_close = np.roll(close, 1)
        prev_vwap = np.roll(self._vwap, 1)
        prev_close[0] = close[0]
        prev_vwap[0] = self._vwap[0]
        # Literal VWAP crossover, confirmed by this bar's close (not the
        # ±1σ band the project's existing vwap_bounce_long/short use).
        self._cross_up = (prev_close < prev_vwap) & (close > self._vwap)
        self._cross_down = (prev_close > prev_vwap) & (close < self._vwap)

        self._atr = _atr(df["high"].to_numpy(), df["low"].to_numpy(), close, self.atr_period)

        self._htf_up_per_bar = None
        if self.htf_key:
            df_htf = data[self.htf_key].copy()
            if "ts" in df_htf.columns:
                df_htf = df_htf.set_index("ts", drop=False)
            df_htf.sort_index(inplace=True)
            htf_close = df_htf["close"].to_numpy()
            alpha = 2 / (self.htf_ema_period + 1)
            ema = np.full(len(htf_close), np.nan)
            p = self.htf_ema_period
            if len(htf_close) >= p:
                ema[p - 1] = htf_close[:p].mean()
                for i in range(p, len(htf_close)):
                    ema[i] = alpha * htf_close[i] + (1 - alpha) * ema[i - 1]
            slope_up = np.concatenate([[False], np.diff(ema) > 0])
            htf_ts = df_htf["ts"].to_numpy() if "ts" in df_htf.columns else df_htf.index.to_numpy()
            ltf_ts = df["ts"].to_numpy() if "ts" in df.columns else df.index.to_numpy()
            idx = np.searchsorted(htf_ts, ltf_ts, side="right") - 1
            valid = idx >= 0
            self._htf_up_per_bar = np.zeros(self._n, dtype=bool)
            self._htf_up_per_bar[valid] = slope_up[idx[valid]]

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position:
            return None
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None
        htf_up = self._htf_up_per_bar[i] if self._htf_up_per_bar is not None else None

        if self._cross_up[i] and (htf_up is None or htf_up):
            entry = bar.close
            sl = entry - self.stop_atr_mult * atr
            return Signal(direction=Direction.LONG, entry=entry, sl=sl,
                          tp1=entry + self.target_r * self.stop_atr_mult * atr,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="vwap_bounce_long")
        if self._cross_down[i] and (htf_up is None or not htf_up):
            entry = bar.close
            sl = entry + self.stop_atr_mult * atr
            return Signal(direction=Direction.SHORT, entry=entry, sl=sl,
                          tp1=entry - self.target_r * self.stop_atr_mult * atr,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="vwap_bounce_short")
        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return False
