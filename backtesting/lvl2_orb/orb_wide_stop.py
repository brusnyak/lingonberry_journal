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
                 htf_key: str | None = None, htf_ema_period: int = 50,
                 vol_atr_period: int = 14, vol_rolling_window: int = 100, vol_min_pctile: float | None = None,
                 require_retest: bool = False, ltf_key: str | None = None, ltf_ema_period: int = 20,
                 multi_target: bool = False, tp1_r: float = 2.0, tp2_r: float = 5.0,
                 confirm_bars: int = 0):
        """
        confirm_bars: DISTINCT from require_retest (which required a full
        pullback to the OR level -- tested, rejected, worse both windows).
        This requires the breakout to simply HOLD for N consecutive closes
        beyond the level before entering (no pullback needed), a lighter
        "let it prove itself" filter per the user's separate "force wait to
        monitor price action" request.
        """
        """
        multi_target: per user's request (real trades showed the single
        10R target is rarely reached -- with tp1_frac/tp2_frac both 0.0,
        NOTHING closes until either EOD or the far target, so almost every
        trade's actual exit is the EOD backstop, not a clean R-multiple).
        When True, adds a genuine partial-close ladder: 50% at tp1_r,
        30% at tp2_r, remaining 20% rides to target_r (or EOD). Fib-like
        progressive spacing (2R/5R/10R), not fit to our own data.
        """
        """
        require_retest: per user's manual-review finding (real trades,
        n/a to forensics -- direct observation) -- ORB was entering on the
        very first close beyond the opening range, without waiting to see
        if the breakout holds. If True, the first breakout in a direction
        only arms a pending signal; entry fires on a SECOND close beyond
        the level after price has pulled back and touched it again (a
        break-retest-continuation pattern), not on the first touch.

        ltf_key: if set (e.g. "30"), ADDS a second, faster trend-agreement
        check alongside htf_key (both must agree, not either/or) -- per
        user's request to see if a same-day local trend read recovers some
        of the reversal days the slow 240m HTF filter blocks (diagnosed in
        CLEAN.md #26: 6/8 of the biggest missed days were HTF-blocked moves
        that later reversed into the allowed direction, which the 240m EMA
        was too slow to catch same-day).
        """
        """
        htf_key: if set (e.g. "240"), gates entries to agree with that
        timeframe's EMA(htf_ema_period) slope direction -- forensics on this
        strategy's own trade population (backtesting/lvl2_orb/trade_forensics.py)
        found a clean split (PF 1.94 aligned vs 0.54 against, n=203/156),
        consistent with the literature's own recommended ORB trend filter.
        Tested here with real discovery/holdout discipline, not just on the
        combined set the forensics pass used.

        vol_min_pctile: if set (e.g. 0.33), skip entries when the HTF ATR's
        CAUSAL rolling percentile (rank within the trailing vol_rolling_window
        bars only -- never the full dataset, which would be lookahead) is
        below this threshold. Trait forensics (trait_forensics.py) found low-
        vol entries underperform (PF 1.35 vs ~2.0 mid/high) on a full-sample
        rank; this rolling version is what a live strategy could actually use,
        tested here with real discovery/holdout discipline before trusting it.
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
        self.vol_atr_period = vol_atr_period
        self.vol_rolling_window = vol_rolling_window
        self.vol_min_pctile = vol_min_pctile
        self.require_retest = require_retest
        self.ltf_key = ltf_key
        self.ltf_ema_period = ltf_ema_period
        self.multi_target = multi_target
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r
        self.confirm_bars = confirm_bars
        self._last_trade_day = -1
        self._hold_count: dict = {}    # day_ord -> consecutive bars held beyond the level
        self._hold_dir: dict = {}      # day_ord -> direction currently being held
        self._pending_dir: dict = {}   # day_ord -> 1/-1, breakout seen, awaiting retest
        self._retested: dict = {}      # day_ord -> True once price has touched back

    @staticmethod
    def _ema_slope_up(close: np.ndarray, period: int) -> np.ndarray:
        alpha = 2 / (period + 1)
        ema = np.full(len(close), np.nan)
        if len(close) >= period:
            ema[period - 1] = close[:period].mean()
            for i in range(period, len(close)):
                ema[i] = alpha * close[i] + (1 - alpha) * ema[i - 1]
        return np.concatenate([[False], np.diff(ema) > 0])

    @staticmethod
    def _map_to_entry_bars(htf_ts: np.ndarray, ltf_ts: np.ndarray, values: np.ndarray, n: int) -> np.ndarray:
        idx = np.searchsorted(htf_ts, ltf_ts, side="right") - 1
        valid = idx >= 0
        out = np.zeros(n, dtype=bool)
        out[valid] = values[idx[valid]]
        return out

    def init(self, data: dict) -> None:
        exclude = {k for k in (self.htf_key, self.ltf_key) if k}
        entry_key = next(k for k in data if k not in exclude) if exclude else next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        self._htf_up_per_bar = None
        self._vol_ok_per_bar = None
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

            if self.vol_min_pctile is not None:
                htf_high = df_htf["high"].to_numpy()
                htf_low = df_htf["low"].to_numpy()
                prev_close = np.roll(close, 1)
                prev_close[0] = close[0]
                tr = np.maximum(htf_high - htf_low, np.maximum(
                    np.abs(htf_high - prev_close), np.abs(htf_low - prev_close)))
                atr = np.full(len(close), np.nan)
                ap = self.vol_atr_period
                if len(close) >= ap:
                    atr[ap - 1] = tr[:ap].mean()
                    for i in range(ap, len(close)):
                        atr[i] = (atr[i - 1] * (ap - 1) + tr[i]) / ap
                # CAUSAL rolling percentile: rank of today's ATR within the
                # trailing vol_rolling_window bars only (shift(1) so the
                # current bar's own ATR isn't part of its own window).
                atr_s = pd.Series(atr)
                roll_pctile = atr_s.rolling(self.vol_rolling_window).apply(
                    lambda w: (w.iloc[-1] > w.iloc[:-1]).mean() if len(w) > 1 else np.nan, raw=False
                ).to_numpy()
                vol_ok_htf = np.nan_to_num(roll_pctile, nan=0.0) >= self.vol_min_pctile
                self._vol_ok_per_bar = np.zeros(self._n, dtype=bool)
                self._vol_ok_per_bar[valid] = vol_ok_htf[idx[valid]]

        self._ltf_up_per_bar = None
        if self.ltf_key:
            df_ltf = data[self.ltf_key].copy()
            if "ts" in df_ltf.columns:
                df_ltf = df_ltf.set_index("ts", drop=False)
            df_ltf.sort_index(inplace=True)
            ltf_slope_up = self._ema_slope_up(df_ltf["close"].to_numpy(), self.ltf_ema_period)
            ltf_ts_arr = df_ltf["ts"].to_numpy() if "ts" in df_ltf.columns else df_ltf.index.to_numpy()
            entry_ts_arr = df["ts"].to_numpy() if "ts" in df.columns else df.index.to_numpy()
            self._ltf_up_per_bar = self._map_to_entry_bars(ltf_ts_arr, entry_ts_arr, ltf_slope_up, self._n)

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

    def _make_signal(self, direction: Direction, entry: float, sl: float, risk: float, label: str) -> Signal:
        sign = 1 if direction == Direction.LONG else -1
        if self.multi_target:
            return Signal(direction=direction, entry=entry, sl=sl,
                          tp1=entry + sign * self.tp1_r * risk,
                          tp2=entry + sign * self.tp2_r * risk,
                          tp3=entry + sign * self.target_r * risk,
                          risk_pct=self.risk_pct, tp1_frac=0.5, tp2_frac=0.3,
                          trail=False, label=label)
        return Signal(direction=direction, entry=entry, sl=sl,
                      tp1=entry + sign * self.target_r * risk, risk_pct=self.risk_pct,
                      tp1_frac=0.0, tp2_frac=0.0, trail=False, label=label)

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
        vol_ok = self._vol_ok_per_bar is None or self._vol_ok_per_bar[i]
        if not vol_ok:
            return None
        htf_ok_long = self._htf_up_per_bar is None or self._htf_up_per_bar[i]
        htf_ok_short = self._htf_up_per_bar is None or not self._htf_up_per_bar[i]
        ltf_ok_long = self._ltf_up_per_bar is None or self._ltf_up_per_bar[i]
        ltf_ok_short = self._ltf_up_per_bar is None or not self._ltf_up_per_bar[i]
        high, low = bar.high, bar.low

        broke_up = close > or_h and self.direction in ("long", "both")
        broke_down = close < or_l and self.direction in ("short", "both")

        if self.require_retest:
            # First breakout only ARMS a pending direction; entry requires
            # price to have pulled back and touched the level again, then
            # broken it a SECOND time. Filters (HTF/vol/LTF) are checked at
            # the actual entry moment, not when the pending state was armed
            # -- matches how a live decision would actually be gated.
            day = self._day_ord[i]
            pending = self._pending_dir.get(day)
            retested = self._retested.get(day, False)

            if pending is None:
                if broke_up:
                    self._pending_dir[day] = 1
                elif broke_down:
                    self._pending_dir[day] = -1
                return None

            if not retested:
                if pending == 1 and low <= or_h:
                    self._retested[day] = True
                elif pending == -1 and high >= or_l:
                    self._retested[day] = True
                # A close through the OPPOSITE level while still pending
                # invalidates the original breakout -- flip to the new one.
                if pending == 1 and broke_down:
                    self._pending_dir[day] = -1
                    self._retested[day] = False
                elif pending == -1 and broke_up:
                    self._pending_dir[day] = 1
                    self._retested[day] = False
                return None

            if pending == 1 and broke_up and htf_ok_long and vol_ok and ltf_ok_long:
                self._last_trade_day = day
                risk = close - or_l
                return self._make_signal(Direction.LONG, close, or_l, risk, "orb_wide_long")
            if pending == -1 and broke_down and htf_ok_short and vol_ok and ltf_ok_short:
                self._last_trade_day = day
                risk = or_h - close
                return self._make_signal(Direction.SHORT, close, or_h, risk, "orb_wide_short")
            # Pending direction failed to reconfirm -- flip if the opposite broke.
            if pending == 1 and broke_down:
                self._pending_dir[day] = -1
                self._retested[day] = False
            elif pending == -1 and broke_up:
                self._pending_dir[day] = 1
                self._retested[day] = False
            return None

        if self.confirm_bars > 0:
            day = self._day_ord[i]
            cur_dir = 1 if broke_up else (-1 if broke_down else None)
            if cur_dir is not None and self._hold_dir.get(day) == cur_dir:
                self._hold_count[day] = self._hold_count.get(day, 0) + 1
            elif cur_dir is not None:
                self._hold_dir[day] = cur_dir
                self._hold_count[day] = 1
            else:
                self._hold_dir[day] = None
                self._hold_count[day] = 0

            if broke_up and htf_ok_long and ltf_ok_long and self._hold_count.get(day, 0) >= self.confirm_bars:
                self._last_trade_day = day
                risk = close - or_l
                return self._make_signal(Direction.LONG, close, or_l, risk, "orb_wide_long")
            if broke_down and htf_ok_short and ltf_ok_short and self._hold_count.get(day, 0) >= self.confirm_bars:
                self._last_trade_day = day
                risk = or_h - close
                return self._make_signal(Direction.SHORT, close, or_h, risk, "orb_wide_short")
            return None

        if broke_up and htf_ok_long and ltf_ok_long:
            self._last_trade_day = self._day_ord[i]
            risk = close - or_l  # full-range stop, not midpoint
            return self._make_signal(Direction.LONG, close, or_l, risk, "orb_wide_long")
        if broke_down and htf_ok_short and ltf_ok_short:
            self._last_trade_day = self._day_ord[i]
            risk = or_h - close
            return self._make_signal(Direction.SHORT, close, or_h, risk, "orb_wide_short")
        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return bool(self._eod[bar.index])
