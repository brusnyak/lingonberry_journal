"""Feature core — one causal per-bar feature API for the new engine.

Wraps the verified pieces into a single index-aligned object:
  - VWAP + bands/slope/z        (features.vwap.build_vwap_index)
  - ATR (Wilder)
  - ADX(14) + regime label      (trend / range / none)
  - ICT structure               (features.ict_structure, strict causal state machine)
  - running last confirmed swing high/low (invalidation references)

All arrays are aligned 1:1 to the input bars (ascending ts). No lookahead:
ATR/ADX use Wilder RMA (causal), structure pivots are confirmed `right` bars late.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index
from backtesting.features.vwap import build_vwap_index

# ADX regime thresholds (Wilder convention)
ADX_TREND = 25.0
ADX_RANGE = 20.0


def _wilder_rma(x: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing (RMA), causal. alpha = 1/period."""
    return pd.Series(x).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    return _wilder_rma(tr, period)


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ADX. Causal."""
    n = len(high)
    if n < 2:
        return np.zeros(n)
    up = high[1:] - high[:-1]
    dn = low[:-1] - low[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    prev_close = close[:-1]
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)))
    atr_s = _wilder_rma(tr, period)
    plus_di = 100.0 * _wilder_rma(plus_dm, period) / np.where(atr_s == 0, np.nan, atr_s)
    minus_di = 100.0 * _wilder_rma(minus_dm, period) / np.where(atr_s == 0, np.nan, atr_s)
    denom = plus_di + minus_di
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where(denom == 0, np.nan, denom)
    adx_s = _wilder_rma(np.nan_to_num(dx), period)
    out = np.zeros(n)
    out[1:] = adx_s
    return out


def regime_from_adx(adx_arr: np.ndarray) -> np.ndarray:
    out = np.full(len(adx_arr), "none", dtype=object)
    out[adx_arr >= ADX_TREND] = "trend"
    out[adx_arr < ADX_RANGE] = "range"
    return out


class FeatureCore:
    """Causal per-bar features for one timeframe. Arrays aligned to input bars."""

    def __init__(self, df: pd.DataFrame, *, atr_period: int = 14, adx_period: int = 14,
                 ict: IctStructureConfig | None = None):
        d = df.copy()
        if "ts" in d.columns:
            d = d.sort_values("ts").reset_index(drop=True)
        self.n = len(d)

        high = d["high"].to_numpy(dtype=float)
        low = d["low"].to_numpy(dtype=float)
        close = d["close"].to_numpy(dtype=float)
        self.high, self.low, self.close = high, low, close

        # VWAP
        v = build_vwap_index(d)
        for col in ("vwap", "vwap_1h", "vwap_1l", "vwap_2h", "vwap_2l",
                    "vwap_slope_12", "vwap_z_score", "vwap_bounce_long", "vwap_bounce_short"):
            setattr(self, col, v[col].to_numpy())

        # Volatility / regime
        self.atr = atr(high, low, close, atr_period)
        self.adx = adx(high, low, close, adx_period)
        self.regime = regime_from_adx(self.adx)

        # Structure
        s = build_ict_structure_index(d, config=ict or IctStructureConfig(left=3, right=3))
        for col in ("bullish_bos", "bearish_bos", "bullish_choch", "bearish_choch",
                    "direction_bias", "protected_high", "protected_low"):
            setattr(self, col, s[col].to_numpy())

        # Running last confirmed swing high/low (ffill) — invalidation references
        swing_type = s["swing_type"].to_numpy()
        swing_price = s["swing_price"].to_numpy()
        last_hi = np.full(self.n, np.nan)
        last_lo = np.full(self.n, np.nan)
        hi = lo = np.nan
        for i in range(self.n):
            if swing_type[i] == "high" and not np.isnan(swing_price[i]):
                hi = swing_price[i]
            elif swing_type[i] == "low" and not np.isnan(swing_price[i]):
                lo = swing_price[i]
            last_hi[i] = hi
            last_lo[i] = lo
        self.last_swing_high = last_hi
        self.last_swing_low = last_lo

    def is_range(self, i: int) -> bool:
        return 0 <= i < self.n and self.regime[i] == "range"
