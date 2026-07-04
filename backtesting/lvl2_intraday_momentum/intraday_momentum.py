"""
Lvl2 (new family) -- Intraday time-series momentum.

Mechanism is genuinely distinct from ORB (breakout-continuation right after
the open): Gao, Han, Li & Zhou (2018, Journal of Financial Economics)
document that the return from the PRIOR session close to 10:00 America/
New_York ("first half-hour return", though it spans overnight + first 30m
of cash trading) predicts the return from 15:30-16:00 NY ("last half-hour
return") on US equities/ETFs. Mechanism candidates in the paper: infrequent
portfolio rebalancing (Bogousslavsky 2016), and late-informed trading into
the close. Cost-adjusted replication (Zarattini, Aziz & Barbon, SSRN
4824172) reports net Sharpe 1.33 on SPY, 2007-2024.

Spec fixed EX-ANTE, taken from the literature, not fit to our data:
  - first-window return = close(prior session) -> close(10:00 NY)
  - entry: 15:30 NY, direction = sign(first-window return)
  - exit: 16:00 NY (flat) -- matches the paper's holding window exactly
  - stop: NOT in the original paper (a pure return-predictability study,
    not a risk-managed system) -- added here as ATR(14)*stop_atr_mult for
    position sizing / prop-rule compliance. Disclosed as our addition, not
    literature-sourced.

The paper studies US equities/ETFs on the regular cash session. Testing
this on FX/commodities (24h-traded, no clean "prior close") is exploratory
extension beyond what the literature covers, not a replication -- flagged
as such wherever it's run.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.ict_structure import build_ict_structure_index


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


class IntradayMomentum(Strategy):
    def __init__(
        self,
        risk_pct: float = 0.005,
        direction: str = "both",
        session_tz: str = "America/New_York",
        first_window_end_min: int = 10 * 60,       # 10:00 NY
        entry_min: int = 15 * 60 + 30,              # 15:30 NY
        eod_min: int = 16 * 60,                      # 16:00 NY (flat)
        atr_period: int = 14,
        stop_atr_mult: float = 1.5,
        stop_mode: str = "atr",          # "atr" or "structure"
        structure_buffer_atr: float = 0.1,  # small pad beyond the swing level
        structure_left: int = 3,
        structure_right: int = 3,
    ):
        self.risk_pct = risk_pct
        self.direction = direction
        self.session_tz = session_tz
        self.first_window_end_min = first_window_end_min
        self.entry_min = entry_min
        self.eod_min = eod_min
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.stop_mode = stop_mode
        self.structure_buffer_atr = structure_buffer_atr
        self.structure_left = structure_left
        self.structure_right = structure_right
        self._last_trade_day = -1

    def init(self, data: dict) -> None:
        df = next(iter(data.values())).copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()
        self._close = close
        self._atr = _atr(high, low, close, self.atr_period)

        self._last_hl = None
        self._last_ll = None
        self._last_lh = None
        self._last_hh = None
        if self.stop_mode == "structure":
            from backtesting.features.ict_structure import IctStructureConfig
            struct_df = df[["ts", "open", "high", "low", "close"]].reset_index(drop=True)
            cfg = IctStructureConfig(left=self.structure_left, right=self.structure_right)
            struct = build_ict_structure_index(struct_df, cfg)
            # forward-fill so every bar sees the most recent CONFIRMED swing level
            # (build_ict_structure_index already only updates last_* at the
            # confirm bar, so this ffill introduces no lookahead)
            self._last_hl = struct["last_hl"].ffill().to_numpy()
            self._last_ll = struct["last_ll"].ffill().to_numpy()
            self._last_lh = struct["last_lh"].ffill().to_numpy()
            self._last_hh = struct["last_hh"].ffill().to_numpy()

        ts = pd.to_datetime(df["ts"])
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        local = ts.dt.tz_convert(self.session_tz)
        mins = local.dt.hour * 60 + local.dt.minute
        day = local.dt.date
        self._day_ord = pd.factorize(day)[0]
        n_days = self._day_ord.max() + 1 if len(self._day_ord) else 0

        # Prior session's last close, and this session's close at/just after
        # first_window_end_min -- both looked up per calendar day, mapped
        # back onto every bar of that day (causal: only uses info already
        # available by the time each bar happens).
        prior_close = np.full(n_days, np.nan)
        window_close = np.full(n_days, np.nan)
        last_close_seen = np.nan
        cur_day = -1
        for i in range(self._n):
            d = self._day_ord[i]
            if d != cur_day:
                if cur_day >= 0:
                    prior_close[d] = last_close_seen
                cur_day = d
            if np.isnan(window_close[d]) and mins.iloc[i] >= self.first_window_end_min:
                window_close[d] = close[i]
            last_close_seen = close[i]

        first_window_ret = np.full(n_days, np.nan)
        valid_days = ~np.isnan(prior_close) & ~np.isnan(window_close) & (prior_close > 0)
        first_window_ret[valid_days] = (window_close[valid_days] - prior_close[valid_days]) / prior_close[valid_days]

        self._signal_per_day = np.where(first_window_ret > 0, 1, np.where(first_window_ret < 0, -1, 0))
        self._entry_ok = (mins >= self.entry_min).to_numpy() & (mins < self.eod_min).to_numpy()
        self._eod = (mins >= self.eod_min).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position or not self._entry_ok[i]:
            return None
        d = self._day_ord[i]
        if d == self._last_trade_day:
            return None
        sig = self._signal_per_day[d] if d < len(self._signal_per_day) else 0
        if sig == 0:
            return None
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None

        close = bar.close
        if sig > 0 and self.direction in ("long", "both"):
            self._last_trade_day = d
            sl = self._structure_sl(i, close, atr, long=True)
            if sl is None:
                return None
            return Signal(direction=Direction.LONG, entry=close, sl=sl,
                          tp1=close + 20 * (close - sl),  # effectively disabled; EOD is the real exit
                          risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                          trail=False, label="intraday_mom_long")
        if sig < 0 and self.direction in ("short", "both"):
            self._last_trade_day = d
            sl = self._structure_sl(i, close, atr, long=False)
            if sl is None:
                return None
            return Signal(direction=Direction.SHORT, entry=close, sl=sl,
                          tp1=close - 20 * (sl - close),
                          risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                          trail=False, label="intraday_mom_short")
        return None

    def _structure_sl(self, i: int, close: float, atr: float, long: bool) -> Optional[float]:
        """Stop behind the nearest confirmed swing point, ATR fallback if
        no swing is available yet (e.g. start of dataset)."""
        if self.stop_mode != "structure":
            return close - self.stop_atr_mult * atr if long else close + self.stop_atr_mult * atr
        buf = self.structure_buffer_atr * atr
        if long:
            level = self._last_hl[i]
            if np.isnan(level):
                level = self._last_ll[i]
            if np.isnan(level) or level >= close:
                return close - self.stop_atr_mult * atr  # fallback: no usable swing below price
            return level - buf
        else:
            level = self._last_lh[i]
            if np.isnan(level):
                level = self._last_hh[i]
            if np.isnan(level) or level <= close:
                return close + self.stop_atr_mult * atr
            return level + buf

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return bool(self._eod[bar.index])
