"""
V1 — HTF regime + Supertrend trend-following.

Separate from the closed mechanical-search family (see CLEAN.md §10). One
fixed, untuned parameter set — no per-instrument grid search this time, that's
the mistake that overfit tr_ict_sweep.py last round.

Mechanism (textbook, not novel):
  - EMA(200) on the entry TF = regime filter. Long only above it, short only
    below it. This is the one piece that survived as "a robust keeper" across
    every prior falsified attempt (see kl_sweep_reclaim_result memory).
  - Supertrend(period, mult) flip in the regime's direction = entry trigger.
  - No fixed take-profit. Exit is the Supertrend line itself, ratcheted in
    the trade's favor each bar via should_close() mutating position.sl —
    classic trend-following payoff (let winners run), not a fixed-RR target.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


def _wma(values: np.ndarray, period: int) -> np.ndarray:
    weights = np.arange(1, period + 1, dtype=float)
    out = np.full(len(values), np.nan)
    for i in range(period - 1, len(values)):
        out[i] = np.dot(values[i - period + 1: i + 1], weights) / weights.sum()
    return out


def _hma(values: np.ndarray, period: int) -> np.ndarray:
    """Hull MA: WMA(2*WMA(n/2) - WMA(n), sqrt(n)) — less lag than SMA/EMA."""
    half = max(1, period // 2)
    sqrt_p = max(1, int(round(np.sqrt(period))))
    wma_half = _wma(values, half)
    wma_full = _wma(values, period)
    raw = 2 * wma_half - wma_full
    raw = np.nan_to_num(raw, nan=values[0])
    return _wma(raw, sqrt_p)


def _moving_average(close: np.ndarray, period: int, ma_type: str) -> np.ndarray:
    if ma_type == "ema":
        return pd.Series(close).ewm(span=period, adjust=False).mean().to_numpy()
    if ma_type == "sma":
        return pd.Series(close).rolling(period).mean().bfill().to_numpy()
    if ma_type == "hma":
        return _hma(close, period)
    raise ValueError(f"Unknown ma_type: {ma_type}")


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 period: int, mult: float) -> tuple[np.ndarray, np.ndarray]:
    """Returns (supertrend_line, direction) — direction: +1 bullish, -1 bearish."""
    n = len(close)
    atr = _atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr

    st = np.full(n, np.nan)
    direction = np.zeros(n, dtype=np.int64)
    direction[: period] = 1

    for i in range(period, n):
        if close[i] > upper[i - 1]:
            direction[i] = 1
        elif close[i] < lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
            if direction[i] == 1 and lower[i] < lower[i - 1]:
                lower[i] = lower[i - 1]
            if direction[i] == -1 and upper[i] > upper[i - 1]:
                upper[i] = upper[i - 1]
        st[i] = lower[i] if direction[i] == 1 else upper[i]

    return st, direction


class TrendV1(Strategy):
    def __init__(
        self,
        ema_period: int = 200,
        st_period: int = 10,
        st_mult: float = 3.0,
        risk_pct: float = 0.005,
        direction: str = "both",  # "long", "short", "both"
        ma_type: str = "ema",     # "sma", "ema", "hma"
    ):
        self.ema_period = ema_period
        self.st_period = st_period
        self.st_mult = st_mult
        self.risk_pct = risk_pct
        self.direction = direction
        self.ma_type = ma_type

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)

        self._high = df["high"].to_numpy()
        self._low = df["low"].to_numpy()
        self._close = df["close"].to_numpy()
        self._n = len(df)

        ma = _moving_average(self._close, self.ema_period, self.ma_type)
        self._regime = np.where(self._close > ma, 1, -1)

        self._st, self._st_dir = _supertrend(self._high, self._low, self._close,
                                              self.st_period, self.st_mult)

        self._min_i = max(self.ema_period, self.st_period) + 2

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._min_i or state.has_open_position:
            return None

        flipped_long = self._st_dir[i] == 1 and self._st_dir[i - 1] == -1
        flipped_short = self._st_dir[i] == -1 and self._st_dir[i - 1] == 1

        if flipped_long and self._regime[i] == 1 and self.direction in ("long", "both"):
            entry = bar.close
            sl = self._st[i]
            if sl >= entry:
                return None
            far_tp = entry + (entry - sl) * 50
            return Signal(direction=Direction.LONG, entry=entry, sl=sl, tp1=far_tp,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="trend_v1_long")

        if flipped_short and self._regime[i] == -1 and self.direction in ("short", "both"):
            entry = bar.close
            sl = self._st[i]
            if sl <= entry:
                return None
            far_tp = entry - (sl - entry) * 50
            return Signal(direction=Direction.SHORT, entry=entry, sl=sl, tp1=far_tp,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="trend_v1_short")

        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        i = bar.index
        if i >= self._n:
            return False
        st_now = self._st[i]
        if position.direction == Direction.LONG:
            if st_now > position.sl:
                position.sl = st_now
        else:
            if st_now < position.sl:
                position.sl = st_now
        return False
