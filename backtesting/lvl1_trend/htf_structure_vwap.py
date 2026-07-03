"""
Lvl2 — HTF CHoCH/BOS structure regime + LTF VWAP entry + structural exits.

Fixes two issues found by manual UI review of lvl1 (HtfEmaVwap):
  1. EMA21 slope is a laggy proxy for trend — it can still call "long" after
     a real bearish CHoCH+BOS has already flipped the structure. Regime is
     now sourced from backtesting.structure_lib.labels.label_structure()
     (causal, validated on synthetic ground truth this session), not an MA.
  2. The old tp1 was set 50R away specifically to disable it — realistic in
     backtest terms but not intraday-sane. TP1 is now the nearest prior-day
     high/low (partial close), remainder trails via ATR. SL moves to
     breakeven once a confirming BOS/CHoCH fires in the trade's direction
     (structural invalidation of the "trade was wrong" case, not a blind
     time/price trail).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.vwap import build_vwap_index
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _prior_day_high_low(ts: pd.Series, high: np.ndarray, low: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Causal: each bar sees only the FULL prior calendar day's high/low."""
    dates = ts.dt.date.to_numpy()
    df = pd.DataFrame({"date": dates, "high": high, "low": low})
    daily = df.groupby("date").agg(day_high=("high", "max"), day_low=("low", "min"))
    daily_shifted = daily.shift(1)  # yesterday's range, available from today's first bar
    mapped = pd.DataFrame({"date": dates}).merge(daily_shifted, on="date", how="left")
    return mapped["day_high"].to_numpy(), mapped["day_low"].to_numpy()


