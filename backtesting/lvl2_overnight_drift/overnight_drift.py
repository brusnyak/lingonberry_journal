"""
Lvl2 (new family) -- Overnight drift, NAS100 index futures.

Third distinct mechanism class (not ORB's breakout-continuation, not
intraday momentum's close-to-close prediction): a pure calendar-time
position -- long from the cash-session close to the next cash-session
open, flat during the day. Decades of independent academic findings for
US equity indices/futures:
  - Lou, Polk & Skouras, "A Tug of War: Overnight vs Intraday Returns"
    (Yale, 2019) -- nearly all long-run index gains accrue overnight.
  - Federal Reserve Bank of New York Staff Report 917, "The Overnight
    Drift in U.S. Equity Returns" (2020).
  - Proposed mechanisms: dealer inventory-risk compensation (Boyarchenko,
    Larsen & Whelan 2023), resolution of uncertainty at the European open
    (Bondarenko & Muravyev 2023).

Chosen deliberately for NAS100 and NOT gold/FX: the mechanism is specific
to equity-index futures overnight positioning, which NAS100 (an index-
futures-tracked CFD) actually matches, unlike the closing-auction-specific
momentum mechanism tested previously (lvl2_intraday_momentum) that needed
real cash-equity auction microstructure NAS100 doesn't have.

Spec fixed EX-ANTE from the literature:
  - enter LONG at the cash session close (16:00 America/New_York)
  - exit at the next cash session open (09:30 America/New_York)
  - one position per overnight session, long-only (the literature's most
    consistent, most-replicated leg -- the "short intraday" complement is
    more mixed across studies and NOT included here to keep this a single
    clean test of the strongest claim, not a stacked bet)
  - stop: NOT in the literature (this is a return-predictability finding,
    not a risk-managed system) -- added here as ATR-based for position
    sizing/prop compliance, disclosed as our addition.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


class OvernightDrift(Strategy):
    """
    htf_key: if set (e.g. "240"), skip the overnight-long entry when that
    timeframe's EMA(htf_ema_period) slope is DOWN. Forensics on this
    strategy's own holdout drawdown (14.6% max DD, breaching both GFT
    accounts) found the driver was not gap risk but a genuine 43-trade
    losing streak (Jan 28-Mar 24 2026, 40L/4W) coinciding with a real
    NAS100 correction (-7.7% over the same window) -- an always-long
    strategy fighting a sustained downtrend. Same root cause and same fix
    already validated for ORB (CLEAN.md #16): gate on HTF trend agreement
    rather than betting blind every single day.
    """
    def __init__(
        self,
        risk_pct: float = 0.005,
        session_tz: str = "America/New_York",
        session_close_min: int = 16 * 60,   # 16:00 NY
        session_open_min: int = 9 * 60 + 30,  # 09:30 NY
        atr_period: int = 14,
        stop_atr_mult: float = 2.0,
        htf_key: str | None = None,
        htf_ema_period: int = 50,
    ):
        self.risk_pct = risk_pct
        self.session_tz = session_tz
        self.session_close_min = session_close_min
        self.session_open_min = session_open_min
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.htf_key = htf_key
        self.htf_ema_period = htf_ema_period
        self._last_entry_day = -1

    def init(self, data: dict) -> None:
        entry_key = self.htf_key and next(k for k in data if k != self.htf_key) or next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()
        self._atr = _atr(high, low, close, self.atr_period)

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

        ts = pd.to_datetime(df["ts"])
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        local = ts.dt.tz_convert(self.session_tz)
        mins = local.dt.hour * 60 + local.dt.minute
        day = local.dt.date
        self._day_ord = pd.factorize(day)[0]

        # Entry: first bar at/after the session close time. Exit: first bar
        # at/after the next session open time. should_close() checks the
        # latter directly rather than pre-computing an exit index, since the
        # engine drives bar-by-bar.
        self._entry_ok = (mins >= self.session_close_min).to_numpy()
        self._exit_ok = (mins >= self.session_open_min).to_numpy() & (mins < self.session_close_min).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position or not self._entry_ok[i]:
            return None
        d = self._day_ord[i]
        if d == self._last_entry_day:
            return None
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None
        if self._htf_up_per_bar is not None and not self._htf_up_per_bar[i]:
            return None

        self._last_entry_day = d
        close = bar.close
        sl = close - self.stop_atr_mult * atr
        return Signal(direction=Direction.LONG, entry=close, sl=sl,
                      tp1=close + 20 * self.stop_atr_mult * atr,  # effectively disabled; next-open is the real exit
                      risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                      trail=False, label="overnight_drift_long")

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return bool(self._exit_ok[bar.index])
