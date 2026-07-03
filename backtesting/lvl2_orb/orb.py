"""
Lvl2 (new family) — Opening Range Breakout, NAS100.

Hypothesis class is TIME-ANCHORED session liquidity, not indicator state:
the first minutes of the NY equity open concentrate institutional order
flow; the direction that resolves the opening range tends to persist into
the session. Published evidence: Zarattini & Aronow (2023) on QQQ 5m ORB.
Nothing previously falsified in this project tested time-of-day anchoring
as the signal itself.

Spec was fixed EX-ANTE (see CLEAN.md) before the first backtest run:
  - opening range = 09:30-09:45 America/New_York (three 5m bars, DST-correct)
  - entry: first 5m close beyond the range, 09:45-15:00 NY, one trade/day
  - stop: range midpoint
  - exit: end of day (flat by 15:55 NY). No take-profit, no parameter grid.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class OrbNy(Strategy):
    def __init__(self, risk_pct: float = 0.005, direction: str = "both"):
        self.risk_pct = risk_pct
        self.direction = direction
        self._last_trade_day = -1

    def init(self, data: dict) -> None:
        df = next(iter(data.values())).copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        ts = pd.to_datetime(df["ts"])
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        ny = ts.dt.tz_convert("America/New_York")
        mins = ny.dt.hour * 60 + ny.dt.minute  # minutes since NY midnight

        # NY calendar day as ordinal, for grouping and one-trade-per-day
        day = ny.dt.date
        self._day_ord = pd.factorize(day)[0]

        # Opening range: bars whose NY time falls in [09:30, 09:45)
        in_or = (mins >= 9 * 60 + 30) & (mins < 9 * 60 + 45)
        tmp = pd.DataFrame({
            "day": self._day_ord,
            "hi": np.where(in_or, df["high"].to_numpy(), np.nan),
            "lo": np.where(in_or, df["low"].to_numpy(), np.nan),
            "n_or": in_or.astype(int),
        })
        g = tmp.groupby("day").agg(or_high=("hi", "max"), or_low=("lo", "min"),
                                   n_or=("n_or", "sum"))
        # Require the full 3-bar range (skip half-session/holiday days)
        g.loc[g["n_or"] < 3, ["or_high", "or_low"]] = np.nan
        mapped = tmp[["day"]].merge(g, left_on="day", right_index=True, how="left")
        self._or_high = mapped["or_high"].to_numpy()
        self._or_low = mapped["or_low"].to_numpy()

        self._entry_ok = ((mins >= 9 * 60 + 45) & (mins < 15 * 60)).to_numpy()
        self._eod = (mins >= 15 * 60 + 55).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position or not self._entry_ok[i]:
            return None
        if self._day_ord[i] == self._last_trade_day:
            return None
        or_h, or_l = self._or_high[i], self._or_low[i]
        if np.isnan(or_h) or np.isnan(or_l):
            return None
        mid = (or_h + or_l) / 2.0
        close = bar.close

        if close > or_h and self.direction in ("long", "both"):
            self._last_trade_day = self._day_ord[i]
            risk = close - mid
            return Signal(direction=Direction.LONG, entry=close, sl=mid,
                          tp1=close + 50 * risk, risk_pct=self.risk_pct,
                          tp1_frac=0.0, tp2_frac=0.0, trail=False,
                          label="orb_long")
        if close < or_l and self.direction in ("short", "both"):
            self._last_trade_day = self._day_ord[i]
            risk = mid - close
            return Signal(direction=Direction.SHORT, entry=close, sl=mid,
                          tp1=close - 50 * risk, risk_pct=self.risk_pct,
                          tp1_frac=0.0, tp2_frac=0.0, trail=False,
                          label="orb_short")
        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return bool(self._eod[bar.index])