class HtfStructureVwap(Strategy):
    def __init__(
        self,
        htf_key: str = "60",
        swing_length: int = 3,
        atr_period: int = 14,
        atr_mult: float = 2.5,
        tp1_frac: float = 0.5,
        risk_pct: float = 0.005,
        direction: str = "both",
        min_rr: float = 1.0,
        cooldown_bars: int = 9,
        atr_ceiling_mult: float = 1.3,
    ):
        self.htf_key = htf_key
        self.swing_length = swing_length
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.tp1_frac = tp1_frac
        self.risk_pct = risk_pct
        self.direction = direction
        self.min_rr = min_rr
        self.cooldown_bars = cooldown_bars
        self.atr_ceiling_mult = atr_ceiling_mult
        self._last_close_i = -10**9
        # Session gate: avoid day-boundary bars (thin, unreliable structure
        # reads at session open/close) and the 12:30-14:00 UTC US news window
        # (CPI/NFP/FOMC-adjacent) -- both flagged from manual chart review.
        self.avoid_day_edge_hours = 1
        self.news_window_utc = (12, 30, 14, 0)
        # Chop gate: reuses the Efficiency Ratio classifier already built and
        # validated (backtesting/engine/regime.py) -- don't trade structure
        # breaks inside genuine accumulation, where they're mostly noise.
        self.er_period = 10
        self.er_threshold = 0.3

    def init(self, data: dict) -> None:
        entry_key = next(k for k in data if k != self.htf_key)
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)

        df_vwap = build_vwap_index(df.reset_index(drop=True))
        self._high = df["high"].to_numpy()
        self._low = df["low"].to_numpy()
        self._close = df["close"].to_numpy()
        self._ts = df["ts"].to_numpy() if "ts" in df.columns else df.index.to_numpy()
        self._n = len(df)

        self._vwap_1h = df_vwap["vwap_1h"].to_numpy()
        self._vwap_1l = df_vwap["vwap_1l"].to_numpy()
        self._vwap_bounce_long = df_vwap["vwap_bounce_long"].to_numpy()
        self._vwap_bounce_short = df_vwap["vwap_bounce_short"].to_numpy()
        self._atr = _atr(self._high, self._low, self._close, self.atr_period)

        self._pdh, self._pdl = _prior_day_high_low(df["ts"], self._high, self._low)

        # HTF CHoCH/BOS regime, mapped onto LTF bars
        df_htf = data[self.htf_key].copy()
        if "ts" in df_htf.columns:
            df_htf = df_htf.set_index("ts", drop=False)
        df_htf.sort_index(inplace=True)
        swings, levels = swing_points(df_htf, swing_length=self.swing_length, causal=True)
        labels = label_structure(df_htf, swings, levels)

        # Tradeable direction is set ONLY by a confirming BOS, never by a bare
        # CHoCH. A CHoCH is just the first hint of a possible reversal; taking
        # a trade on it alone (as the previous version of this strategy did)
        # produced exactly the "entered short right after price recovered
        # into an uptrend" mistakes caught by manual chart review. Only a
        # BOS in the new direction (which by definition requires the CHoCH's
        # reversal to have actually held and extended) confirms the flip.
        htf_regime = np.zeros(len(df_htf), dtype=np.int64)
        state = 0
        for i in range(len(df_htf)):
            if labels["bullish_bos"].iloc[i]:
                state = 1
            elif labels["bearish_bos"].iloc[i]:
                state = -1
            htf_regime[i] = state
        # Index of the most recent CONFIRMING (BOS) event in the current
        # direction's favor -- used to detect a NEW confirmation after a
        # position opens, not just "was ever confirmed historically."
        htf_last_bos_idx = np.full(len(df_htf), -1, dtype=np.int64)
        last_bos = -1
        for i in range(len(df_htf)):
            if labels["bullish_bos"].iloc[i] or labels["bearish_bos"].iloc[i]:
                last_bos = i
            htf_last_bos_idx[i] = last_bos

        htf_ts = df_htf["ts"].to_numpy() if "ts" in df_htf.columns else df_htf.index.to_numpy()
        idx = np.searchsorted(htf_ts, self._ts, side="right") - 1
        valid = idx >= 0
        self._regime_per_bar = np.zeros(self._n, dtype=np.int64)
        self._regime_per_bar[valid] = htf_regime[idx[valid]]
        self._last_bos_idx_per_bar = np.full(self._n, -1, dtype=np.int64)
        self._last_bos_idx_per_bar[valid] = htf_last_bos_idx[idx[valid]]
        self._entry_bar_bos_idx: dict[int, int] = {}  # pos.id -> last_bos_idx at entry

        # Session gate (LTF timestamps)
        hours = pd.to_datetime(self._ts).hour
        minutes = pd.to_datetime(self._ts).minute
        dates = pd.to_datetime(self._ts).date
        prev_date = np.roll(dates, 1)
        next_date = np.roll(dates, -1)
        is_new_day = (dates != prev_date)
        is_last_of_day = (dates != next_date)
        # crude day-edge mask: within avoid_day_edge_hours of a date change
        day_edge = np.zeros(self._n, dtype=bool)
        h0, m0, h1, m1 = self.news_window_utc
        news_mask = ((hours > h0) | ((hours == h0) & (minutes >= m0))) & \
                    ((hours < h1) | ((hours == h1) & (minutes <= m1)))
        # mark bars within the first/last N hours of the session as day-edge
        day_edge |= (hours < self.avoid_day_edge_hours)
        day_edge |= (hours >= 24 - self.avoid_day_edge_hours)
        self._time_ok = ~day_edge & ~news_mask

        # Chop gate via Kaufman Efficiency Ratio on the HTF
        from backtesting.engine.regime import efficiency_ratio
        htf_close = df_htf["close"].to_numpy()
        htf_er = efficiency_ratio(htf_close, period=self.er_period)
        htf_trend_ok = htf_er > self.er_threshold
        self._trend_ok = np.zeros(self._n, dtype=bool)
        self._trend_ok[valid] = np.nan_to_num(htf_trend_ok[idx[valid]], nan=False).astype(bool)

        # Volatility ceiling is deliberately separate from ER. ER answers
        # "directional or choppy"; ATR/ATRavg answers "calm enough to trade."
        htf_high = df_htf["high"].to_numpy()
        htf_low = df_htf["low"].to_numpy()
        htf_atr = _atr(htf_high, htf_low, htf_close, self.atr_period)
        htf_atr_avg = pd.Series(htf_atr).rolling(100).mean().to_numpy()
        htf_vol_ok = (htf_atr > 0) & (htf_atr_avg > 0) & (htf_atr <= self.atr_ceiling_mult * htf_atr_avg)
        self._vol_ok = np.zeros(self._n, dtype=bool)
        self._vol_ok[valid] = np.nan_to_num(htf_vol_ok[idx[valid]], nan=False).astype(bool)

        self._min_i = max(self.swing_length * 3, self.atr_period) + 5

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._min_i or state.has_open_position:
            return None
        if i - self._last_close_i < self.cooldown_bars:
            return None

        regime = self._regime_per_bar[i]
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0 or regime == 0:
            return None
        if not self._time_ok[i] or not self._trend_ok[i] or not self._vol_ok[i]:
            return None

        pdh, pdl = self._pdh[i], self._pdl[i]

        if regime == 1 and self._vwap_bounce_long[i] and self.direction in ("long", "both"):
            entry = bar.close
            sl = entry - self.atr_mult * atr
            tp1 = pdh if (not np.isnan(pdh) and pdh > entry) else entry + self.atr_mult * atr * 2
            if sl >= entry or tp1 <= entry:
                return None
            if (tp1 - entry) / (entry - sl) < self.min_rr:
                return None
            return Signal(direction=Direction.LONG, entry=entry, sl=sl, tp1=tp1,
                          risk_pct=self.risk_pct, tp1_frac=self.tp1_frac,
                          tp2_frac=0.0, trail=True, label="lvl2_struct_long")

        if regime == -1 and self._vwap_bounce_short[i] and self.direction in ("short", "both"):
            entry = bar.close
            sl = entry + self.atr_mult * atr
            tp1 = pdl if (not np.isnan(pdl) and pdl < entry) else entry - self.atr_mult * atr * 2
            if sl <= entry or tp1 >= entry:
                return None
            if (entry - tp1) / (sl - entry) < self.min_rr:
                return None
            return Signal(direction=Direction.SHORT, entry=entry, sl=sl, tp1=tp1,
                          risk_pct=self.risk_pct, tp1_frac=self.tp1_frac,
                          tp2_frac=0.0, trail=True, label="lvl2_struct_short")
        return None

    def on_close(self, trade, state: EngineState) -> None:
        self._last_close_i = state.bar_index

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        i = bar.index
        if i >= self._n:
            return False

        # Lazily record the BOS index that was already "current" when this
        # position opened -- breakeven only fires on a NEW confirming BOS
        # that happens strictly after entry, not on stale historical state.
        if position.id not in self._entry_bar_bos_idx:
            entry_idx = int(np.searchsorted(self._ts, position.entry_time))
            entry_idx = min(max(entry_idx, 0), self._n - 1)
            self._entry_bar_bos_idx[position.id] = self._last_bos_idx_per_bar[entry_idx]

        regime = self._regime_per_bar[i]
        new_bos_since_entry = self._last_bos_idx_per_bar[i] > self._entry_bar_bos_idx[position.id]
        if new_bos_since_entry:
            if position.direction == Direction.LONG and regime == 1 and position.sl < position.entry_price:
                position.sl = position.entry_price
            elif position.direction == Direction.SHORT and regime == -1 and position.sl > position.entry_price:
                position.sl = position.entry_price

        # Distance-based breakeven: once price has covered 50% of the
        # distance to TP1, lock in breakeven regardless of structure state.
        # Complements the structure-based BE above, doesn't replace it.
        entry, tp1 = position.entry_price, position.tp1
        target_dist = abs(tp1 - entry)
        if target_dist > 0:
            if position.direction == Direction.LONG:
                progress = (bar.close - entry) / target_dist
                if progress >= 0.5 and position.sl < entry:
                    position.sl = entry
            else:
                progress = (entry - bar.close) / target_dist
                if progress >= 0.5 and position.sl > entry:
                    position.sl = entry
        # After TP1, trail the runner with ATR (engine's own trail mechanism
        # handles this via signal.trail=True + tp1_frac<1.0).
        return False
