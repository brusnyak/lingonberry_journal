"""
Lvl2 ORB, payoff variant 2 — pre-registered in CLEAN.md #14.3 before running,
to avoid tuning drift on our own data.

Only change from `orb.py` (kept as a separate class, not a parameter, so
this stays a single un-gridded variant): stop moves from the range MIDPOINT
to the OPPOSITE side of the opening range (full-range stop), and the target
is a fixed 10R with EOD as a backstop exit if neither is hit intraday --
matching the Zarattini & Aronow (2023) ORB spec more closely than the first
pass. Same opening range window, same one-trade-per-day rule, same NAS100/5m
instrument. No other change.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class OrbNyWideStop(Strategy):
    """
    session_tz/session_open_min/or_len_min/entry_end_min/eod_min let this
    same mechanism be pointed at a different market's own real session open
    -- e.g. NAS100 uses NYSE cash open (09:30 America/New_York, the default,
    unchanged); FX has no single "cash open" but London (08:00 UTC) is the
    standard highest-volume session-open convention. This is picking ONE
    well-established convention per asset class, not fitting a threshold to
    our own data -- the opening-range window itself (15 min) and stop/target
    mechanics are unchanged.
    """
    def __init__(self, risk_pct: float = 0.005, direction: str = "both", target_r: float = 10.0,
                 session_tz: str = "America/New_York", session_open_min: int = 9 * 60 + 30,
                 or_len_min: int = 15, entry_end_min: int = 15 * 60, eod_min: int = 15 * 60 + 55,
                 htf_key: str | None = None, htf_ema_period: int = 50):
        """
        htf_key: if set (e.g. "240"), gates entries to agree with that
        timeframe's EMA(htf_ema_period) slope direction -- forensics on this
        strategy's own trade population (backtesting/lvl2_orb/trade_forensics.py)
        found a clean split (PF 1.94 aligned vs 0.54 against, n=203/156),
        consistent with the literature's own recommended ORB trend filter.
        Tested here with real discovery/holdout discipline, not just on the
        combined set the forensics pass used.
        """
        self.risk_pct = risk_pct
        self.direction = direction
        self.target_r = target_r
        self.session_tz = session_tz
        self.session_open_min = session_open_min
        self.or_len_min = or_len_min
        self.entry_end_min = entry_end_min
        self.eod_min = eod_min
        self.htf_key = htf_key
        self.htf_ema_period = htf_ema_period
        self._last_trade_day = -1

    def init(self, data: dict) -> None:
        entry_key = self.htf_key and next(k for k in data if k != self.htf_key) or next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        self._htf_up_per_bar = None
        if self.htf_key:
            df_htf = data[self.htf_key].copy()
            if "ts" in df_htf.columns:
                df_htf = df_htf.set_index("ts", drop=False)
            df_htf.sort_index(inplace=True)
            close = df_htf["close"].to_numpy()
            alpha = 2 / (self.htf_ema_period + 1)
            ema = np.full(len(close), np.nan)
            p = self.htf_ema_period
            if len(close) >= p:
                ema[p - 1] = close[:p].mean()
                for i in range(p, len(close)):
                    ema[i] = alpha * close[i] + (1 - alpha) * ema[i - 1]
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

        or_start, or_end = self.session_open_min, self.session_open_min + self.or_len_min
        # Infer the entry timeframe's own bar duration from the data instead
        # of assuming 5m -- needed to test this strategy on other entry TFs.
        ts_series = pd.to_datetime(df["ts"]) if "ts" in df.columns else pd.to_datetime(pd.Series(df.index))
        diffs_sec = ts_series.diff().dropna().dt.total_seconds()
        bar_minutes = float(diffs_sec.median() / 60) if len(diffs_sec) > 0 else 5.0
        n_or_bars = max(1, round(self.or_len_min / bar_minutes))
        in_or = (mins >= or_start) & (mins < or_end)
        tmp = pd.DataFrame({
            "day": self._day_ord,
            "hi": np.where(in_or, df["high"].to_numpy(), np.nan),
            "lo": np.where(in_or, df["low"].to_numpy(), np.nan),
            "n_or": in_or.astype(int),
        })
        g = tmp.groupby("day").agg(or_high=("hi", "max"), or_low=("lo", "min"),
                                   n_or=("n_or", "sum"))
        g.loc[g["n_or"] < n_or_bars, ["or_high", "or_low"]] = np.nan
        mapped = tmp[["day"]].merge(g, left_on="day", right_index=True, how="left")
        self._or_high = mapped["or_high"].to_numpy()
        self._or_low = mapped["or_low"].to_numpy()

        self._entry_ok = ((mins >= or_end) & (mins < self.entry_end_min)).to_numpy()
        self._eod = (mins >= self.eod_min).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position or not self._entry_ok[i]:
            return None
        if self._day_ord[i] == self._last_trade_day:
            return None
        or_h, or_l = self._or_high[i], self._or_low[i]
        if np.isnan(or_h) or np.isnan(or_l):
            return None
        close = bar.close
        htf_ok_long = self._htf_up_per_bar is None or self._htf_up_per_bar[i]
        htf_ok_short = self._htf_up_per_bar is None or not self._htf_up_per_bar[i]

        if close > or_h and self.direction in ("long", "both") and htf_ok_long:
            self._last_trade_day = self._day_ord[i]
            risk = close - or_l  # full-range stop, not midpoint
            return Signal(direction=Direction.LONG, entry=close, sl=or_l,
                          tp1=close + self.target_r * risk, risk_pct=self.risk_pct,
                          tp1_frac=0.0, tp2_frac=0.0, trail=False,
                          label="orb_wide_long")
        if close < or_l and self.direction in ("short", "both") and htf_ok_short:
            self._last_trade_day = self._day_ord[i]
            risk = or_h - close
            return Signal(direction=Direction.SHORT, entry=close, sl=or_h,
                          tp1=close - self.target_r * risk, risk_pct=self.risk_pct,
                          tp1_frac=0.0, tp2_frac=0.0, trail=False,
                          label="orb_wide_short")
        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return bool(self._eod[bar.index])
