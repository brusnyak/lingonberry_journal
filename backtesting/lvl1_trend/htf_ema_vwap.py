"""
Lvl1 variant — HTF EMA bias + LTF VWAP entry.

User's proposed design: HTF (1H/30m) 21-EMA gives overall direction, LTF (5m)
VWAP gives intraday fair value / entry timing. Grounded in standard retail/
practitioner framing (VWAP = intraday mean institutions benchmark against,
EMA = trend slope) — not novel, deliberately textbook.

Mechanism:
  - HTF regime: price above/below 21-EMA on the HTF (e.g. "60" or "30").
  - LTF entry: VWAP band bounce on the LTF (e.g. "5"), aligned with HTF
    regime — price dipped below the -1sigma VWAP band and closed back above
    it (long), or mirror (short). Reuses backtesting/features/vwap.py
    (causal, session-anchored, already built — not reinvented here).
  - Exit: ATR-trailing stop on the LTF, same should_close() ratchet pattern
    as TrendV1, for comparability.

Caveat: NAS100's volume column in this data store is near-constant
(synthetic placeholder, not real volume) — VWAP there degrades to ~TWAP.
XAUUSD/XAGUSD have real, varying tick volume.
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


class HtfEmaVwap(Strategy):
    def __init__(
        self,
        htf_key: str = "60",
        htf_ema_period: int = 21,
        atr_period: int = 14,
        atr_mult: float = 2.5,
        risk_pct: float = 0.005,
        direction: str = "both",
    ):
        self.htf_key = htf_key
        self.htf_ema_period = htf_ema_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.risk_pct = risk_pct
        self.direction = direction

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

        # HTF regime, mapped onto LTF bar indices (vectorized, no per-bar searchsorted)
        df_htf = data[self.htf_key].copy()
        if "ts" in df_htf.columns:
            df_htf = df_htf.set_index("ts")
        df_htf.sort_index(inplace=True)
        htf_ema = pd.Series(df_htf["close"]).ewm(span=self.htf_ema_period, adjust=False).mean()
        htf_regime = np.where(df_htf["close"].to_numpy() > htf_ema.to_numpy(), 1, -1)
        htf_ts = df_htf.index.to_numpy()

        idx = np.searchsorted(htf_ts, self._ts, side="right") - 1
        mapped = np.zeros(self._n, dtype=np.int64)
        valid = idx >= 0
        mapped[valid] = htf_regime[idx[valid]]
        self._regime_per_bar = mapped

        self._min_i = max(self.htf_ema_period, self.atr_period) + 2

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._min_i or state.has_open_position:
            return None

        regime = self._regime_per_bar[i]
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None

        if regime == 1 and self._vwap_bounce_long[i] and self.direction in ("long", "both"):
            entry = bar.close
            sl = entry - self.atr_mult * atr
            far_tp = entry + (entry - sl) * 50
            return Signal(direction=Direction.LONG, entry=entry, sl=sl, tp1=far_tp,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="htf_ema_vwap_long")

        if regime == -1 and self._vwap_bounce_short[i] and self.direction in ("short", "both"):
            entry = bar.close
            sl = entry + self.atr_mult * atr
            far_tp = entry - (sl - entry) * 50
            return Signal(direction=Direction.SHORT, entry=entry, sl=sl, tp1=far_tp,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="htf_ema_vwap_short")

        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        i = bar.index
        if i >= self._n:
            return False
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return False
        if position.direction == Direction.LONG:
            new_sl = bar.close - self.atr_mult * atr
            if new_sl > position.sl:
                position.sl = new_sl
        else:
            new_sl = bar.close + self.atr_mult * atr
            if new_sl < position.sl:
                position.sl = new_sl
        return False
