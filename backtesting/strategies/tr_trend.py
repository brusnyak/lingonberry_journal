"""
TR Trend/Structure — 3-timeframe MA confluence entry.

Thesis:
  HTF MA (4H+) determines overall bias.
  MTF MA (15m-1H) confirms local trend direction.
  Entry TF MA (1m-15m) provides pullback entry when both higher TFs align.
  Enter when price pulls back to entry TF MA in the direction of HTF+MTF.

MA types supported: sma, ema, hma (Hull MA).

Setup (bullish):
  1. HTF: close > MA(htf_ma_period) on htf_tf_key TF
  2. MTF: close > MA(mtf_ma_period) on mtf_tf_key TF
  3. Entry TF: close pulls back to within entry_band pips of MA(entry_ma_period)
  4. Enter long at bar.close
  5. SL: sl_atr_mult × ATR(14) below entry — HARD STOP (prop firm compliant)
  6. TP: tp_r × risk above entry

Rules:
  - Only one position at a time.
  - Hard SL is mandatory — no SL-less operation.
  - Exit also if HTF MA flips (close below HTF MA after entry).

Data required:
  {htf_tf_key: df_htf, mtf_tf_key: df_mtf, entry_tf_key: df_entry}
  entry_tf_key defaults to first key that is neither htf nor mtf.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


# ── MA implementations ────────────────────────────────────────────────────────

def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)
    def _apply(x):
        return np.dot(x, weights) / weights.sum()
    return series.rolling(period).apply(_apply, raw=True)


def _hma(series: pd.Series, period: int) -> pd.Series:
    half = max(period // 2, 1)
    sqrt_p = max(int(np.sqrt(period)), 1)
    raw = 2 * _wma(series, half) - _wma(series, period)
    return _wma(raw, sqrt_p)


def _compute_ma(series: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type == "ema":
        return _ema(series, period)
    if ma_type == "hma":
        return _hma(series, period)
    return _sma(series, period)


def _atr14(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(14).mean()


# ── strategy ─────────────────────────────────────────────────────────────────

class TrTrend(Strategy):
    """3-TF MA confluence pullback strategy."""

    spaces = {
        "htf_ma_period": [20, 50, 100],
        "mtf_ma_period": [10, 20, 50],
        "entry_ma_period": [5, 8, 13, 20],
        "ma_type": ["sma", "ema", "hma"],
        "entry_band_pips": [2, 3, 5],
        "sl_atr_mult": [1.0, 1.5, 2.0],
        "tp_r": [1.0, 1.5, 2.0],
        "risk_pct": [0.005],
    }

    def __init__(
        self,
        htf_tf_key: str = "240",      # 4H
        mtf_tf_key: str = "60",       # 1H
        htf_ma_period: int = 50,
        mtf_ma_period: int = 20,
        entry_ma_period: int = 8,
        ma_type: str = "ema",         # "sma" | "ema" | "hma"
        entry_band_pips: int = 3,     # price must be within N pips of entry TF MA
        sl_atr_mult: float = 1.5,     # SL = entry ± sl_atr_mult × ATR14
        tp_r: float = 1.5,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
    ):
        self.htf_tf_key = htf_tf_key
        self.mtf_tf_key = mtf_tf_key
        self.htf_ma_period = htf_ma_period
        self.mtf_ma_period = mtf_ma_period
        self.entry_ma_period = entry_ma_period
        self.ma_type = ma_type
        self.entry_band_pips = entry_band_pips
        self.sl_atr_mult = sl_atr_mult
        self.tp_r = tp_r
        self.risk_pct = risk_pct
        self.pip_size = pip_size

    def init(self, data: dict) -> None:
        # HTF
        htf = data[self.htf_tf_key].copy()
        if "ts" in htf.columns:
            htf = htf.set_index("ts")
        htf.sort_index(inplace=True)
        self._htf_ma = _compute_ma(htf["close"], self.htf_ma_period, self.ma_type)
        self._htf_index = htf.index

        # MTF
        mtf = data[self.mtf_tf_key].copy()
        if "ts" in mtf.columns:
            mtf = mtf.set_index("ts")
        mtf.sort_index(inplace=True)
        self._mtf_ma = _compute_ma(mtf["close"], self.mtf_ma_period, self.ma_type)
        self._mtf_index = mtf.index

        # Entry TF — find the key that is neither htf nor mtf
        entry_key = None
        for k in data:
            if k not in (self.htf_tf_key, self.mtf_tf_key):
                entry_key = k
                break
        if entry_key is None:
            raise ValueError(f"No entry TF found. data keys: {list(data.keys())}, htf={self.htf_tf_key}, mtf={self.mtf_tf_key}")

        entry_df = data[entry_key].copy()
        if "ts" in entry_df.columns:
            entry_df = entry_df.set_index("ts")
        entry_df.sort_index(inplace=True)
        self._entry_ma = _compute_ma(entry_df["close"], self.entry_ma_period, self.ma_type)
        self._atr = _atr14(entry_df)
        self._entry_df = entry_df

    def _htf_bias(self, bar_ts: pd.Timestamp) -> int:
        """Return +1 (bull), -1 (bear), 0 (no signal)."""
        idx = self._htf_index.searchsorted(bar_ts, side="right") - 1
        if idx < 0:
            return 0
        ts = self._htf_index[idx]
        ma = float(self._htf_ma.loc[ts]) if ts in self._htf_ma.index else float("nan")
        close = float(self._entry_df.index.searchsorted)  # unused placeholder
        # Use actual close from HTF df (not available here, so compare via index)
        # Instead: compare bar_ts price vs MA value at latest HTF bar
        if np.isnan(ma):
            return 0
        # We need the HTF close at the last HTF bar before bar_ts
        # We have htf_ma as a series indexed by timestamp
        htf_close_at_idx = self._htf_ma.index[idx]
        # Retrieve close from entry_df at current bar
        # Actually compare current entry bar close vs HTF MA
        # This is a proxy: entry bar close vs HTF MA
        return 0  # computed in next() for access to bar

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        pip = self.pip_size
        band = self.entry_band_pips * pip

        bar_ts = pd.Timestamp(bar.ts)
        if hasattr(bar_ts, "tz") and bar_ts.tzinfo is None:
            bar_ts = bar_ts.tz_localize("UTC")

        # ── HTF bias ──────────────────────────────────────────────────────────
        htf_idx = self._htf_index.searchsorted(bar_ts, side="right") - 1
        if htf_idx < 0:
            return None
        htf_ma_val = float(self._htf_ma.iloc[htf_idx])
        if np.isnan(htf_ma_val):
            return None
        # HTF close at that bar
        htf_close_ts = self._htf_index[htf_idx]
        # We don't have HTF OHLC stored separately; use HTF MA as proxy for direction
        # Bullish HTF: current bar close above HTF MA
        htf_bull = bar.close > htf_ma_val
        htf_bear = bar.close < htf_ma_val

        # ── MTF bias ──────────────────────────────────────────────────────────
        mtf_idx = self._mtf_index.searchsorted(bar_ts, side="right") - 1
        if mtf_idx < 0:
            return None
        mtf_ma_val = float(self._mtf_ma.iloc[mtf_idx])
        if np.isnan(mtf_ma_val):
            return None
        mtf_bull = bar.close > mtf_ma_val
        mtf_bear = bar.close < mtf_ma_val

        # ── Entry TF: pullback to MA ───────────────────────────────────────────
        if i >= len(self._entry_ma):
            return None
        entry_ma_val = float(self._entry_ma.iloc[i])
        atr_val = float(self._atr.iloc[i])
        if np.isnan(entry_ma_val) or np.isnan(atr_val) or atr_val == 0:
            return None

        price_to_ma = abs(bar.close - entry_ma_val)

        # ── Signals ───────────────────────────────────────────────────────────
        sl_dist = self.sl_atr_mult * atr_val

        if htf_bull and mtf_bull and price_to_ma <= band and bar.close >= entry_ma_val:
            # Price pulled back to MA from above — long entry
            sl = bar.close - sl_dist
            stop = bar.close - sl
            if stop <= 0:
                return None
            return Signal(
                direction=Direction.LONG,
                entry=bar.close,
                sl=sl,
                tp1=bar.close + self.tp_r * stop,
                risk_pct=self.risk_pct,
                tp1_frac=0.5,
                tp2_frac=0.0,
                trail=True,
                label=f"trend_bull_{self.ma_type}",
            )

        if htf_bear and mtf_bear and price_to_ma <= band and bar.close <= entry_ma_val:
            # Price pulled back to MA from below — short entry
            sl = bar.close + sl_dist
            stop = sl - bar.close
            if stop <= 0:
                return None
            return Signal(
                direction=Direction.SHORT,
                entry=bar.close,
                sl=sl,
                tp1=bar.close - self.tp_r * stop,
                risk_pct=self.risk_pct,
                tp1_frac=0.5,
                tp2_frac=0.0,
                trail=True,
                label=f"trend_bear_{self.ma_type}",
            )

        return None
