"""
Chop-regime mean-reversion — VWAP fade, gated to ER<=0.3 (complement of lvl1's
trend gate). A genuinely different hypothesis from the RSI+BB mean-reversion
already falsified this session: that one ran unconditionally, including
during trends, where mean-reversion gets run over. This only fires when the
market is *measurably* non-trending (Efficiency Ratio), which none of the
prior mean-reversion attempts tested for.

Mechanism: price extends beyond the 2-sigma VWAP band, bet on reversion to
VWAP. Exit at VWAP (mean) or stop beyond the 2-sigma band (fixed RR, not
trend-style trailing -- mean-reversion's edge is hitting the target, not
letting winners run).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.regime import efficiency_ratio
from backtesting.features.vwap import build_vwap_index


class ChopVwapFade(Strategy):
    def __init__(self, er_period: int = 10, er_threshold: float = 0.3,
                 risk_pct: float = 0.005, direction: str = "both"):
        self.er_period = er_period
        self.er_threshold = er_threshold
        self.risk_pct = risk_pct
        self.direction = direction

    def init(self, data: dict) -> None:
        df = next(iter(data.values())).copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        df_vwap = build_vwap_index(df.reset_index(drop=True))

        self._close = df["close"].to_numpy()
        self._n = len(df)
        self._vwap = df_vwap["vwap"].to_numpy()
        self._vwap_2h = df_vwap["vwap_2h"].to_numpy()
        self._vwap_2l = df_vwap["vwap_2l"].to_numpy()
        self._er = efficiency_ratio(self._close, self.er_period)
        self._min_i = self.er_period + 2

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._min_i or state.has_open_position:
            return None
        er = self._er[i]
        if np.isnan(er) or er > self.er_threshold:
            return None  # only fire in chop, complement of lvl1's trend gate

        vwap, hi, lo = self._vwap[i], self._vwap_2h[i], self._vwap_2l[i]
        close = bar.close

        if close < lo and self.direction in ("long", "both"):
            sl = lo - (hi - lo) * 0.5
            return Signal(direction=Direction.LONG, entry=close, sl=sl, tp1=vwap,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="chop_fade_long")
        if close > hi and self.direction in ("short", "both"):
            sl = hi + (hi - lo) * 0.5
            return Signal(direction=Direction.SHORT, entry=close, sl=sl, tp1=vwap,
                          risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0,
                          trail=False, label="chop_fade_short")
        return None
